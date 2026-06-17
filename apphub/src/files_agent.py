import base64
import grp
import hashlib
import json
import os
import pwd
import shutil
import stat
import tempfile
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, Optional

import docker
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse


TEXT_FILE_LIMIT_BYTES = 1024 * 1024
DOCKER_HELPER_MOUNT_PATH = "/workspace"
DOCKER_HELPER_IMAGE_FALLBACK = "python:3.11-slim"
DOCKER_HELPER_IDLE_TTL_SECONDS = max(int(os.getenv("WEBSOFT9_FILES_AGENT_HELPER_IDLE_TTL", "300") or "300"), 30)
DOCKER_HELPER_SCRIPT = r'''
import base64
import grp
import json
import os
import pwd
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

ROOT = os.environ.get("WEBSOFT9_FILE_HELPER_ROOT", "/workspace")
TEXT_FILE_LIMIT_BYTES = 1024 * 1024

def fail(status_code, message, details=""):
    print(json.dumps({"ok": False, "status_code": status_code, "message": message, "details": details}))
    sys.exit(1)

def normalize_relative_path(path_value, allow_root=True):
    raw = str(path_value or "/").strip() or "/"
    normalized = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
    parts = []
    for part in normalized.parts:
        if part in {"", "/", "."}:
            continue
        if part == "..":
            fail(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
        parts.append(part)
    path = "/" if not parts else "/" + "/".join(parts)
    if not allow_root and path == "/":
        fail(400, "Invalid Request", "The volume root is not a valid target for this operation")
    return path

def resolve_target_path(requested_path, allow_root=True, require_exists=True):
    normalized = normalize_relative_path(requested_path, allow_root=allow_root)
    target_path = os.path.realpath(os.path.join(ROOT, normalized.lstrip("/")))
    root_real = os.path.realpath(ROOT)
    if not (target_path == root_real or target_path.startswith(root_real + os.sep)):
        fail(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
    if require_exists and not os.path.exists(target_path):
        fail(404, "File Not Found", "The requested path does not exist")
    return target_path

def normalize_name(value):
    normalized = str(value or "").strip()
    if not normalized:
        fail(400, "Invalid Request", "Name cannot be empty")
    if "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        fail(400, "Invalid Request", "Name cannot include path separators or traversal tokens")
    return normalized

def normalize_item_path(root_path, entry_path):
    relative = os.path.relpath(entry_path, root_path)
    return "/" if relative == "." else "/" + relative.replace(os.sep, "/")

def format_timestamp(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

def lookup_owner(uid, include_id=False):
    try:
        value = pwd.getpwuid(uid).pw_name
    except KeyError:
        value = str(uid)
    return f"{value} ({uid})" if include_id else value

def lookup_group(gid, include_id=False):
    try:
        value = grp.getgrgid(gid).gr_name
    except KeyError:
        value = str(gid)
    return f"{value} ({gid})" if include_id else value

def infer_text_editable(name, item_type, size, mode):
    if item_type != "file" or size > TEXT_FILE_LIMIT_BYTES or not stat.S_ISREG(mode):
        return False
    return True

def build_metadata(target_path, display_name, stat_result, include_identity_ids):
    relative = os.path.relpath(target_path, ROOT)
    name = display_name if relative == "." else os.path.basename(target_path.rstrip(os.sep)) or display_name or "/"
    item_type = "directory" if os.path.isdir(target_path) else "file"
    return {
        "name": name,
        "path": "/" if relative == "." else "/" + relative.replace(os.sep, "/"),
        "item_type": item_type,
        "size": stat_result.st_size,
        "mode": stat.filemode(stat_result.st_mode),
        "owner": lookup_owner(stat_result.st_uid, include_id=include_identity_ids),
        "group": lookup_group(stat_result.st_gid, include_id=include_identity_ids),
        "accessed_at": format_timestamp(stat_result.st_atime),
        "modified_at": format_timestamp(stat_result.st_mtime),
        "created_at": format_timestamp(stat_result.st_ctime),
        "text_editable": infer_text_editable(name, item_type, stat_result.st_size, stat_result.st_mode),
    }

def parse_identity_value(value, kind):
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith(")") and " (" in normalized:
        normalized = normalized.rsplit(" (", 1)[0].strip()
    if normalized.isdigit():
        return int(normalized)
    try:
        if kind == "owner":
            return pwd.getpwnam(normalized).pw_uid
        return grp.getgrnam(normalized).gr_gid
    except KeyError:
        fail(400, "Invalid Request", f"Unknown {kind}: {normalized}")

def build_permission_mode(payload):
    permission_groups = (
        payload.get("owner_permissions") or {},
        payload.get("group_permissions") or {},
        payload.get("other_permissions") or {},
    )
    if not any(group for group in permission_groups):
        return None
    def bits(group):
        value = 0
        if group.get("read"):
            value |= 4
        if group.get("write"):
            value |= 2
        if group.get("execute"):
            value |= 1
        return value
    return (bits(permission_groups[0]) << 6) | (bits(permission_groups[1]) << 3) | bits(permission_groups[2])

def emit(value):
    print(json.dumps({"ok": True, "data": value}))

def action_directory(payload):
    target_path = resolve_target_path(payload.get("path", "/"))
    if not os.path.isdir(target_path):
        fail(400, "Invalid Request", "The requested path is not a directory")
    directory_stat = os.stat(target_path, follow_symlinks=False)
    metadata = build_metadata(target_path, payload.get("display_name", ""), directory_stat, False)
    try:
        entries = sorted(os.scandir(target_path), key=lambda entry: entry.name.lower())
    except FileNotFoundError:
        fail(404, "File Not Found", "The requested path disappeared while being read")
    items = []
    for entry in entries:
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        item_type = "directory" if entry.is_dir(follow_symlinks=False) else "file"
        size = 0 if item_type == "directory" else entry_stat.st_size
        items.append({
            "name": entry.name,
            "path": normalize_item_path(target_path, entry.path),
            "item_type": item_type,
            "size": size,
            "mode": stat.filemode(entry_stat.st_mode),
            "owner": lookup_owner(entry_stat.st_uid),
            "group": lookup_group(entry_stat.st_gid),
            "accessed_at": format_timestamp(entry_stat.st_atime),
            "modified_at": format_timestamp(entry_stat.st_mtime),
            "created_at": format_timestamp(entry_stat.st_ctime),
            "text_editable": infer_text_editable(entry.name, item_type, size, entry_stat.st_mode),
        })
    emit({"metadata": metadata, "items": items})

def action_metadata(payload):
    target_path = resolve_target_path(payload.get("path", "/"))
    target_stat = os.stat(target_path, follow_symlinks=False)
    emit(build_metadata(target_path, payload.get("display_name", ""), target_stat, True))

def action_read_text(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False)
    if not os.path.isfile(target_path):
        fail(404, "File Not Found", "The requested file does not exist")
    size = os.path.getsize(target_path)
    if size > TEXT_FILE_LIMIT_BYTES:
        fail(400, "Unsupported File", "The selected file is too large for inline text editing")
    with open(target_path, "rb") as handle:
        raw = handle.read()
    if b"\x00" in raw:
        fail(400, "Unsupported File", "Binary files cannot be opened in the inline editor")
    try:
        emit({"content": raw.decode("utf-8")})
    except UnicodeDecodeError:
        fail(400, "Unsupported File", "Only UTF-8 text files are supported for inline editing")

def action_write_text(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False, require_exists=False)
    parent_path = os.path.dirname(target_path)
    os.makedirs(parent_path, exist_ok=True)
    original_stat = os.stat(target_path) if os.path.exists(target_path) else None
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=parent_path, delete=False) as handle:
            handle.write(str(payload.get("content", "")))
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, target_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
    if original_stat is not None:
        try:
            os.chown(target_path, original_stat.st_uid, original_stat.st_gid)
        except OSError:
            pass
        try:
            os.chmod(target_path, stat.S_IMODE(original_stat.st_mode))
        except OSError:
            pass
    emit({"status": "ok"})

def action_create_directory(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False, require_exists=False)
    os.makedirs(target_path, exist_ok=False)
    emit({"status": "ok"})

def action_create_file(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False, require_exists=False)
    parent_path = os.path.dirname(target_path)
    os.makedirs(parent_path, exist_ok=True)
    with open(target_path, "x", encoding="utf-8"):
        pass
    emit({"status": "ok"})

def action_rename(payload):
    source_path = resolve_target_path(payload.get("source_path", "/"), allow_root=False)
    target_path = resolve_target_path(payload.get("target_path", "/"), allow_root=False, require_exists=False)
    if not os.path.exists(source_path):
        fail(404, "File Not Found", "The source path does not exist")
    parent_path = os.path.dirname(target_path)
    if not os.path.isdir(parent_path):
        fail(400, "Invalid Request", "The target parent directory does not exist")
    os.rename(source_path, target_path)
    emit({"status": "ok"})

def action_copy(payload):
    source_path = resolve_target_path(payload.get("source_path", "/"), allow_root=False)
    destination_path = resolve_target_path(payload.get("destination_path", "/"))
    if not os.path.exists(source_path):
        fail(404, "File Not Found", "The source path does not exist")
    if not os.path.isdir(destination_path):
        fail(400, "Invalid Request", "The destination path must be an existing directory")
    target_path = os.path.join(destination_path, os.path.basename(source_path.rstrip(os.sep)))
    if os.path.realpath(target_path) == os.path.realpath(source_path):
        fail(400, "Invalid Request", "The selected item is already in this directory")
    if os.path.exists(target_path):
        fail(400, "Invalid Request", "A file or directory with the same name already exists")
    if os.path.isdir(source_path) and os.path.realpath(target_path).startswith(os.path.realpath(source_path) + os.sep):
        fail(400, "Invalid Request", "A directory cannot be copied into itself")
    if os.path.isdir(source_path):
        shutil.copytree(source_path, target_path)
    else:
        shutil.copy2(source_path, target_path)
    emit({"status": "ok"})

def action_move(payload):
    source_path = resolve_target_path(payload.get("source_path", "/"), allow_root=False)
    destination_path = resolve_target_path(payload.get("destination_path", "/"))
    if not os.path.exists(source_path):
        fail(404, "File Not Found", "The source path does not exist")
    if not os.path.isdir(destination_path):
        fail(400, "Invalid Request", "The destination path must be an existing directory")
    target_path = os.path.join(destination_path, os.path.basename(source_path.rstrip(os.sep)))
    if os.path.realpath(target_path) == os.path.realpath(source_path):
        fail(400, "Invalid Request", "The selected item is already in this directory")
    if os.path.exists(target_path):
        fail(400, "Invalid Request", "A file or directory with the same name already exists")
    if os.path.isdir(source_path) and os.path.realpath(target_path).startswith(os.path.realpath(source_path) + os.sep):
        fail(400, "Invalid Request", "A directory cannot be moved into itself")
    shutil.move(source_path, target_path)
    emit({"status": "ok"})

def action_attributes(payload):
    source_path = resolve_target_path(payload.get("source_path", "/"), allow_root=False)
    if not os.path.exists(source_path):
        fail(404, "File Not Found", "The source path does not exist")
    target_path = source_path
    target_name = str(payload.get("target_name") or "").strip() or None
    if target_name and target_name != os.path.basename(source_path.rstrip(os.sep)):
        target_relative_path = str(PurePosixPath(normalize_relative_path(payload.get("source_path", "/"))).parent / target_name)
        target_path = resolve_target_path(target_relative_path, allow_root=False, require_exists=False)
        if os.path.exists(target_path):
            fail(400, "Invalid Request", "A file or directory with the same name already exists")
        os.rename(source_path, target_path)
    owner = parse_identity_value(payload.get("owner"), "owner")
    group = parse_identity_value(payload.get("group"), "group")
    if owner is not None or group is not None:
        stat_result = os.stat(target_path, follow_symlinks=False)
        os.chown(target_path, owner if owner is not None else stat_result.st_uid, group if group is not None else stat_result.st_gid, follow_symlinks=False)
    permission_mode = build_permission_mode(payload)
    if permission_mode is not None:
        os.chmod(target_path, permission_mode, follow_symlinks=False)
    target_stat = os.stat(target_path, follow_symlinks=False)
    emit(build_metadata(target_path, payload.get("display_name", ""), target_stat, True))

def action_delete(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False)
    if not os.path.exists(target_path):
        fail(404, "File Not Found", "The target path does not exist")
    if os.path.isdir(target_path):
        shutil.rmtree(target_path)
    else:
        os.remove(target_path)
    emit({"status": "ok"})

def action_upload(payload):
    parent_path = resolve_target_path(payload.get("parent_path", "/"))
    if not os.path.isdir(parent_path):
        fail(400, "Invalid Request", "Upload target directory does not exist")
    try:
        content = base64.b64decode(str(payload.get("content_base64") or "").encode("utf-8"), validate=True)
    except Exception:
        fail(400, "Invalid Request", "content_base64 must be valid base64")
    file_name = normalize_name(payload.get("file_name", ""))
    relative_parent = normalize_relative_path(payload.get("parent_path", "/"))
    target_relative_path = str(PurePosixPath(relative_parent) / file_name)
    target_path = resolve_target_path(target_relative_path, allow_root=False, require_exists=False)
    with open(target_path, "wb") as handle:
        handle.write(content)
    emit({"status": "ok"})

def action_download(payload):
    target_path = resolve_target_path(payload.get("path", "/"), allow_root=False)
    if not os.path.isfile(target_path):
        fail(400, "Invalid Request", "Only file downloads are supported")
    with open(target_path, "rb") as handle:
        emit({"content_base64": base64.b64encode(handle.read()).decode("utf-8")})

payload = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8")) if len(sys.argv) > 2 else {}
action = sys.argv[1]
actions = {
    "directory": action_directory,
    "metadata": action_metadata,
    "read-text": action_read_text,
    "write-text": action_write_text,
    "create-directory": action_create_directory,
    "create-file": action_create_file,
    "rename": action_rename,
    "copy": action_copy,
    "move": action_move,
    "attributes": action_attributes,
    "delete": action_delete,
    "upload": action_upload,
    "download": action_download,
}

try:
    handler = actions[action]
except KeyError:
    fail(400, "Invalid Request", f"Unknown helper action: {action}")

try:
    handler(payload)
except FileExistsError:
    fail(400, "Invalid Request", "A file or directory with the same name already exists")
except PermissionError as exc:
    fail(500, "File Operation Error", str(exc))
except OSError as exc:
    fail(500, "File Operation Error", str(exc))
'''


class DockerHelperManager:
    def __init__(self, docker_client=None, helper_image: Optional[str] = None, idle_ttl_seconds: int = DOCKER_HELPER_IDLE_TTL_SECONDS):
        self.docker_client = docker_client
        self.helper_image = helper_image
        self.idle_ttl_seconds = idle_ttl_seconds
        self._lock = threading.Lock()
        self._helpers: dict[str, dict[str, object]] = {}

    def execute(self, root_path: str, action: str, payload: dict[str, object]) -> dict[str, object]:
        encoded_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        container = self._ensure_container(root_path)
        try:
            result = container.exec_run(
                ["python3", "-c", DOCKER_HELPER_SCRIPT, action, encoded_payload],
                environment={"WEBSOFT9_FILE_HELPER_ROOT": DOCKER_HELPER_MOUNT_PATH},
            )
        except Exception as exc:
            self._drop_container(root_path, force_remove=True)
            raise CustomException(500, "File Operation Error", f"Failed to execute Docker helper action: {exc}")
        output = result.output.decode("utf-8", errors="replace").strip()
        return self._parse_output(output)

    def _ensure_container(self, root_path: str):
        with self._lock:
            self._prune_stale_locked()
            entry = self._helpers.get(root_path)
            if entry is not None:
                container = self._load_running_container(entry.get("container_id"))
                if container is not None:
                    entry["last_used"] = time.monotonic()
                    return container
                self._helpers.pop(root_path, None)

            container = self._create_container(root_path)
            self._helpers[root_path] = {"container_id": container.id, "last_used": time.monotonic()}
            return container

    def _prune_stale_locked(self) -> None:
        now = time.monotonic()
        stale_roots = [
            root_path
            for root_path, entry in self._helpers.items()
            if now - float(entry.get("last_used") or 0.0) > self.idle_ttl_seconds
        ]
        for root_path in stale_roots:
            container_id = self._helpers.pop(root_path, {}).get("container_id")
            self._remove_container(container_id)

    def _create_container(self, root_path: str):
        client = self._get_docker_client()
        image = self._get_helper_image()
        name = f"websoft9-files-helper-{hashlib.sha1(root_path.encode('utf-8')).hexdigest()[:12]}"
        self._remove_container(name)
        try:
            return client.containers.run(
                image,
                command=["sh", "-lc", "while true; do sleep 3600; done"],
                detach=True,
                remove=False,
                user="0:0",
                working_dir=DOCKER_HELPER_MOUNT_PATH,
                name=name,
                labels={
                    "com.websoft9.role": "files-helper",
                    "com.websoft9.files-root": root_path,
                },
                volumes={root_path: {"bind": DOCKER_HELPER_MOUNT_PATH, "mode": "rw"}},
            )
        except docker.errors.ImageNotFound:
            client.images.pull(image)
            return client.containers.run(
                image,
                command=["sh", "-lc", "while true; do sleep 3600; done"],
                detach=True,
                remove=False,
                user="0:0",
                working_dir=DOCKER_HELPER_MOUNT_PATH,
                name=name,
                labels={
                    "com.websoft9.role": "files-helper",
                    "com.websoft9.files-root": root_path,
                },
                volumes={root_path: {"bind": DOCKER_HELPER_MOUNT_PATH, "mode": "rw"}},
            )
        except Exception as exc:
            raise CustomException(500, "File Operation Error", f"Failed to start Docker helper container: {exc}")

    def _load_running_container(self, container_ref):
        if not container_ref:
            return None
        try:
            container = self._get_docker_client().containers.get(container_ref)
            container.reload()
            if container.attrs.get("State", {}).get("Running"):
                return container
        except Exception:
            return None
        return None

    def _drop_container(self, root_path: str, *, force_remove: bool) -> None:
        with self._lock:
            entry = self._helpers.pop(root_path, None)
        if force_remove and entry is not None:
            self._remove_container(entry.get("container_id"))

    def _remove_container(self, container_ref) -> None:
        if not container_ref:
            return
        try:
            container = self._get_docker_client().containers.get(container_ref)
            container.remove(force=True)
        except Exception:
            pass

    def _get_docker_client(self):
        if self.docker_client is None:
            self.docker_client = docker.from_env()
        return self.docker_client

    def _get_helper_image(self) -> str:
        if self.helper_image:
            return self.helper_image
        configured_image = os.getenv("WEBSOFT9_FILE_HELPER_IMAGE", "").strip()
        if configured_image:
            self.helper_image = configured_image
            return configured_image
        hostname = os.getenv("HOSTNAME", "").strip()
        if hostname:
            try:
                container = self._get_docker_client().containers.get(hostname)
                image = str(container.attrs.get("Config", {}).get("Image") or "").strip()
                if image:
                    self.helper_image = image
                    return image
            except Exception:
                pass
        try:
            for image in self._get_docker_client().images.list(name="websoft9dev/websoft9"):
                for tag in image.tags:
                    if tag.startswith("websoft9dev/websoft9:"):
                        self.helper_image = tag
                        return tag
        except Exception:
            pass
        self.helper_image = DOCKER_HELPER_IMAGE_FALLBACK
        return self.helper_image

    @staticmethod
    def _parse_output(output: str) -> dict[str, object]:
        if not output:
            raise CustomException(500, "File Operation Error", "Docker helper returned no output")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise CustomException(500, "File Operation Error", f"Invalid Docker helper response: {exc}: {output}")
        if not payload.get("ok"):
            raise CustomException(
                int(payload.get("status_code") or 500),
                str(payload.get("message") or "File Operation Error"),
                str(payload.get("details") or ""),
            )
        data = payload.get("data")
        return data if isinstance(data, dict) else {"value": data}


@lru_cache(maxsize=1)
def _helper_manager() -> DockerHelperManager:
    return DockerHelperManager()


class AgentPathRequest(BaseModel):
    root_path: str = Field(min_length=1)
    path: str = Field(default="/")
    display_name: str = Field(default="")


class AgentWriteTextRequest(AgentPathRequest):
    content: str = Field(default="", max_length=TEXT_FILE_LIMIT_BYTES)


class AgentRenameRequest(BaseModel):
    root_path: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    display_name: str = Field(default="")


class AgentCopyRequest(BaseModel):
    root_path: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    destination_path: str = Field(min_length=1)
    display_name: str = Field(default="")


class AgentPermissionBits(BaseModel):
    read: bool = False
    write: bool = False
    execute: bool = False


class AgentUpdateAttributesRequest(BaseModel):
    root_path: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    target_name: Optional[str] = Field(default=None)
    owner: Optional[str] = Field(default=None)
    group: Optional[str] = Field(default=None)
    owner_permissions: AgentPermissionBits = Field(default_factory=AgentPermissionBits)
    group_permissions: AgentPermissionBits = Field(default_factory=AgentPermissionBits)
    other_permissions: AgentPermissionBits = Field(default_factory=AgentPermissionBits)
    display_name: str = Field(default="")


class AgentUploadRequest(BaseModel):
    root_path: str = Field(min_length=1)
    parent_path: str = Field(default="/")
    file_name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    display_name: str = Field(default="")


app = FastAPI(title="Websoft9 Files Agent", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(CustomException)
async def custom_exception_handler(_request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(message=exc.message, details=exc.details).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    errors = ", ".join(f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors())
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(message="Request Validation Error", details=errors).model_dump(),
    )


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@app.post("/internal/files/directory")
async def list_directory(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "directory", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path)
    if not os.path.isdir(target_path):
        raise CustomException(400, "Invalid Request", "The requested path is not a directory")

    directory_stat = os.stat(target_path, follow_symlinks=False)
    metadata = _build_metadata(
        target_path,
        root_path,
        payload.display_name,
        directory_stat,
        include_identity_ids=False,
    )

    try:
        entries = sorted(os.scandir(target_path), key=lambda entry: entry.name.lower())
    except FileNotFoundError:
        raise CustomException(404, "File Not Found", "The requested path disappeared while being read")

    items = []
    for entry in entries:
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        item_type = "directory" if entry.is_dir(follow_symlinks=False) else "file"
        size = 0 if item_type == "directory" else entry_stat.st_size
        items.append(
            {
                "name": entry.name,
                "path": _normalize_item_path(root_path, entry.path),
                "item_type": item_type,
                "size": size,
                "mode": stat.filemode(entry_stat.st_mode),
                "owner": _lookup_owner(entry_stat.st_uid),
                "group": _lookup_group(entry_stat.st_gid),
                "accessed_at": _format_timestamp(entry_stat.st_atime),
                "modified_at": _format_timestamp(entry_stat.st_mtime),
                "created_at": _format_timestamp(entry_stat.st_ctime),
                "text_editable": _infer_text_editable(entry.name, item_type, size, entry_stat.st_mode),
            }
        )

    return {"metadata": metadata, "items": items}


@app.post("/internal/files/metadata")
async def get_metadata(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "metadata", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path)
    if not os.path.exists(target_path):
        raise CustomException(404, "File Not Found", "The requested path does not exist")
    target_stat = os.stat(target_path, follow_symlinks=False)
    return _build_metadata(
        target_path,
        root_path,
        payload.display_name,
        target_stat,
        include_identity_ids=True,
    )


@app.post("/internal/files/read-text")
async def read_text_file(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "read-text", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False)
    if not os.path.isfile(target_path):
        raise CustomException(404, "File Not Found", "The requested file does not exist")
    size = os.path.getsize(target_path)
    if size > TEXT_FILE_LIMIT_BYTES:
        raise CustomException(400, "Unsupported File", "The selected file is too large for inline text editing")
    with open(target_path, "rb") as handle:
        raw = handle.read()
    if b"\x00" in raw:
        raise CustomException(400, "Unsupported File", "Binary files cannot be opened in the inline editor")
    try:
        return {"content": raw.decode("utf-8")}
    except UnicodeDecodeError:
        raise CustomException(400, "Unsupported File", "Only UTF-8 text files are supported for inline editing")


@app.put("/internal/files/write-text")
async def write_text_file(payload: AgentWriteTextRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "write-text", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False, require_exists=False)
    parent_path = os.path.dirname(target_path)
    _ensure_inside_root(root_path, parent_path)
    os.makedirs(parent_path, exist_ok=True)

    # Preserve original owner, group, and mode if the file already exists
    original_stat = None
    if os.path.exists(target_path):
        original_stat = os.stat(target_path)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=parent_path, delete=False) as handle:
            handle.write(payload.content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, target_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    # Restore original ownership and permissions
    if original_stat is not None:
        try:
            os.chown(target_path, original_stat.st_uid, original_stat.st_gid)
        except OSError:
            pass
        try:
            os.chmod(target_path, stat.S_IMODE(original_stat.st_mode))
        except OSError:
            pass

    return {"status": "ok"}


@app.post("/internal/files/create-directory")
async def create_directory(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "create-directory", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False, require_exists=False)
    os.makedirs(target_path, exist_ok=False)
    return {"status": "ok"}


@app.post("/internal/files/create-file")
async def create_empty_file(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "create-file", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False, require_exists=False)
    parent_path = os.path.dirname(target_path)
    _ensure_inside_root(root_path, parent_path)
    os.makedirs(parent_path, exist_ok=True)
    with open(target_path, "x", encoding="utf-8"):
        pass
    return {"status": "ok"}


@app.post("/internal/files/rename")
async def rename_path(payload: AgentRenameRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "rename", payload.model_dump(exclude_none=True))
    source_path = _resolve_target_path(root_path, payload.source_path, allow_root=False)
    target_path = _resolve_target_path(root_path, payload.target_path, allow_root=False, require_exists=False)
    if not os.path.exists(source_path):
        raise CustomException(404, "File Not Found", "The source path does not exist")
    parent_path = os.path.dirname(target_path)
    if not os.path.isdir(parent_path):
        raise CustomException(400, "Invalid Request", "The target parent directory does not exist")
    os.rename(source_path, target_path)
    return {"status": "ok"}


@app.post("/internal/files/copy")
async def copy_path(payload: AgentCopyRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "copy", payload.model_dump(exclude_none=True))
    source_path = _resolve_target_path(root_path, payload.source_path, allow_root=False)
    destination_path = _resolve_target_path(root_path, payload.destination_path)
    if not os.path.exists(source_path):
        raise CustomException(404, "File Not Found", "The source path does not exist")
    if not os.path.isdir(destination_path):
        raise CustomException(400, "Invalid Request", "The destination path must be an existing directory")

    target_path = os.path.join(destination_path, os.path.basename(source_path.rstrip(os.sep)))
    _ensure_inside_root(root_path, target_path, allow_root=False)
    if os.path.realpath(target_path) == os.path.realpath(source_path):
        raise CustomException(400, "Invalid Request", "The selected item is already in this directory")
    if os.path.exists(target_path):
        raise CustomException(400, "Invalid Request", "A file or directory with the same name already exists")
    if os.path.isdir(source_path) and _is_within_root(target_path, source_path):
        raise CustomException(400, "Invalid Request", "A directory cannot be copied into itself")

    if os.path.isdir(source_path):
        shutil.copytree(source_path, target_path)
    else:
        shutil.copy2(source_path, target_path)
    return {"status": "ok"}


@app.post("/internal/files/move")
async def move_path(payload: AgentCopyRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "move", payload.model_dump(exclude_none=True))
    source_path = _resolve_target_path(root_path, payload.source_path, allow_root=False)
    destination_path = _resolve_target_path(root_path, payload.destination_path)
    if not os.path.exists(source_path):
        raise CustomException(404, "File Not Found", "The source path does not exist")
    if not os.path.isdir(destination_path):
        raise CustomException(400, "Invalid Request", "The destination path must be an existing directory")

    target_path = os.path.join(destination_path, os.path.basename(source_path.rstrip(os.sep)))
    _ensure_inside_root(root_path, target_path, allow_root=False)
    if os.path.realpath(target_path) == os.path.realpath(source_path):
        raise CustomException(400, "Invalid Request", "The selected item is already in this directory")
    if os.path.exists(target_path):
        raise CustomException(400, "Invalid Request", "A file or directory with the same name already exists")
    if os.path.isdir(source_path) and _is_within_root(target_path, source_path):
        raise CustomException(400, "Invalid Request", "A directory cannot be moved into itself")

    shutil.move(source_path, target_path)
    return {"status": "ok"}


@app.put("/internal/files/attributes")
async def update_attributes(payload: AgentUpdateAttributesRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "attributes", payload.model_dump(exclude_none=True))
    source_path = _resolve_target_path(root_path, payload.source_path, allow_root=False)
    if not os.path.exists(source_path):
        raise CustomException(404, "File Not Found", "The source path does not exist")

    target_path = source_path
    target_name = (payload.target_name or "").strip() or None
    if target_name and target_name != os.path.basename(source_path.rstrip(os.sep)):
        target_relative_path = str(PurePosixPath(_normalize_relative_path(payload.source_path)).parent / target_name)
        target_path = _resolve_target_path(root_path, target_relative_path, allow_root=False, require_exists=False)
        if os.path.exists(target_path):
            raise CustomException(400, "Invalid Request", "A file or directory with the same name already exists")
        os.rename(source_path, target_path)

    owner = _parse_owner_value(payload.owner)
    group = _parse_group_value(payload.group)
    if owner is not None or group is not None:
        stat_result = os.stat(target_path, follow_symlinks=False)
        os.chown(
            target_path,
            owner if owner is not None else stat_result.st_uid,
            group if group is not None else stat_result.st_gid,
            follow_symlinks=False,
        )

    permission_mode = _build_permission_mode(payload)
    if permission_mode is not None:
        os.chmod(target_path, permission_mode, follow_symlinks=False)

    target_stat = os.stat(target_path, follow_symlinks=False)
    return _build_metadata(
        target_path,
        root_path,
        payload.display_name,
        target_stat,
        include_identity_ids=True,
    )


@app.delete("/internal/files/path")
async def delete_path(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "delete", payload.model_dump(exclude_none=True))
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False)
    if not os.path.exists(target_path):
        raise CustomException(404, "File Not Found", "The target path does not exist")
    if os.path.isdir(target_path):
        shutil.rmtree(target_path)
    else:
        os.remove(target_path)
    return {"status": "ok"}


@app.post("/internal/files/upload")
async def upload_file(payload: AgentUploadRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        return _helper_manager().execute(root_path, "upload", payload.model_dump(exclude_none=True))
    parent_path = _resolve_target_path(root_path, payload.parent_path)
    if not os.path.isdir(parent_path):
        raise CustomException(400, "Invalid Request", "Upload target directory does not exist")
    try:
        content = base64.b64decode(payload.content_base64.encode("utf-8"), validate=True)
    except Exception:
        raise CustomException(400, "Invalid Request", "content_base64 must be valid base64")
    file_name = _normalize_name(payload.file_name)
    relative_parent = _normalize_relative_path(payload.parent_path)
    target_relative_path = str(PurePosixPath(relative_parent) / file_name)
    target_path = _resolve_target_path(root_path, target_relative_path, allow_root=False, require_exists=False)
    with open(target_path, "wb") as handle:
        handle.write(content)
    return {"status": "ok"}


@app.post("/internal/files/download")
async def download_file(payload: AgentPathRequest):
    root_path = _normalize_root_path(payload.root_path)
    if _should_use_helper_root(root_path):
        response = _helper_manager().execute(root_path, "download", payload.model_dump(exclude_none=True))
        return Response(content=base64.b64decode(str(response.get("content_base64") or "").encode("utf-8")), media_type="application/octet-stream")
    target_path = _resolve_target_path(root_path, payload.path, allow_root=False)
    if not os.path.isfile(target_path):
        raise CustomException(400, "Invalid Request", "Only file downloads are supported")
    with open(target_path, "rb") as handle:
        content = handle.read()
    return Response(content=content, media_type="application/octet-stream")


def _normalize_root_path(root_path: str) -> str:
    normalized = os.path.realpath(str(root_path or "").strip())
    if not normalized or not os.path.isabs(normalized):
        raise CustomException(400, "Invalid Request", "A valid absolute root_path is required")
    if not any(_is_within_root(normalized, allowed_root) for allowed_root in _allowed_roots()):
        raise CustomException(400, "Invalid Request", "Requested root path is outside the allowed files-agent roots")
    if not os.path.exists(normalized) and not any(_is_within_root(normalized, allowed_root) for allowed_root in _docker_allowed_roots()):
        raise CustomException(404, "File Not Found", "The requested root path does not exist")
    return normalized


def _should_use_helper_root(root_path: str) -> bool:
    return not os.path.exists(root_path) and any(_is_within_root(root_path, allowed_root) for allowed_root in _docker_allowed_roots())


def _resolve_target_path(root_path: str, requested_path: str, allow_root: bool = True, require_exists: bool = True) -> str:
    normalized_path = _normalize_relative_path(requested_path)
    target_path = os.path.realpath(os.path.join(root_path, normalized_path.lstrip("/")))
    _ensure_inside_root(root_path, target_path, allow_root=allow_root)
    if require_exists and not os.path.exists(target_path):
        raise CustomException(404, "File Not Found", "The requested path does not exist")
    return target_path


def _ensure_inside_root(root_path: str, target_path: str, allow_root: bool = True) -> None:
    if not _is_within_root(target_path, root_path):
        raise CustomException(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
    if not allow_root and os.path.realpath(target_path) == os.path.realpath(root_path):
        raise CustomException(400, "Invalid Request", "The volume root is not a valid target for this operation")


def _normalize_relative_path(path_value: str) -> str:
    raw = str(path_value or "/").strip() or "/"
    normalized = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
    parts = []
    for part in normalized.parts:
        if part in {"", "/", "."}:
            continue
        if part == "..":
            raise CustomException(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
        parts.append(part)
    return "/" if not parts else "/" + "/".join(parts)


def _normalize_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CustomException(400, "Invalid Request", "Name cannot be empty")
    if "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise CustomException(400, "Invalid Request", "Name cannot include path separators or traversal tokens")
    return normalized


def _normalize_item_path(root_path: str, entry_path: str) -> str:
    relative = os.path.relpath(entry_path, root_path)
    return "/" if relative == "." else "/" + relative.replace(os.sep, "/")


def _build_metadata(
    target_path: str,
    root_path: str,
    display_name: str,
    stat_result: os.stat_result,
    *,
    include_identity_ids: bool,
) -> dict[str, Any]:
    relative = os.path.relpath(target_path, root_path)
    name = display_name if relative == "." else os.path.basename(target_path.rstrip(os.sep)) or display_name or "/"
    item_type = "directory" if os.path.isdir(target_path) else "file"
    return {
        "name": name,
        "path": "/" if relative == "." else "/" + relative.replace(os.sep, "/"),
        "item_type": item_type,
        "size": stat_result.st_size,
        "mode": stat.filemode(stat_result.st_mode),
        "owner": _lookup_owner(stat_result.st_uid, include_id=include_identity_ids),
        "group": _lookup_group(stat_result.st_gid, include_id=include_identity_ids),
        "accessed_at": _format_timestamp(stat_result.st_atime),
        "modified_at": _format_timestamp(stat_result.st_mtime),
        "created_at": _format_timestamp(stat_result.st_ctime),
        "text_editable": _infer_text_editable(name, item_type, stat_result.st_size, stat_result.st_mode),
    }


def _infer_text_editable(name: str, item_type: str, size: int, mode: int) -> bool:
    if item_type != "file" or size > TEXT_FILE_LIMIT_BYTES or not stat.S_ISREG(mode):
        return False
    # Keep volume browsing aligned with host-access file manager: allow small regular
    # files to enter the inline editor and let the read endpoint reject true binaries.
    return True


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=256)
def _lookup_owner_name(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


@lru_cache(maxsize=256)
def _lookup_group_name(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def _lookup_owner(uid: int, include_id: bool = False) -> str:
    owner = _lookup_owner_name(uid)
    return f"{owner} ({uid})" if include_id else owner


def _lookup_group(gid: int, include_id: bool = False) -> str:
    group = _lookup_group_name(gid)
    return f"{group} ({gid})" if include_id else group


def _build_permission_mode(payload: AgentUpdateAttributesRequest) -> Optional[int]:
    permission_groups = (
        payload.owner_permissions,
        payload.group_permissions,
        payload.other_permissions,
    )
    if not any(group.model_fields_set for group in permission_groups):
        return None

    def _bits(group: AgentPermissionBits) -> int:
        bits = 0
        if group.read:
            bits |= 4
        if group.write:
            bits |= 2
        if group.execute:
            bits |= 1
        return bits

    return (_bits(permission_groups[0]) << 6) | (_bits(permission_groups[1]) << 3) | _bits(permission_groups[2])


def _parse_owner_value(value: Optional[str]) -> Optional[int]:
    return _parse_identity_value(value, kind="owner")


def _parse_group_value(value: Optional[str]) -> Optional[int]:
    return _parse_identity_value(value, kind="group")


def _parse_identity_value(value: Optional[str], *, kind: str) -> Optional[int]:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith(")") and " (" in normalized:
        normalized = normalized.rsplit(" (", 1)[0].strip()
    if normalized.isdigit():
        return int(normalized)

    try:
        if kind == "owner":
            return pwd.getpwnam(normalized).pw_uid
        return grp.getgrnam(normalized).gr_gid
    except KeyError:
        raise CustomException(400, "Invalid Request", f"Unknown {kind}: {normalized}")


import subprocess


def _detect_docker_volumes_root() -> str:
    """Auto-detect the Docker volumes directory via the Docker socket or filesystem."""
    # 1) Query the Docker daemon via the mounted socket (most reliable).
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.DockerRootDir}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            root = os.path.join(result.stdout.strip(), "volumes")
            if os.path.isdir(root):
                return os.path.realpath(root)
    except Exception:
        pass

    # 2) If the Docker CLI is unavailable, probe common paths.
    candidates = [
        "/var/lib/docker/volumes",
        "/data/docker/volumes",
        "/opt/docker/volumes",
    ]
    for path in candidates:
        if os.path.isdir(path):
            return os.path.realpath(path)

    # 3) Last resort: the compose default.
    return os.path.realpath("/var/lib/docker/volumes")


@lru_cache(maxsize=1)
def _docker_allowed_roots() -> tuple[str, ...]:
    volumes_root = _detect_docker_volumes_root()
    env_override = os.getenv("WEBSOFT9_FILES_AGENT_ALLOWED_ROOTS", "")
    values = []
    for part in [volumes_root] + (env_override.split(":") if env_override else []):
        normalized = os.path.realpath(part.strip())
        if normalized and normalized not in values:
            values.append(normalized)
    return tuple(values)


@lru_cache(maxsize=1)
def _allowed_roots() -> tuple[str, ...]:
    platform_cert_path = os.getenv(
        "WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH",
        "/data/config/platform-gateway/ssl/websoft9-platform-gateway.cert",
    )

    values = list(_docker_allowed_roots())
    platform_cert_root = os.path.realpath(os.path.dirname(platform_cert_path))
    if platform_cert_root and platform_cert_root not in values:
        values.append(platform_cert_root)
    return tuple(values)


def _is_within_root(path: str, root_path: str) -> bool:
    normalized_path = os.path.realpath(path)
    normalized_root = os.path.realpath(root_path)
    return normalized_path == normalized_root or normalized_path.startswith(normalized_root + os.sep)