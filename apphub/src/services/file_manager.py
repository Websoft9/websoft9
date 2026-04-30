import base64
import os
import time
from pathlib import PurePosixPath
from typing import Any, Optional

import docker
import requests

from src.core.exception import CustomException
from src.services.product_auth import ProductAuthService


VOLUME_NAME_CACHE_TTL_SECONDS = 5.0
DEFAULT_FILES_AGENT_URL = "http://127.0.0.1:8091"
DOCKER_VOLUMES_ROOT_SENTINEL = "__docker_volumes_root__"
_volume_name_cache: dict[str, Any] = {"expires_at": 0.0, "names": tuple()}


class FilesAgentExecutor:
    def __init__(self, base_url: Optional[str] = None, session: Optional[requests.Session] = None):
        configured_url = base_url or os.getenv("WEBSOFT9_FILES_AGENT_URL", DEFAULT_FILES_AGENT_URL)
        self.base_url = configured_url.rstrip("/")
        self.session = session or requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
        expect_binary: bool = False,
    ) -> Any:
        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=json_payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise CustomException(503, "Files Agent Error", f"Failed to reach internal files agent: {exc}")

        if response.status_code >= 400:
            message = "Files Agent Error"
            details = response.text
            try:
                payload = response.json()
                message = payload.get("message", message)
                details = payload.get("details") or payload.get("message") or details
            except ValueError:
                pass
            status_code = response.status_code if 400 <= response.status_code < 600 else 500
            raise CustomException(status_code, message, details)

        if expect_binary:
            return response.content

        try:
            return response.json()
        except ValueError as exc:
            raise CustomException(500, "Files Agent Error", f"Invalid files-agent response: {exc}")

    def list_directory(self, root_path: str, relative_path: str, display_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/internal/files/directory",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )

    def get_metadata(self, root_path: str, relative_path: str, display_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/internal/files/metadata",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )

    def read_text_file(self, root_path: str, relative_path: str, display_name: str) -> str:
        payload = self._request(
            "POST",
            "/internal/files/read-text",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )
        return str(payload.get("content", ""))

    def write_text_file(self, root_path: str, relative_path: str, content: str, display_name: str) -> None:
        self._request(
            "PUT",
            "/internal/files/write-text",
            json_payload={"root_path": root_path, "path": relative_path, "content": content, "display_name": display_name},
        )

    def create_directory(self, root_path: str, relative_path: str, display_name: str) -> None:
        self._request(
            "POST",
            "/internal/files/create-directory",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )

    def create_empty_file(self, root_path: str, relative_path: str, display_name: str) -> None:
        self._request(
            "POST",
            "/internal/files/create-file",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )

    def rename_path(self, root_path: str, source_relative_path: str, target_relative_path: str, display_name: str) -> None:
        self._request(
            "POST",
            "/internal/files/rename",
            json_payload={
                "root_path": root_path,
                "source_path": source_relative_path,
                "target_path": target_relative_path,
                "display_name": display_name,
            },
        )

    def delete_path(self, root_path: str, relative_path: str, display_name: str) -> None:
        self._request(
            "DELETE",
            "/internal/files/path",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
        )

    def upload_file(self, root_path: str, parent_relative_path: str, file_name: str, payload: bytes, display_name: str) -> None:
        self._request(
            "POST",
            "/internal/files/upload",
            json_payload={
                "root_path": root_path,
                "parent_path": parent_relative_path,
                "file_name": file_name,
                "content_base64": base64.b64encode(payload).decode("utf-8"),
                "display_name": display_name,
            },
        )

    def download_file(self, root_path: str, relative_path: str, display_name: str) -> bytes:
        return self._request(
            "POST",
            "/internal/files/download",
            json_payload={"root_path": root_path, "path": relative_path, "display_name": display_name},
            expect_binary=True,
        )


HelperContainerExecutor = FilesAgentExecutor


class FileManagerService:
    def __init__(self, docker_client: Optional[Any] = None, helper_executor: Optional[Any] = None, auth_service: Optional[ProductAuthService] = None):
        self.docker_client = docker_client or docker.from_env()
        self.helper_executor = helper_executor or FilesAgentExecutor()
        self.auth_service = auth_service or ProductAuthService()

    def list_volumes(self, session_token: Optional[str]) -> list[dict[str, Any]]:
        self.auth_service._require_authenticated_operator(session_token)
        volumes = self._list_docker_volumes(refresh=True)
        summaries = []
        for volume in sorted(volumes, key=lambda item: self._volume_name(item).lower()):
            attrs = self._volume_attrs(volume)
            labels = attrs.get("Labels") or {}
            summaries.append(
                {
                    "volume_name": attrs.get("Name", self._volume_name(volume)),
                    "driver": attrs.get("Driver", "local"),
                    "app_id": labels.get("com.docker.compose.project"),
                    "owner": labels.get("owner"),
                }
            )
        return summaries

    def list_directory(self, session_token: Optional[str], volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        normalized_path = self._normalize_relative_path(relative_path)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        directory_payload = self.helper_executor.list_directory(root_path, normalized_path, display_name)
        metadata = directory_payload.get("metadata") or {}
        return {
            "volume_name": volume_name,
            "current_path": normalized_path,
            "metadata": {"volume_name": volume_name, **metadata},
            "items": directory_payload.get("items", []),
        }

    def read_text_file(self, session_token: Optional[str], volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        normalized_path = self._normalize_relative_path(relative_path, allow_root=False)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        content = self.helper_executor.read_text_file(root_path, normalized_path, display_name)
        return {"volume_name": volume_name, "path": normalized_path, "content": content}

    def get_metadata(self, session_token: Optional[str], volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        normalized_path = self._normalize_relative_path(relative_path)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        metadata = self.helper_executor.get_metadata(root_path, normalized_path, display_name)
        return {"volume_name": volume_name, **metadata}

    def get_root_metadata(self, session_token: Optional[str]) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        root_path = self._docker_volumes_root_path()
        metadata = self.helper_executor.get_metadata(root_path, "/", "volumes")
        return {"volume_name": "", **metadata}

    def get_root_directory(self, session_token: Optional[str]) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        root_path = self._docker_volumes_root_path()
        directory_payload = self.helper_executor.list_directory(root_path, "/", "volumes")
        metadata = directory_payload.get("metadata") or {}
        return {
            "volume_name": "",
            "current_path": "/",
            "metadata": {"volume_name": "", **metadata},
            "items": directory_payload.get("items", []),
        }

    def write_text_file(self, session_token: Optional[str], volume_id: str, relative_path: str, content: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        normalized_path = self._normalize_relative_path(relative_path, allow_root=False)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        self.helper_executor.write_text_file(root_path, normalized_path, content, display_name)
        return {"volume_name": volume_name, "path": normalized_path, "operation": "save-text"}

    def create_directory(self, session_token: Optional[str], volume_id: str, parent_path: str, name: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        target = self._join_relative_path(parent_path, name)
        self.helper_executor.create_directory(root_path, target, display_name)
        return {"volume_name": volume_name, "path": target, "operation": "create-directory"}

    def create_empty_file(self, session_token: Optional[str], volume_id: str, parent_path: str, name: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        target = self._join_relative_path(parent_path, name)
        self.helper_executor.create_empty_file(root_path, target, display_name)
        return {"volume_name": volume_name, "path": target, "operation": "create-file"}

    def rename_path(self, session_token: Optional[str], volume_id: str, source_path: str, target_name: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        normalized_source = self._normalize_relative_path(source_path, allow_root=False)
        parent = str(PurePosixPath(normalized_source).parent)
        parent = "/" if parent in {".", ""} else parent
        target_path = self._join_relative_path(parent, target_name)
        self.helper_executor.rename_path(root_path, normalized_source, target_path, display_name)
        return {"volume_name": volume_name, "path": target_path, "operation": "rename"}

    def delete_path(self, session_token: Optional[str], volume_id: str, relative_path: str) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        normalized_path = self._normalize_relative_path(relative_path)
        if normalized_path == "/" and volume_name:
            self._delete_volume_root(volume_name)
            return {"volume_name": volume_name, "path": normalized_path, "operation": "delete-volume"}
        if normalized_path == "/":
            raise CustomException(400, "Invalid Request", "The Docker volumes root cannot be deleted")
        self.helper_executor.delete_path(root_path, normalized_path, display_name)
        return {"volume_name": volume_name, "path": normalized_path, "operation": "delete"}

    def upload_file(self, session_token: Optional[str], volume_id: str, parent_path: str, file_name: str, payload: bytes) -> dict[str, Any]:
        self.auth_service._require_authenticated_operator(session_token)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        normalized_parent = self._normalize_relative_path(parent_path)
        normalized_name = self._normalize_name(file_name)
        self.helper_executor.upload_file(root_path, normalized_parent, normalized_name, payload, display_name)
        return {"volume_name": volume_name, "path": self._join_relative_path(normalized_parent, normalized_name), "operation": "upload"}

    def download_file(self, session_token: Optional[str], volume_id: str, relative_path: str) -> tuple[str, bytes]:
        self.auth_service._require_authenticated_operator(session_token)
        normalized_path = self._normalize_relative_path(relative_path, allow_root=False)
        volume_name, root_path, display_name = self._resolve_scope(volume_id)
        payload = self.helper_executor.download_file(root_path, normalized_path, display_name)
        return PurePosixPath(normalized_path).name, payload

    def _resolve_scope(self, volume_id: str) -> tuple[str, str, str]:
        normalized = str(volume_id or "").strip()
        if normalized == DOCKER_VOLUMES_ROOT_SENTINEL:
            return "", self._docker_volumes_root_path(), "volumes"

        volume_name = self._require_known_volume(normalized)
        return volume_name, self._resolve_volume_root_path(volume_name), volume_name

    def _require_known_volume(self, volume_id: str) -> str:
        normalized = str(volume_id or "").strip()
        if not normalized:
            raise CustomException(400, "Invalid Request", "Volume ID cannot be empty")
        if normalized in self._list_known_volume_names():
            return normalized
        raise CustomException(404, "Volume Not Found", "The requested Docker volume does not exist")

    def _docker_volumes_root_path(self) -> str:
        try:
            info = self.docker_client.info()
            docker_root = info.get("DockerRootDir")
            if docker_root:
                return os.path.join(str(docker_root), "volumes")
        except Exception:
            pass

        for volume in self._list_docker_volumes():
            mountpoint = self._volume_attrs(volume).get("Mountpoint")
            if mountpoint:
                return str(PurePosixPath(str(mountpoint)).parent.parent)

        raise CustomException(500, "File Operation Error", "Unable to resolve Docker volumes root path")

    def _resolve_volume_root_path(self, volume_name: str) -> str:
        volume = self._resolve_volume(volume_name)
        mountpoint = self._volume_attrs(volume).get("Mountpoint")
        if mountpoint:
            return os.path.realpath(str(mountpoint))
        return os.path.join(self._docker_volumes_root_path(), volume_name, "_data")

    def _resolve_volume(self, volume_name: str) -> Any:
        volume_manager = getattr(self.docker_client, "volumes", None)
        get_volume = getattr(volume_manager, "get", None)
        try:
            if callable(get_volume):
                return get_volume(volume_name)
            return next(item for item in volume_manager.list() if self._volume_name(item) == volume_name)
        except StopIteration:
            raise CustomException(404, "Volume Not Found", "The requested Docker volume does not exist")
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(500, "File Operation Error", f"Failed to resolve Docker volume: {exc}")

    def _delete_volume_root(self, volume_name: str) -> None:
        volume = self._resolve_volume(volume_name)
        remove_volume = getattr(volume, "remove", None)
        if not callable(remove_volume):
            raise CustomException(500, "File Operation Error", "The Docker volume cannot be removed by the current backend")
        try:
            remove_volume(force=True)
            self._invalidate_volume_name_cache()
        except Exception as exc:
            raise CustomException(500, "File Operation Error", f"Failed to remove Docker volume: {exc}")

    def _list_docker_volumes(self, refresh: bool = False) -> list[Any]:
        try:
            return list(self.docker_client.volumes.list())
        except Exception as exc:
            raise CustomException(500, "File Operation Error", f"Failed to list Docker volumes: {exc}")

    def _list_known_volume_names(self) -> set[str]:
        now = time.monotonic()
        cached_names = _volume_name_cache.get("names")
        expires_at = float(_volume_name_cache.get("expires_at", 0.0))
        if isinstance(cached_names, tuple) and now < expires_at:
            return set(cached_names)

        names = tuple(self._volume_name(volume) for volume in self._list_docker_volumes(refresh=True))
        _volume_name_cache["names"] = names
        _volume_name_cache["expires_at"] = now + VOLUME_NAME_CACHE_TTL_SECONDS
        return set(names)

    def _invalidate_volume_name_cache(self) -> None:
        _volume_name_cache["names"] = tuple()
        _volume_name_cache["expires_at"] = 0.0

    def _normalize_relative_path(self, value: Optional[str], allow_root: bool = True) -> str:
        raw = str(value or "/").strip()
        if not raw:
            raw = "/"
        normalized = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
        parts = []
        for part in normalized.parts:
            if part in {"", "/", "."}:
                continue
            if part == "..":
                raise CustomException(400, "Invalid Request", "Requested path resolves outside the allowed volume root")
            parts.append(part)
        final_path = "/" if not parts else "/" + "/".join(parts)
        if not allow_root and final_path == "/":
            raise CustomException(400, "Invalid Request", "The volume root is not a valid target for this operation")
        return final_path

    def _normalize_name(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise CustomException(400, "Invalid Request", "Name cannot be empty")
        if "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
            raise CustomException(400, "Invalid Request", "Name cannot include path separators or traversal tokens")
        return normalized

    def _join_relative_path(self, parent_path: str, name: str) -> str:
        normalized_parent = self._normalize_relative_path(parent_path)
        normalized_name = self._normalize_name(name)
        base = "" if normalized_parent == "/" else normalized_parent.rstrip("/")
        return f"{base}/{normalized_name}" if base else f"/{normalized_name}"

    def _volume_attrs(self, volume: Any) -> dict[str, Any]:
        if isinstance(volume, dict):
            return dict(volume)
        return dict(getattr(volume, "attrs", {}) or {})

    def _volume_name(self, volume: Any) -> str:
        attrs = self._volume_attrs(volume)
        return attrs.get("Name") or getattr(volume, "name", "")