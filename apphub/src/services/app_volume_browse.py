from pathlib import PurePosixPath
from typing import Any, Optional

import docker

from src.core.exception import CustomException
from src.services.product_auth import ProductAuthService


TEXT_FILE_LIMIT_BYTES = 1024 * 1024
DIRECTORY_ITEM_LIMIT = 500

_LIST_DIRECTORY_SCRIPT = r'''dir="$1"
root="$2"
if [ ! -d "$root" ]; then
    exit 2
fi
cd -P -- "$root" || exit 2
root_dir="$PWD"
cd -P -- "$dir" || exit 2
case "$root_dir" in
    /) ;;
    *) case "$PWD" in "$root_dir"|"$root_dir"/*) ;; *) exit 2 ;; esac ;;
esac
if [ ! -d "$PWD" ]; then
    exit 2
fi
dir="$PWD"
printf 'W9B1\0'
metadata=$(stat -c '%A|%U|%G|%s|%X|%Y|%Z' -- "$dir") || exit 2
old_ifs=$IFS
IFS='|'
set -- $metadata
IFS=$old_ifs
[ "$#" -eq 7 ] || exit 2
printf 'R\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0' "$1" "$2" "$3" "$4" "$5" "$6" "$7"
count=0
truncated=false
for entry in "$dir"/* "$dir"/.[!.]* "$dir"/..?*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    [ -L "$entry" ] && continue
    if [ "$count" -ge "500" ]; then
        truncated=true
        break
    fi
    name=${entry##*/}
    metadata=$(stat -c '%A|%U|%G|%s|%X|%Y|%Z' -- "$entry") || continue
    old_ifs=$IFS
    IFS='|'
    set -- $metadata
    IFS=$old_ifs
    [ "$#" -eq 7 ] || continue
    if [ -d "$entry" ]; then
        printf 'D\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0' "$name" "$1" "$2" "$3" "$4" "$5" "$6" "$7"
        count=$((count + 1))
    elif [ -f "$entry" ]; then
        printf 'F\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0' "$name" "$1" "$2" "$3" "$4" "$5" "$6" "$7"
        count=$((count + 1))
    fi
done
printf 'T\0%s\0' "$truncated"
'''

_READ_TEXT_SCRIPT = r'''file="$1"
root="$2"
if [ ! -d "$root" ]; then
    exit 2
fi
cd -P -- "$root" || exit 2
root_dir="$PWD"
file_dir=${file%/*}
file_name=${file##*/}
[ "$file_dir" = "$file" ] && file_dir=.
cd -P -- "$file_dir" || exit 2
case "$root_dir" in
    /) ;;
    *) case "$PWD" in "$root_dir"|"$root_dir"/*) ;; *) exit 2 ;; esac ;;
esac
if [ ! -f "$file_name" ] || [ -L "$file_name" ]; then
    exit 2
fi
set -- $(wc -c < "$file_name")
size="$1"
case "$size" in
    ''|*[!0-9]*) exit 2 ;;
esac
if [ "$size" -gt "1048576" ]; then
    exit 3
fi
cat "$file_name"
'''


class AppVolumeBrowseService:
    def __init__(self, docker_client: Optional[Any] = None, auth_service: Optional[ProductAuthService] = None):
        self.docker_client = docker_client
        self.auth_service = auth_service or ProductAuthService()

    def list_directory(self, session_token: Optional[str], app_id: str, volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, container, mount_path = self._resolve_container_mount(app_id, volume_id)
        normalized_path = self._normalize_relative_path(relative_path)
        output = self._exec(container, _LIST_DIRECTORY_SCRIPT, self._join_container_path(mount_path, normalized_path), mount_path)
        directory, items, truncated = self._parse_directory_output(output, normalized_path)
        return {
            "volume_name": volume_name,
            "source_container": self._container_name(container),
            "current_path": normalized_path,
            "directory": directory,
            "truncated": truncated,
            "items": items,
        }

    def read_text_file(self, session_token: Optional[str], app_id: str, volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, container, mount_path = self._resolve_container_mount(app_id, volume_id)
        normalized_path = self._normalize_relative_path(relative_path, allow_root=False)
        output = self._exec(container, _READ_TEXT_SCRIPT, self._join_container_path(mount_path, normalized_path), mount_path, read_text=True)
        if b"\x00" in output:
            raise CustomException(422, "Unsupported File", "Binary files cannot be previewed in the browser")
        try:
            content = output.decode("utf-8")
        except UnicodeDecodeError:
            raise CustomException(422, "Unsupported File", "Only UTF-8 text files can be previewed in the browser")
        return {
            "volume_name": volume_name,
            "source_container": self._container_name(container),
            "path": normalized_path,
            "content": content,
        }

    def _resolve_container_mount(self, app_id: str, volume_id: str) -> tuple[str, Any, str]:
        normalized_app_id = str(app_id or "").strip()
        normalized_volume_id = str(volume_id or "").strip()
        if not normalized_app_id or not normalized_volume_id:
            raise CustomException(400, "Invalid Request", "Application ID and volume ID are required")
        try:
            volume = self._get_docker_client().volumes.get(normalized_volume_id)
        except Exception:
            raise CustomException(404, "Volume Not Found", "The requested Docker volume does not exist")
        volume_attrs = self._attrs(volume)
        labels = volume_attrs.get("Labels") or {}
        if labels.get("com.docker.compose.project") != normalized_app_id:
            raise CustomException(403, "Volume Access Denied", "The requested volume does not belong to this application")

        try:
            containers = self._get_docker_client().containers.list(filters={"status": "running"})
        except Exception as exc:
            raise CustomException(503, "Docker Unavailable", f"Failed to list application containers: {exc}")

        matches: list[tuple[str, Any, str]] = []
        for container in containers:
            attrs = self._attrs(container)
            container_labels = attrs.get("Config", {}).get("Labels", {}) or attrs.get("Labels", {}) or {}
            if container_labels.get("com.docker.compose.project") != normalized_app_id:
                continue
            mount_paths = [
                str(mount.get("Destination") or "")
                for mount in attrs.get("Mounts", []) or []
                if mount.get("Type") == "volume" and mount.get("Name") == normalized_volume_id and mount.get("Destination")
            ]
            if len(mount_paths) > 1:
                raise CustomException(422, "Unsupported Mount", "The requested volume is mounted multiple times in one application container")
            if mount_paths:
                matches.append((self._container_name(container), container, mount_paths[0]))

        if not matches:
            raise CustomException(409, "Volume Unavailable", "The application is not running or does not mount this volume")
        matches.sort(key=lambda item: item[0])
        return normalized_volume_id, matches[0][1], matches[0][2]

    def _exec(self, container: Any, script: str, target_path: str, mount_path: str, read_text: bool = False) -> bytes:
        try:
            result = container.exec_run(["/bin/sh", "-c", script, "websoft9-volume-browse", target_path, mount_path])
        except Exception as exc:
            raise CustomException(503, "Container Browse Failed", f"Failed to browse the application container: {exc}")
        exit_code = int(getattr(result, "exit_code", 1))
        output = bytes(getattr(result, "output", b"") or b"")
        if exit_code == 0:
            return output
        if exit_code == 3 and read_text:
            raise CustomException(422, "File Too Large", "Only files up to 1 MB can be previewed in the browser")
        if exit_code == 2:
            raise CustomException(404, "File Not Found", "The requested path does not exist or cannot be browsed")
        raise CustomException(422, "Container Browse Unsupported", "The application container does not support volume file browsing")

    @staticmethod
    def _parse_directory_output(output: bytes, current_path: str) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        fields = output.split(b"\x00")
        if not fields or fields[0] != b"W9B1":
            raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory response")
        if len(fields) < 9 or fields[1] != b"R":
            raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory response")
        directory = AppVolumeBrowseService._parse_metadata_record(fields[2:9], current_path, "directory")
        items: list[dict[str, Any]] = []
        truncated = False
        index = 9
        while index < len(fields):
            record_type = fields[index]
            index += 1
            if record_type == b"":
                break
            if record_type == b"T":
                if index >= len(fields):
                    raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory response")
                truncated = fields[index] == b"true"
                break
            if record_type not in {b"D", b"F"}:
                raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory record")
            if index + 6 >= len(fields):
                raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory record")
            raw_name = fields[index]
            index += 8
            try:
                name = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory record")
            path = f"/{name}" if current_path == "/" else f"{current_path}/{name}"
            items.append(AppVolumeBrowseService._parse_metadata_record(
                fields[index - 7:index], path, "directory" if record_type == b"D" else "file", name,
            ))
        return directory, items, truncated

    @staticmethod
    def _parse_metadata_record(fields: list[bytes], path: str, item_type: str, name: Optional[str] = None) -> dict[str, Any]:
        if len(fields) != 7:
            raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory record")
        raw_mode, raw_owner, raw_group, raw_size, raw_accessed_at, raw_modified_at, raw_created_at = fields
        try:
            size = int(raw_size.decode("ascii"))
            return {
                "name": name if name is not None else path.rsplit("/", 1)[-1] or "/",
                "path": path,
                "item_type": item_type,
                "size": 0 if item_type == "directory" else size,
                "mode": raw_mode.decode("utf-8"),
                "owner": raw_owner.decode("utf-8"),
                "group": raw_group.decode("utf-8"),
                "accessed_at": int(raw_accessed_at.decode("ascii")),
                "modified_at": int(raw_modified_at.decode("ascii")),
                "created_at": int(raw_created_at.decode("ascii")),
                "text_viewable": item_type == "file" and size <= TEXT_FILE_LIMIT_BYTES,
            }
        except (UnicodeDecodeError, ValueError):
            raise CustomException(500, "Container Browse Failed", "The application container returned an invalid directory record")

    def _get_docker_client(self) -> Any:
        if self.docker_client is None:
            self.docker_client = docker.from_env()
        return self.docker_client

    @staticmethod
    def _normalize_relative_path(value: str, allow_root: bool = True) -> str:
        raw = str(value or "/").strip() or "/"
        candidate = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
        parts = []
        for part in candidate.parts:
            if part in {"", "/", "."}:
                continue
            if part == "..":
                raise CustomException(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
            parts.append(part)
        normalized = "/" if not parts else "/" + "/".join(parts)
        if not allow_root and normalized == "/":
            raise CustomException(400, "Invalid Request", "The volume root is not a valid file target")
        return normalized

    @staticmethod
    def _join_container_path(mount_path: str, relative_path: str) -> str:
        root = str(PurePosixPath(mount_path))
        return root if relative_path == "/" else str(PurePosixPath(root) / relative_path.lstrip("/"))

    @staticmethod
    def _attrs(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        return dict(getattr(value, "attrs", {}) or {})

    @staticmethod
    def _container_name(container: Any) -> str:
        return str(getattr(container, "name", "") or AppVolumeBrowseService._attrs(container).get("Name") or getattr(container, "id", "unknown")).lstrip("/")