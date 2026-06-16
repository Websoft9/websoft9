import hashlib
import json
import os
import shlex
import socket
import sqlite3
import stat
import sys
import threading
import time
import uuid
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from io import BytesIO
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Optional

try:
    import paramiko
except ModuleNotFoundError:
    fallback_site_packages = "/opt/certbot/lib/python3.11/site-packages"
    if fallback_site_packages not in sys.path:
        sys.path.append(fallback_site_packages)
    import paramiko

from src.core.exception import CustomException
from src.services.product_auth import ProductAuthService


HOST_ACCESS_HOST = os.getenv("WEBSOFT9_HOST_ACCESS_HOST") or os.getenv("DOCKER0_IP") or "172.17.0.1"
try:
    HOST_ACCESS_PORT = max(1, min(65535, int(os.getenv("WEBSOFT9_HOST_ACCESS_PORT", "22"))))
except ValueError:
    HOST_ACCESS_PORT = 22
TEXT_FILE_PREVIEW_LIMIT = 2 * 1024 * 1024
FILE_BROWSER_CLIENT_IDLE_TTL_SECONDS = 20
IDENTITY_SOURCE_CACHE_TTL_SECONDS = 300
TERMINAL_SESSION_IDLE_TTL_SECONDS = 300
TERMINAL_SESSION_BUFFER_LIMIT = 256 * 1024
TERMINAL_SESSION_CHUNK_LIMIT = 512


class HostAccessService:
    _lock = threading.RLock()
    _runtime_profiles: dict[str, dict[str, Any]] = {}
    _terminal_sessions: dict[str, dict[str, Any]] = {}
    _identity_label_cache: dict[str, str] = {}
    _identity_source_cache: dict[str, dict[str, Any]] = {}
    _file_browser_clients: dict[str, dict[str, Any]] = {}

    def __init__(self, data_dir: Optional[str] = None, auth_service: Optional[ProductAuthService] = None):
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_HOST_ACCESS_DATA_DIR") or "/data/config/host-access")
        self.database_file = self.data_dir / "host-access.sqlite"
        self.auth_service = auth_service or ProductAuthService()

    def get_profile(self, session_token: Optional[str]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        return self._get_profile_for_operator(operator["id"])

    def update_file_preferences(self, session_token: Optional[str], payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        preferences = self._normalize_file_preferences(payload)
        self._store_file_preferences(operator["id"], preferences)
        return dict(preferences)

    def save_profile(self, session_token: Optional[str], payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        profile = self._normalize_profile_payload(payload)
        profile = self._merge_saved_profile_auth(operator["id"], profile)
        verified_profile = self._verify_profile(profile)

        with self._lock:
            self._runtime_profiles[operator["id"]] = dict(verified_profile)
            if verified_profile.get("remember"):
                self._ensure_unique_profile_username(operator["id"], verified_profile)
                self._store_operator_profile(operator["id"], verified_profile)
                self._set_active_profile_id(operator["id"], str(verified_profile["profile_id"]))
            else:
                self._clear_active_profile_id(operator["id"])

        return self._get_profile_for_operator(operator["id"])

    def test_profile(self, session_token: Optional[str], payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        profile = self._normalize_profile_payload(payload)
        profile = self._merge_saved_profile_auth(operator["id"], profile)
        verified_profile = self._verify_profile(profile)
        return {
            "success": True,
            "message": "Host access connection test succeeded",
            "host": str(verified_profile.get("host") or HOST_ACCESS_HOST),
            "port": int(verified_profile.get("port") or HOST_ACCESS_PORT),
            "username": str(verified_profile.get("username") or ""),
        }

    def test_saved_profile(self, session_token: Optional[str], profile_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        profile = self._load_saved_profile(operator["id"], profile_id)
        if profile is None:
            raise CustomException(404, "Host Access Profile Not Found", "The requested saved login does not exist")
        verified_profile = self._verify_profile(profile)
        return {
            "success": True,
            "message": "Host access connection test succeeded",
            "host": str(verified_profile.get("host") or HOST_ACCESS_HOST),
            "port": int(verified_profile.get("port") or HOST_ACCESS_PORT),
            "username": str(verified_profile.get("username") or ""),
        }

    def clear_profile(self, session_token: Optional[str]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            self._runtime_profiles.pop(operator["id"], None)
            self._clear_active_profile_id(operator["id"])
        return self._get_profile_for_operator(operator["id"])

    def activate_saved_profile(self, session_token: Optional[str], profile_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            profile = self._load_saved_profile(operator["id"], profile_id)
            if profile is None:
                raise CustomException(404, "Host Access Profile Not Found", "The requested saved login does not exist")
            self._runtime_profiles[operator["id"]] = dict(profile)
            self._set_active_profile_id(operator["id"], profile_id)
        return self._get_profile_for_operator(operator["id"])

    def set_default_profile(self, session_token: Optional[str], profile_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        with self._lock:
            with self._db_connect() as connection:
                row = connection.execute(
                    "SELECT profile_id FROM host_profiles WHERE operator_id = ? AND profile_id = ?",
                    (operator["id"], profile_id),
                ).fetchone()
                if row is None:
                    raise CustomException(404, "Host Access Profile Not Found", "The requested saved login does not exist")
                connection.execute("UPDATE host_profiles SET is_default = 0 WHERE operator_id = ?", (operator["id"],))
                connection.execute("UPDATE host_profiles SET is_default = 1 WHERE operator_id = ? AND profile_id = ?", (operator["id"], profile_id))
                connection.commit()
        return self._get_profile_for_operator(operator["id"])

    def delete_saved_profile(self, session_token: Optional[str], profile_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        replacement_profile_id: Optional[str] = None

        with self._lock:
            with self._db_connect() as connection:
                row = connection.execute(
                    "SELECT is_default FROM host_profiles WHERE operator_id = ? AND profile_id = ?",
                    (operator["id"], profile_id),
                ).fetchone()
                if row is None:
                    raise CustomException(404, "Host Access Profile Not Found", "The requested saved login does not exist")

                connection.execute(
                    "DELETE FROM host_profiles WHERE operator_id = ? AND profile_id = ?",
                    (operator["id"], profile_id),
                )

                remaining_rows = connection.execute(
                    "SELECT profile_id, is_default, updated_at FROM host_profiles WHERE operator_id = ? ORDER BY is_default DESC, updated_at DESC",
                    (operator["id"],),
                ).fetchall()

                if remaining_rows:
                    replacement_profile_id = next((str(item["profile_id"]) for item in remaining_rows if item["is_default"]), None)
                    if replacement_profile_id is None:
                        replacement_profile_id = str(remaining_rows[0]["profile_id"])
                        connection.execute("UPDATE host_profiles SET is_default = 0 WHERE operator_id = ?", (operator["id"],))
                        connection.execute(
                            "UPDATE host_profiles SET is_default = 1 WHERE operator_id = ? AND profile_id = ?",
                            (operator["id"], replacement_profile_id),
                        )

                connection.commit()

            runtime_profile = self._runtime_profiles.get(operator["id"])
            if runtime_profile and runtime_profile.get("profile_id") == profile_id:
                self._runtime_profiles.pop(operator["id"], None)
                if replacement_profile_id:
                    replacement = self._load_saved_profile(operator["id"], replacement_profile_id)
                    if replacement is not None:
                        self._runtime_profiles[operator["id"]] = dict(replacement)

            current_active_profile_id = self._get_active_profile_id(operator["id"])
            if current_active_profile_id == profile_id:
                if replacement_profile_id:
                    self._set_active_profile_id(operator["id"], replacement_profile_id)
                else:
                    self._clear_active_profile_id(operator["id"])

        return self._get_profile_for_operator(operator["id"])

    def list_directory(self, session_token: Optional[str], path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        with self._open_sftp(profile) as sftp:
            resolved = self._resolve_directory_path(sftp, path or profile["working_directory"])
            directory_entries = sorted(sftp.listdir_attr(resolved), key=lambda item: (not stat.S_ISDIR(item.st_mode), item.filename.lower()))
            metadata_entry = sftp.stat(resolved)
            owner_labels, group_labels = self._load_identity_labels(
                sftp,
                [self._extract_stat_id(metadata_entry, "st_uid"), *[self._extract_stat_id(entry, "st_uid") for entry in directory_entries]],
                [self._extract_stat_id(metadata_entry, "st_gid"), *[self._extract_stat_id(entry, "st_gid") for entry in directory_entries]],
            )
            metadata = self._build_path_metadata(
                sftp,
                resolved,
                entry=metadata_entry,
                owner_labels=owner_labels,
                group_labels=group_labels,
            )
            items = []
            for entry in directory_entries:
                items.append(
                    self._build_file_item(
                        resolved,
                        entry,
                        owner_labels=owner_labels,
                        group_labels=group_labels,
                    )
                )
            return {"current_path": resolved, "metadata": metadata, "items": items}

    def read_text_file(self, session_token: Optional[str], path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_path = self._normalize_remote_path(path)
        with self._open_sftp(profile) as sftp:
            with sftp.open(normalized_path, "r") as handle:
                payload = handle.read(TEXT_FILE_PREVIEW_LIMIT + 1)
        if isinstance(payload, str):
            content = payload
        else:
            if len(payload) > TEXT_FILE_PREVIEW_LIMIT:
                raise CustomException(400, "File Too Large", "Only files up to 2 MB can be previewed in the browser")
            try:
                content = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CustomException(400, "Unsupported File", f"Only UTF-8 text files can be previewed: {exc}")
        return {"path": normalized_path, "content": content}

    def write_text_file(self, session_token: Optional[str], path: str, content: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_path = self._normalize_remote_path(path)
        with self._open_sftp(profile) as sftp:
            self._ensure_parent_directory_exists(sftp, normalized_path)
            try:
                with sftp.open(normalized_path, "w") as handle:
                    handle.write(content)
            except IOError as exc:
                raise CustomException(400, "Write Failed", f"Failed to save file: {exc}")
        return {"path": normalized_path, "operation": "write"}

    def create_directory(self, session_token: Optional[str], parent_path: str, name: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        with self._open_sftp(profile) as sftp:
            resolved_parent = self._resolve_directory_path(sftp, parent_path)
            target_path = self._join_remote_path(resolved_parent, name)
            try:
                sftp.mkdir(target_path)
            except IOError as exc:
                raise CustomException(400, "Create Directory Failed", f"Failed to create directory: {exc}")
        return {"path": target_path, "operation": "create-directory"}

    def create_empty_file(self, session_token: Optional[str], parent_path: str, name: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        with self._open_sftp(profile) as sftp:
            resolved_parent = self._resolve_directory_path(sftp, parent_path)
            target_path = self._join_remote_path(resolved_parent, name)
            try:
                with sftp.open(target_path, "x"):
                    pass
            except IOError:
                try:
                    existing = sftp.stat(target_path)
                except IOError as exc:
                    raise CustomException(400, "Create File Failed", f"Failed to create file: {exc}")
                if existing:
                    raise CustomException(400, "Create File Failed", "A file or directory with the same name already exists")
        return {"path": target_path, "operation": "create-file"}

    def rename_item(self, session_token: Optional[str], source_path: str, target_name: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_source = self._normalize_remote_path(source_path)
        parent_path = str(PurePosixPath(normalized_source).parent) or "/"
        target_path = self._join_remote_path(parent_path, target_name)
        if normalized_source == "/":
            raise CustomException(400, "Rename Failed", "The root directory cannot be renamed")

        with self._open_sftp(profile) as sftp:
            self._ensure_remote_exists(sftp, normalized_source)
            try:
                sftp.stat(target_path)
            except IOError:
                pass
            else:
                raise CustomException(400, "Rename Failed", "A file or directory with the same name already exists")

            try:
                sftp.rename(normalized_source, target_path)
            except IOError as exc:
                raise CustomException(400, "Rename Failed", f"Failed to rename item: {exc}")

        return {"path": target_path, "operation": "rename"}

    def delete_item(self, session_token: Optional[str], path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_path = self._normalize_remote_path(path)
        if normalized_path == "/":
            raise CustomException(400, "Delete Failed", "The root directory cannot be deleted")

        with self._open_sftp(profile) as sftp:
            entry = self._ensure_remote_exists(sftp, normalized_path)
            try:
                if stat.S_ISDIR(int(getattr(entry, "st_mode", 0) or 0)):
                    self._remove_directory_tree(sftp, normalized_path)
                else:
                    sftp.remove(normalized_path)
            except IOError as exc:
                raise CustomException(400, "Delete Failed", f"Failed to delete item: {exc}")

        return {"path": normalized_path, "operation": "delete"}

    def download_file(self, session_token: Optional[str], path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_path = self._normalize_remote_path(path)
        with self._open_sftp(profile) as sftp:
            entry = self._ensure_remote_exists(sftp, normalized_path)
            if stat.S_ISDIR(int(getattr(entry, "st_mode", 0) or 0)):
                raise CustomException(400, "Download Failed", "Directories cannot be downloaded from the terminal file browser")

            try:
                with sftp.open(normalized_path, "rb") as handle:
                    content = handle.read()
            except IOError as exc:
                raise CustomException(400, "Download Failed", f"Failed to download file: {exc}")

        return {
            "file_name": PurePosixPath(normalized_path).name or "download",
            "media_type": "application/octet-stream",
            "content": content,
        }

    def update_item_attributes(self, session_token: Optional[str], payload: dict[str, Any], profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_source = self._normalize_remote_path(payload.get("source_path"))
        target_name = str(payload.get("target_name") or "").strip() or None
        owner = str(payload.get("owner") or "").strip() or None
        group = str(payload.get("group") or "").strip() or None

        with self._open_file_client(profile) as client:
            sftp = client.open_sftp()
            try:
                entry = self._ensure_remote_exists(sftp, normalized_source)
                target_path = normalized_source

                if target_name and target_name != PurePosixPath(normalized_source).name:
                    if normalized_source == "/":
                        raise CustomException(400, "Update Attributes Failed", "The root directory cannot be renamed")
                    target_path = self._join_remote_path(str(PurePosixPath(normalized_source).parent) or "/", target_name)
                    try:
                        sftp.stat(target_path)
                    except IOError:
                        pass
                    else:
                        raise CustomException(400, "Update Attributes Failed", "A file or directory with the same name already exists")
                    try:
                        sftp.rename(normalized_source, target_path)
                    except IOError as exc:
                        raise CustomException(400, "Update Attributes Failed", f"Failed to rename item: {exc}")

                permission_mode = self._build_permission_mode(payload)
                if owner is not None or group is not None:
                    owner_spec = owner or ""
                    group_spec = group or ""
                    self._run_remote_command(
                        client,
                        f"chown {shlex.quote(f'{owner_spec}:{group_spec}' if group is not None else owner_spec)} -- {shlex.quote(target_path)}",
                        "Update Attributes Failed",
                        "Failed to update owner or group",
                    )

                if permission_mode is not None:
                    self._run_remote_command(
                        client,
                        f"chmod {permission_mode} -- {shlex.quote(target_path)}",
                        "Update Attributes Failed",
                        "Failed to update permissions",
                    )

                refreshed_entry = self._ensure_remote_exists(sftp, target_path)
                owner_labels, group_labels = self._load_identity_labels(
                    sftp,
                    [self._extract_stat_id(refreshed_entry, "st_uid")],
                    [self._extract_stat_id(refreshed_entry, "st_gid")],
                )
                metadata = self._build_path_metadata(
                    sftp,
                    target_path,
                    entry=refreshed_entry,
                    owner_labels=owner_labels,
                    group_labels=group_labels,
                )
            finally:
                sftp.close()

        return {"path": target_path, "operation": "update-attributes", "metadata": metadata}

    def copy_item(self, session_token: Optional[str], source_path: str, destination_path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_source = self._normalize_remote_path(source_path)
        if normalized_source == "/":
            raise CustomException(400, "Copy Failed", "The root directory cannot be copied")

        with self._open_file_client(profile) as client:
            sftp = client.open_sftp()
            try:
                self._ensure_remote_exists(sftp, normalized_source)
                resolved_destination = self._resolve_directory_path(sftp, destination_path)
                target_path = self._join_remote_path(resolved_destination, PurePosixPath(normalized_source).name)
                if target_path == normalized_source:
                    raise CustomException(400, "Copy Failed", "The selected item is already in this directory")
                try:
                    sftp.stat(target_path)
                except IOError:
                    pass
                else:
                    raise CustomException(400, "Copy Failed", "A file or directory with the same name already exists")

                self._run_remote_command(
                    client,
                    f"cp -a -- {shlex.quote(normalized_source)} {shlex.quote(target_path)}",
                    "Copy Failed",
                    "Failed to copy item",
                )
            finally:
                sftp.close()

        return {"path": target_path, "operation": "copy"}

    def move_item(self, session_token: Optional[str], source_path: str, destination_path: str, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        normalized_source = self._normalize_remote_path(source_path)
        if normalized_source == "/":
            raise CustomException(400, "Move Failed", "The root directory cannot be moved")

        with self._open_sftp(profile) as sftp:
            self._ensure_remote_exists(sftp, normalized_source)
            resolved_destination = self._resolve_directory_path(sftp, destination_path)
            target_path = self._join_remote_path(resolved_destination, PurePosixPath(normalized_source).name)
            if target_path == normalized_source:
                raise CustomException(400, "Move Failed", "The selected item is already in this directory")
            try:
                sftp.stat(target_path)
            except IOError:
                pass
            else:
                raise CustomException(400, "Move Failed", "A file or directory with the same name already exists")

            try:
                sftp.rename(normalized_source, target_path)
            except IOError as exc:
                raise CustomException(400, "Move Failed", f"Failed to move item: {exc}")

        return {"path": target_path, "operation": "move"}

    def upload_file(self, session_token: Optional[str], parent_path: str, file_name: str, payload: bytes, profile_id: Optional[str] = None) -> dict[str, Any]:
        profile = self.get_connection_profile(session_token, profile_id=profile_id)
        with self._open_sftp(profile) as sftp:
            resolved_parent = self._resolve_directory_path(sftp, parent_path)
            target_path = self._join_remote_path(resolved_parent, file_name)
            try:
                sftp.putfo(BytesIO(payload), target_path)
            except IOError as exc:
                raise CustomException(400, "Upload Failed", f"Failed to upload file: {exc}")
        return {"path": target_path, "operation": "upload"}

    def get_connection_profile(self, session_token: Optional[str], profile_id: Optional[str] = None) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized_profile_id = str(profile_id or '').strip()
        if normalized_profile_id:
            profile = self._load_saved_profile(operator['id'], normalized_profile_id)
            if profile is None:
                raise CustomException(400, 'Host Access Profile Not Found', 'The requested host profile is unavailable for file operations')
            return profile
        profile = self._resolve_active_profile(operator["id"])
        if profile is None:
            raise CustomException(400, "Host Access Not Configured", "Sign in to the local host before browsing files or opening a terminal")
        return profile

    def _get_profile_for_operator(self, operator_id: str) -> dict[str, Any]:
        saved_profiles = self._list_operator_profiles(operator_id)
        active_profile = self._resolve_active_profile(operator_id, saved_profiles=saved_profiles)
        default_profile_id = next((item["profile_id"] for item in saved_profiles if item.get("is_default")), None)
        file_preferences = self._load_file_preferences(operator_id)
        return self._build_profile_response(active_profile, saved_profiles, default_profile_id, file_preferences)

    def _build_profile_response(
        self,
        active_profile: Optional[dict[str, Any]],
        saved_profiles: list[dict[str, Any]],
        default_profile_id: Optional[str],
        file_preferences: dict[str, Any],
    ) -> dict[str, Any]:
        base_payload = {
            "configured": active_profile is not None,
            "remembered": bool(active_profile.get("remember", False)) if active_profile else False,
            "host": str(active_profile.get("host") or HOST_ACCESS_HOST) if active_profile else HOST_ACCESS_HOST,
            "port": int(active_profile.get("port") or HOST_ACCESS_PORT) if active_profile else HOST_ACCESS_PORT,
            "local_host_ip": HOST_ACCESS_HOST,
            "active_profile_id": active_profile.get("profile_id") if active_profile else None,
            "default_profile_id": default_profile_id,
            "saved_profiles": saved_profiles,
            "has_password": bool(active_profile.get("password")) if active_profile else False,
            "has_private_key": bool(active_profile.get("private_key")) if active_profile else False,
            "file_preferences": file_preferences,
        }
        if active_profile is None:
            return base_payload
        return {
            **base_payload,
            "auth_method": active_profile.get("auth_method"),
            "username": active_profile.get("username"),
            "working_directory": active_profile.get("working_directory"),
            "shell": active_profile.get("shell"),
        }

    def _resolve_active_profile(self, operator_id: str, saved_profiles: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
        profiles = saved_profiles if saved_profiles is not None else self._list_operator_profiles(operator_id)
        active_profile_id = self._get_active_profile_id(operator_id)
        if active_profile_id:
            profile = self._load_saved_profile(operator_id, active_profile_id)
            if profile is not None:
                self._runtime_profiles[operator_id] = dict(profile)
                return dict(profile)
            self._clear_active_profile_id(operator_id)

        runtime_profile = self._runtime_profiles.get(operator_id)
        if runtime_profile is not None:
            runtime_profile_id = str(runtime_profile.get("profile_id") or "").strip()
            if not runtime_profile.get("remember"):
                return dict(runtime_profile)

            # Remembered profiles must follow persisted state, otherwise a stale
            # worker-local runtime cache can override the user's actual active/default choice.
            if runtime_profile_id and any(item.get("profile_id") == runtime_profile_id for item in profiles):
                self._runtime_profiles.pop(operator_id, None)
            else:
                return dict(runtime_profile)

        default_profile = next((item for item in profiles if item.get("is_default")), None)
        if default_profile is None:
            return None

        profile = self._load_saved_profile(operator_id, default_profile["profile_id"])
        if profile is None:
            return None

        self._runtime_profiles[operator_id] = dict(profile)
        return dict(profile)
        return None

    def open_terminal_channel(self, session_token: Optional[str], cols: int, rows: int) -> tuple[paramiko.SSHClient, Any, dict[str, Any]]:
        profile = self.get_connection_profile(session_token)
        client = self._connect_client(profile)
        transport = client.get_transport()
        if transport is None:
            client.close()
            raise CustomException(500, "SSH Transport Error", "SSH transport is not available")
        channel = transport.open_session()
        channel.get_pty(term="xterm-256color", width=max(cols, 40), height=max(rows, 10))
        bootstrap = self._build_terminal_bootstrap(profile)
        if bootstrap:
            channel.exec_command(bootstrap)
        else:
            channel.invoke_shell()
        return client, channel, profile

    def attach_terminal_session(self, session_token: Optional[str], session_id: str, cols: int, rows: int) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized_session_id = str(session_id or '').strip()
        if not normalized_session_id:
            raise CustomException(400, 'Terminal Session Error', 'Missing terminal session identifier')

        with self._lock:
            self._cleanup_terminal_sessions_locked()
            existing = self._terminal_sessions.get(normalized_session_id)
            if existing is not None:
                if existing['operator_id'] != operator['id']:
                    raise CustomException(403, 'Terminal Session Forbidden', 'The requested terminal session belongs to a different operator')
                if self._is_terminal_session_alive_locked(existing):
                    existing['detached_at'] = None
                    existing['last_activity_at'] = time.time()
                    existing['channel'].resize_pty(width=max(cols, 40), height=max(rows, 10))
                    return {
                        'profile': dict(existing['profile']),
                        'buffer': str(existing['buffer']),
                        'cursor': int(existing['cursor']),
                        'closed': bool(existing['closed']),
                    }
                self._close_terminal_session_locked(normalized_session_id)

        client, channel, profile = self.open_terminal_channel(session_token=session_token, cols=cols, rows=rows)
        terminal_session = {
            'operator_id': operator['id'],
            'client': client,
            'channel': channel,
            'profile': dict(profile),
            'buffer': '',
            'chunks': [],
            'cursor': 0,
            'closed': False,
            'detached_at': None,
            'created_at': time.time(),
            'last_activity_at': time.time(),
            'resources_closed': False,
        }
        with self._lock:
            self._terminal_sessions[normalized_session_id] = terminal_session
            self._start_terminal_reader_locked(normalized_session_id)
        return {
            'profile': dict(profile),
            'buffer': '',
            'cursor': 0,
            'closed': False,
        }

    def read_terminal_updates(self, session_id: str, after_cursor: int) -> tuple[list[str], int, bool]:
        normalized_session_id = str(session_id or '').strip()
        with self._lock:
            session = self._terminal_sessions.get(normalized_session_id)
            if session is None:
                return [], after_cursor, True
            updates = [payload for cursor, payload in session['chunks'] if cursor > after_cursor]
            return updates, int(session['cursor']), bool(session['closed'])

    def send_terminal_input(self, session_id: str, data: str) -> None:
        session = self._get_terminal_session_for_io(session_id)
        session['channel'].send(data)
        with self._lock:
            session['last_activity_at'] = time.time()

    def resize_terminal_session(self, session_id: str, cols: int, rows: int) -> None:
        session = self._get_terminal_session_for_io(session_id)
        session['channel'].resize_pty(width=max(cols, 40), height=max(rows, 10))
        with self._lock:
            session['last_activity_at'] = time.time()

    def detach_terminal_session(self, session_id: str) -> None:
        normalized_session_id = str(session_id or '').strip()
        with self._lock:
            session = self._terminal_sessions.get(normalized_session_id)
            if session is None:
                return
            session['detached_at'] = time.time()
            session['last_activity_at'] = time.time()

    def terminate_terminal_session(self, session_token: Optional[str], session_id: str) -> None:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized_session_id = str(session_id or '').strip()
        if not normalized_session_id:
            return
        with self._lock:
            session = self._terminal_sessions.get(normalized_session_id)
            if session is None:
                return
            if session['operator_id'] != operator['id']:
                raise CustomException(403, 'Terminal Session Forbidden', 'The requested terminal session belongs to a different operator')
            self._close_terminal_session_locked(normalized_session_id)

    def _get_terminal_session_for_io(self, session_id: str) -> dict[str, Any]:
        normalized_session_id = str(session_id or '').strip()
        with self._lock:
            session = self._terminal_sessions.get(normalized_session_id)
            if session is None or not self._is_terminal_session_alive_locked(session):
                raise CustomException(410, 'Terminal Session Closed', 'The terminal session is no longer available')
            return session

    def _start_terminal_reader_locked(self, session_id: str) -> None:
        session = self._terminal_sessions[session_id]

        def _reader() -> None:
            while True:
                with self._lock:
                    current = self._terminal_sessions.get(session_id)
                    if current is not session:
                        return
                    channel = current['channel']

                try:
                    emitted = False
                    should_close = False

                    while channel.recv_ready():
                        payload = channel.recv(4096)
                        if not payload:
                            should_close = True
                            break
                        self._append_terminal_output(session_id, payload.decode('utf-8', errors='ignore'))
                        emitted = True

                    while not should_close and channel.recv_stderr_ready():
                        payload = channel.recv_stderr(4096)
                        if not payload:
                            break
                        self._append_terminal_output(session_id, payload.decode('utf-8', errors='ignore'))
                        emitted = True

                    if should_close or channel.closed or channel.exit_status_ready():
                        break

                    if not emitted:
                        time.sleep(0.02)
                except Exception:
                    break

            with self._lock:
                current = self._terminal_sessions.get(session_id)
                if current is not session:
                    return
                current['closed'] = True
                current['detached_at'] = time.time()
                self._close_terminal_resources_locked(current)

        thread = threading.Thread(target=_reader, name=f'host-access-terminal-{session_id}', daemon=True)
        session['reader'] = thread
        thread.start()

    def _append_terminal_output(self, session_id: str, payload: str) -> None:
        if not payload:
            return
        with self._lock:
            session = self._terminal_sessions.get(session_id)
            if session is None:
                return
            session['cursor'] += 1
            session['chunks'].append((session['cursor'], payload))
            if len(session['chunks']) > TERMINAL_SESSION_CHUNK_LIMIT:
                session['chunks'] = session['chunks'][-TERMINAL_SESSION_CHUNK_LIMIT:]
            session['buffer'] = f"{session['buffer']}{payload}"
            if len(session['buffer']) > TERMINAL_SESSION_BUFFER_LIMIT:
                session['buffer'] = session['buffer'][-TERMINAL_SESSION_BUFFER_LIMIT:]
            session['last_activity_at'] = time.time()

    def _is_terminal_session_alive_locked(self, session: dict[str, Any]) -> bool:
        if session.get('closed'):
            return False
        client = session.get('client')
        channel = session.get('channel')
        transport = client.get_transport() if client is not None else None
        return bool(channel is not None and not channel.closed and transport is not None and transport.is_active())

    def _close_terminal_resources_locked(self, session: dict[str, Any]) -> None:
        if session.get('resources_closed'):
            return
        channel = session.get('channel')
        client = session.get('client')
        try:
            if channel is not None:
                channel.close()
        finally:
            if client is not None:
                client.close()
        session['resources_closed'] = True

    def _close_terminal_session_locked(self, session_id: str) -> None:
        session = self._terminal_sessions.pop(session_id, None)
        if session is None:
            return
        session['closed'] = True
        self._close_terminal_resources_locked(session)

    def _cleanup_terminal_sessions_locked(self) -> None:
        now = time.time()
        stale_session_ids = [
            session_id
            for session_id, session in self._terminal_sessions.items()
            if session.get('detached_at') and now - float(session['detached_at']) > TERMINAL_SESSION_IDLE_TTL_SECONDS
        ]
        for session_id in stale_session_ids:
            self._close_terminal_session_locked(session_id)

    @contextmanager
    def _open_file_client(self, profile: dict[str, Any]) -> Iterator[paramiko.SSHClient]:
        cache_key = self._build_file_client_cache_key(profile)
        client: Optional[paramiko.SSHClient] = None
        try:
            with self._lock:
                self._cleanup_file_browser_clients_locked()
                cached_client = self._file_browser_clients.get(cache_key, {}).get("client")
                if cached_client is not None and self._is_ssh_client_active(cached_client):
                    client = cached_client
                    self._file_browser_clients[cache_key]["last_used_at"] = time.time()
                else:
                    self._close_file_browser_client_locked(cache_key)
                    client = self._connect_client(profile)
                    self._file_browser_clients[cache_key] = {
                        "client": client,
                        "sftp": None,
                        "lock": threading.RLock(),
                        "last_used_at": time.time(),
                    }

            yield client
        except Exception:
            with self._lock:
                self._close_file_browser_client_locked(cache_key)
            raise
        finally:
            if client is not None:
                with self._lock:
                    cached_entry = self._file_browser_clients.get(cache_key)
                    if cached_entry and cached_entry.get("client") is client and self._is_ssh_client_active(client):
                        cached_entry["last_used_at"] = time.time()

    @contextmanager
    def _open_sftp(self, profile: dict[str, Any]) -> Iterator[paramiko.SFTPClient]:
        """SFTP context manager with one automatic retry on transient transport failure."""
        with ExitStack() as stack:
            try:
                sftp = stack.enter_context(self._open_sftp_impl(profile))
            except CustomException as exc:
                if exc.status_code == 500:
                    # Transport died between is_active() check and open_sftp() (TOCTOU).
                    # Cache was evicted by _open_file_client's exception handler.
                    # Retry once with a fresh connection.
                    sftp = stack.enter_context(self._open_sftp_impl(profile))
                else:
                    raise
            yield sftp

    @contextmanager
    def _open_sftp_impl(self, profile: dict[str, Any]) -> Iterator[paramiko.SFTPClient]:
        cache_key = self._build_file_client_cache_key(profile)
        client: Optional[paramiko.SSHClient] = None
        sftp: Optional[paramiko.SFTPClient] = None
        cache_entry: Optional[dict[str, Any]] = None
        entry_lock: Optional[threading.RLock] = None
        should_close_on_exit = False
        try:
            with self._open_file_client(profile) as active_client:
                client = active_client
                with self._lock:
                    cache_entry = self._file_browser_clients.get(cache_key)
                    if cache_entry and cache_entry.get("client") is client:
                        cached_lock = cache_entry.get("lock")
                        if cached_lock is not None and hasattr(cached_lock, "acquire") and hasattr(cached_lock, "release"):
                            entry_lock = cached_lock
                        else:
                            entry_lock = threading.RLock()
                            cache_entry["lock"] = entry_lock
                if entry_lock is not None:
                    entry_lock.acquire()

                try:
                    if cache_entry is not None:
                        cached_sftp = cache_entry.get("sftp")
                        if cached_sftp is not None and self._is_sftp_client_active(cached_sftp):
                            sftp = cached_sftp
                        else:
                            if cached_sftp is not None:
                                try:
                                    cached_sftp.close()
                                except Exception:
                                    pass
                            sftp = client.open_sftp()
                            cache_entry["sftp"] = sftp
                    else:
                        sftp = client.open_sftp()
                        should_close_on_exit = True

                    yield sftp
                except Exception:
                    if cache_entry is not None and sftp is not None:
                        with self._lock:
                            if cache_entry.get("sftp") is sftp:
                                try:
                                    sftp.close()
                                except Exception:
                                    pass
                                cache_entry["sftp"] = None
                    raise
                finally:
                    if cache_entry is not None:
                        with self._lock:
                            current_entry = self._file_browser_clients.get(cache_key)
                            if current_entry is cache_entry:
                                current_entry["last_used_at"] = time.time()
                    if entry_lock is not None:
                        entry_lock.release()
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(500, "SFTP Error", f"Failed to open SFTP session: {exc}")
        finally:
            if should_close_on_exit and sftp is not None:
                sftp.close()

    def _build_file_client_cache_key(self, profile: dict[str, Any]) -> str:
        fingerprint = json.dumps(
            {
                "host": str(profile.get("host") or HOST_ACCESS_HOST),
                "port": int(profile.get("port") or HOST_ACCESS_PORT),
                "username": str(profile.get("username") or ""),
                "auth_method": str(profile.get("auth_method") or "password"),
                "password": str(profile.get("password") or ""),
                "private_key": str(profile.get("private_key") or ""),
                "passphrase": str(profile.get("passphrase") or ""),
            },
            sort_keys=True,
        )
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _cleanup_file_browser_clients_locked(self) -> None:
        now = time.time()
        stale_keys = [
            cache_key
            for cache_key, cache_entry in self._file_browser_clients.items()
            if now - float(cache_entry.get("last_used_at") or 0) > FILE_BROWSER_CLIENT_IDLE_TTL_SECONDS
            or not self._is_ssh_client_active(cache_entry.get("client"))
        ]
        for cache_key in stale_keys:
            self._close_file_browser_client_locked(cache_key)

    def _close_file_browser_client_locked(self, cache_key: str) -> None:
        cache_entry = self._file_browser_clients.pop(cache_key, None)
        sftp = cache_entry.get("sftp") if cache_entry else None
        client = cache_entry.get("client") if cache_entry else None
        if sftp is not None:
            try:
                sftp.close()
            except Exception:
                pass
        if client is None:
            return
        try:
            client.close()
        except Exception:
            return

    def _is_ssh_client_active(self, client: Any) -> bool:
        try:
            transport = client.get_transport() if client is not None else None
            return bool(transport is not None and transport.is_active())
        except Exception:
            return False

    def _is_sftp_client_active(self, sftp: Any) -> bool:
        try:
            channel = sftp.get_channel() if sftp is not None else None
            return bool(channel is not None and not channel.closed)
        except Exception:
            return False

    def _connect_client(self, profile: dict[str, Any]) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        target_host = str(profile.get("host") or HOST_ACCESS_HOST)
        target_port = int(profile.get("port") or HOST_ACCESS_PORT)
        connect_kwargs: dict[str, Any] = {
            "hostname": target_host,
            "port": target_port,
            "username": profile["username"],
            "timeout": 10,
            "banner_timeout": 10,
            "auth_timeout": 10,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if profile["auth_method"] == "password":
            connect_kwargs["password"] = profile.get("password") or ""
        else:
            connect_kwargs["pkey"] = self._parse_private_key(profile.get("private_key") or "", profile.get("passphrase") or None)
            if profile.get("passphrase"):
                connect_kwargs["password"] = profile["passphrase"]
        try:
            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            client.close()
            if profile["auth_method"] == "password":
                try:
                    return self._connect_client_with_password_fallback(
                        target_host,
                        target_port,
                        profile["username"],
                        profile.get("password") or "",
                    )
                except Exception as fallback_exc:
                    raise CustomException(400, "SSH Authentication Failed", f"Unable to connect to the local host over SSH ({target_host}:{target_port}): {fallback_exc}") from exc
            raise CustomException(400, "SSH Authentication Failed", f"Unable to connect to the local host over SSH ({target_host}:{target_port}): {exc}") from exc
        except CustomException:
            raise
        except Exception as exc:
            client.close()
            raise CustomException(400, "SSH Authentication Failed", f"Unable to connect to the local host over SSH ({target_host}:{target_port}): {exc}")
        return client

    def _connect_client_with_password_fallback(self, host: str, port: int, username: str, password: str) -> paramiko.SSHClient:
        sock: Optional[socket.socket] = None
        transport: Optional[paramiko.Transport] = None
        try:
            sock = socket.create_connection((host, port), timeout=10)
            transport = paramiko.Transport(sock)
            transport.banner_timeout = 10
            transport.auth_timeout = 10
            transport.start_client(timeout=10)
            transport.auth_password(username, password, fallback=True)
            if not transport.is_authenticated():
                raise paramiko.AuthenticationException("Authentication failed")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client._transport = transport
            return client
        except Exception:
            if transport is not None:
                transport.close()
            elif sock is not None:
                sock.close()
            raise

    def _verify_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        verified = dict(profile)
        client = self._connect_client(verified)
        sftp = None
        try:
            sftp = client.open_sftp()
            verified["working_directory"] = self._resolve_working_directory(
                client,
                sftp,
                verified.get("working_directory") or "",
                str(verified.get("username") or ""),
            )
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(500, "SFTP Error", f"Failed to open SFTP session: {exc}")
        finally:
            if sftp is not None:
                sftp.close()
            client.close()
        return verified

    def _resolve_working_directory(
        self,
        client: paramiko.SSHClient,
        sftp: paramiko.SFTPClient,
        path: str,
        username: str,
    ) -> str:
        if str(path or "").strip():
            return self._resolve_directory_path(sftp, path)

        candidates = self._default_working_directory_candidates(client, username)
        for candidate in candidates:
            resolved = self._resolve_directory_candidate(sftp, candidate)
            if resolved is not None:
                return resolved

        return self._resolve_directory_path(sftp, "/")

    def _default_working_directory_candidates(self, client: paramiko.SSHClient, username: str) -> list[str]:
        candidates: list[str] = []
        discovered_home = self._discover_remote_home_directory(client, username)
        for candidate in (discovered_home, "/"):
            normalized = self._normalize_remote_path(candidate) if candidate else ""
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _discover_remote_home_directory(self, client: paramiko.SSHClient, username: str) -> str:
        normalized_username = str(username or "").strip()
        if not normalized_username:
            return ""

        command = (
            f"home=$(getent passwd {shlex.quote(normalized_username)} 2>/dev/null | cut -d: -f6 | head -n 1); "
            "if [ -n \"$home\" ]; then printf '%s' \"$home\"; else printf '%s' \"$HOME\"; fi"
        )
        try:
            _, stdout, _ = client.exec_command(command, timeout=10)
            output = stdout.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

        if not output.startswith("/"):
            return ""
        return output

    def _resolve_directory_candidate(self, sftp: paramiko.SFTPClient, path: str) -> Optional[str]:
        try:
            return self._resolve_directory_path(sftp, path)
        except CustomException:
            return None

    def _resolve_directory_path(self, sftp: paramiko.SFTPClient, path: str) -> str:
        if not str(path or "").strip():
            return str(PurePosixPath(sftp.normalize(".")))
        candidate = self._normalize_remote_path(path)
        try:
            sftp.chdir(candidate)
            return str(PurePosixPath(sftp.normalize(".")))
        except IOError as exc:
            raise CustomException(400, "Invalid Directory", f"The requested working directory is not accessible: {exc}")

    def _normalize_profile_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        host = self._normalize_host_value(payload.get("host"))
        name = str(payload.get("name") or "").strip()
        description = str(payload.get("description") or "").strip()
        username = str(payload.get("username") or "").strip()
        auth_method = str(payload.get("auth_method") or "password").strip()
        if auth_method not in {"password", "key"}:
            raise CustomException(400, "Invalid Request", "Unsupported authentication method")
        working_directory = str(payload.get("working_directory") or "").strip()
        shell = str(payload.get("shell") or "").strip() or "/bin/bash"
        port = self._normalize_port_value(payload.get("port"))
        profile = {
            "profile_id": str(payload.get("profile_id") or uuid.uuid4()),
            "name": name,
            "description": description,
            "host": host,
            "port": port,
            "auth_method": auth_method,
            "username": username,
            "password": str(payload.get("password") or ""),
            "private_key": str(payload.get("private_key") or ""),
            "passphrase": str(payload.get("passphrase") or ""),
            "working_directory": self._normalize_remote_path(working_directory) if working_directory else "",
            "shell": shell,
            "remember": bool(payload.get("remember", True)),
            "is_default": bool(payload.get("is_default", False)),
        }
        if not profile["username"]:
            raise CustomException(400, "Invalid Request", "Username cannot be empty")
        # Only validate auth credentials for new profiles; for edits (profile_id provided),
        # _merge_saved_profile_auth will fill in the existing credentials if left empty.
        is_new_profile = not str(payload.get("profile_id") or "").strip()
        if is_new_profile:
            if profile["auth_method"] == "password" and not profile["password"].strip():
                raise CustomException(400, "Invalid Request", "Password cannot be empty for password authentication")
            if profile["auth_method"] == "key" and not profile["private_key"].strip():
                raise CustomException(400, "Invalid Request", "Private key cannot be empty for key authentication")
        return profile

    def _merge_saved_profile_auth(self, operator_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            return profile

        saved_profile = self._load_saved_profile(operator_id, profile_id)
        if saved_profile is None:
            return profile

        merged_profile = dict(profile)
        if merged_profile.get("auth_method") == saved_profile.get("auth_method"):
            if merged_profile["auth_method"] == "password" and not str(merged_profile.get("password") or "").strip():
                merged_profile["password"] = str(saved_profile.get("password") or "")
            if merged_profile["auth_method"] == "key" and not str(merged_profile.get("private_key") or "").strip():
                merged_profile["private_key"] = str(saved_profile.get("private_key") or "")
                merged_profile["passphrase"] = str(merged_profile.get("passphrase") or saved_profile.get("passphrase") or "")
        return merged_profile

    def _is_local_host_value(self, host: Any) -> bool:
        normalized = str(host or "").strip().casefold()
        return normalized in {
            "",
            "127.0.0.1",
            "localhost",
            "::1",
            str(HOST_ACCESS_HOST).strip().casefold(),
        }

    def _normalize_host_value(self, value: Any) -> str:
        normalized_host = str(value or "").strip()
        if not normalized_host:
            return HOST_ACCESS_HOST
        return normalized_host

    def _normalize_port_value(self, value: Any) -> int:
        if value is None or str(value).strip() == "":
            return HOST_ACCESS_PORT
        try:
            port = int(str(value).strip())
        except ValueError as exc:
            raise CustomException(400, "Invalid Request", f"Port must be an integer: {exc}")
        if port < 1 or port > 65535:
            raise CustomException(400, "Invalid Request", "Port must be between 1 and 65535")
        return port

    def _normalize_remote_path(self, path: Optional[str]) -> str:
        raw = str(path or "").strip()
        if not raw:
            raw = "/"
        if not raw.startswith("/"):
            raw = f"/{raw}"
        return str(PurePosixPath(raw))

    def _join_remote_path(self, parent_path: str, name: str) -> str:
        normalized_name = str(name or '').strip()
        if not normalized_name or '/' in normalized_name or normalized_name in {'.', '..'}:
            raise CustomException(400, 'Invalid Request', 'Name must be a single path segment')
        return str(PurePosixPath(parent_path) / normalized_name)

    def _ensure_parent_directory_exists(self, sftp: paramiko.SFTPClient, path: str) -> None:
        parent_path = str(PurePosixPath(path).parent)
        self._resolve_directory_path(sftp, parent_path)

    def _parse_private_key(self, private_key: str, passphrase: Optional[str]) -> paramiko.PKey:
        errors = []
        for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                return key_class.from_private_key(StringIO(private_key), password=passphrase)
            except Exception as exc:
                errors.append(str(exc))
        raise CustomException(400, "Invalid Private Key", "; ".join(errors[:1]) or "Unable to parse private key")

    def _build_terminal_bootstrap(self, profile: dict[str, Any]) -> str:
        directory = shlex.quote(profile["working_directory"])
        shell = str(profile.get("shell") or "").strip()
        if shell:
            return f"cd {directory} && exec {shlex.quote(shell)} -l"
        return f"cd {directory}"

    def _build_file_item(
        self,
        parent_path: str,
        entry: Any,
        created_at: Optional[str] = None,
        owner_labels: Optional[dict[int, str]] = None,
        group_labels: Optional[dict[int, str]] = None,
    ) -> dict[str, Any]:
        item_path = str(PurePosixPath(parent_path) / entry.filename)
        is_directory = stat.S_ISDIR(entry.st_mode)
        owner_id = self._extract_stat_id(entry, "st_uid")
        group_id = self._extract_stat_id(entry, "st_gid")
        return {
            "name": entry.filename,
            "path": item_path,
            "item_type": "directory" if is_directory else "file",
            "size": int(getattr(entry, "st_size", 0) or 0),
            "mode": stat.filemode(int(getattr(entry, "st_mode", 0) or 0)),
            "owner": self._resolve_identity_label(owner_id, owner_labels),
            "group": self._resolve_identity_label(group_id, group_labels),
            "accessed_at": self._format_timestamp(getattr(entry, "st_atime", None)),
            "modified_at": self._format_timestamp(getattr(entry, "st_mtime", None)),
            "created_at": created_at or self._format_timestamp(getattr(entry, "st_ctime", None)),
            "text_editable": (not is_directory) and int(getattr(entry, "st_size", 0) or 0) <= TEXT_FILE_PREVIEW_LIMIT,
        }

    def _build_path_metadata(
        self,
        sftp: paramiko.SFTPClient,
        path: str,
        entry: Any | None = None,
        created_at: Optional[str] = None,
        owner_labels: Optional[dict[int, str]] = None,
        group_labels: Optional[dict[int, str]] = None,
    ) -> dict[str, Any]:
        if entry is None:
            try:
                entry = sftp.stat(path)
            except IOError as exc:
                raise CustomException(400, "Invalid Directory", f"The requested working directory is not accessible: {exc}")

        normalized_path = self._normalize_remote_path(path)
        is_directory = stat.S_ISDIR(int(getattr(entry, "st_mode", 0) or 0))
        name = PurePosixPath(normalized_path).name or normalized_path
        owner_id = self._extract_stat_id(entry, "st_uid")
        group_id = self._extract_stat_id(entry, "st_gid")
        return {
            "name": name,
            "path": normalized_path,
            "item_type": "directory" if is_directory else "file",
            "size": int(getattr(entry, "st_size", 0) or 0),
            "mode": stat.filemode(int(getattr(entry, "st_mode", 0) or 0)),
            "owner": self._resolve_identity_label(owner_id, owner_labels),
            "group": self._resolve_identity_label(group_id, group_labels),
            "accessed_at": self._format_timestamp(getattr(entry, "st_atime", None)),
            "modified_at": self._format_timestamp(getattr(entry, "st_mtime", None)),
            "created_at": created_at or self._format_timestamp(getattr(entry, "st_ctime", None)),
            "text_editable": False,
        }

    def _extract_stat_id(self, entry: Any, key: str) -> Optional[int]:
        try:
            return int(getattr(entry, key, None))
        except Exception:
            return None

    def _resolve_identity_label(self, identity_id: Optional[int], labels: Optional[dict[int, str]]) -> Optional[str]:
        if identity_id is None:
            return None
        identity_value = str(identity_id)
        if labels and identity_id in labels:
            label = str(labels[identity_id] or "").strip()
            if label and label != identity_value:
                return f"{label}({identity_value})"
        return identity_value

    def _load_identity_labels(self, sftp: paramiko.SFTPClient, owner_ids: list[Optional[int]], group_ids: list[Optional[int]]) -> tuple[dict[int, str], dict[int, str]]:
        normalized_owner_ids = [identity_id for identity_id in dict.fromkeys(owner_ids) if identity_id is not None]
        normalized_group_ids = [identity_id for identity_id in dict.fromkeys(group_ids) if identity_id is not None]
        return (
            self._load_identity_lookup(sftp, normalized_owner_ids, "passwd"),
            self._load_identity_lookup(sftp, normalized_group_ids, "group"),
        )

    def _load_identity_lookup(self, sftp: paramiko.SFTPClient, identity_ids: list[int], source: str) -> dict[int, str]:
        if not identity_ids:
            return {}
        cache_prefix = f"{source}:"
        cached: dict[int, str] = {}
        missing_ids: list[int] = []
        for identity_id in identity_ids:
            cache_key = f"{cache_prefix}{identity_id}"
            cached_label = self._identity_label_cache.get(cache_key)
            if cached_label is None:
                missing_ids.append(identity_id)
                continue
            cached[identity_id] = cached_label
        if not missing_ids:
            return cached
        labels = self._load_identity_source_labels(sftp, source)
        resolved = {identity_id: labels.get(identity_id, str(identity_id)) for identity_id in missing_ids}
        for identity_id, label in resolved.items():
            self._identity_label_cache[f"{cache_prefix}{identity_id}"] = label
        return {**cached, **resolved}

    def _load_identity_source_labels(self, sftp: paramiko.SFTPClient, source: str) -> dict[int, str]:
        now = time.time()
        cache_prefix = f"{source}:"
        cached_entry = self._identity_source_cache.get(source)
        if cached_entry and now - float(cached_entry.get("loaded_at") or 0) <= IDENTITY_SOURCE_CACHE_TTL_SECONDS:
            return dict(cached_entry.get("labels") or {})

        source_path = "/etc/passwd" if source == "passwd" else "/etc/group"
        labels: dict[int, str] = {}
        try:
            with sftp.open(source_path, "r") as handle:
                payload = handle.read()
        except Exception:
            payload = b""

        if isinstance(payload, bytes):
            text = payload.decode("utf-8", errors="ignore")
        else:
            text = str(payload)

        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            segments = line.split(":")
            if len(segments) <= 2:
                continue
            raw_name = segments[0].strip()
            raw_id = segments[2].strip()
            if not raw_name or not raw_id:
                continue
            try:
                labels[int(raw_id)] = raw_name
            except Exception:
                continue

        for identity_id, label in labels.items():
            self._identity_label_cache[f"{cache_prefix}{identity_id}"] = label
        self._identity_source_cache[source] = {"labels": dict(labels), "loaded_at": now}
        return labels

    def _build_permission_mode(self, payload: dict[str, Any]) -> Optional[str]:
        def value_for(key: str) -> int:
            bits = payload.get(key) or {}
            return (4 if bool(bits.get("read")) else 0) + (2 if bool(bits.get("write")) else 0) + (1 if bool(bits.get("execute")) else 0)

        owner_bits = value_for("owner_permissions")
        group_bits = value_for("group_permissions")
        other_bits = value_for("other_permissions")
        return f"{owner_bits}{group_bits}{other_bits}"

    def _run_remote_command(self, client: paramiko.SSHClient, command: str, title: str, prefix: str) -> None:
        try:
            _, stdout, stderr = client.exec_command(command, timeout=15)
            exit_code = stdout.channel.recv_exit_status()
            error_text = stderr.read().decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            raise CustomException(400, title, f"{prefix}: {exc}")
        if exit_code != 0:
            raise CustomException(400, title, f"{prefix}: {error_text or f'Exit code {exit_code}'}")

    def _normalize_file_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        view_mode = str(payload.get("view_mode") or "list").strip().lower()
        if view_mode not in {"list", "grid"}:
            view_mode = "list"
        return {
            "view_mode": view_mode,
            "show_hidden_files": bool(payload.get("show_hidden_files", False)),
        }

    def _default_file_preferences(self) -> dict[str, Any]:
        return {"view_mode": "list", "show_hidden_files": False}

    def _load_file_preferences(self, operator_id: str) -> dict[str, Any]:
        self._ensure_storage()
        with self._db_connect() as connection:
            row = connection.execute(
                "SELECT payload FROM host_file_preferences WHERE operator_id = ?",
                (operator_id,),
            ).fetchone()
        if row is None:
            return self._default_file_preferences()
        try:
            payload = json.loads(str(row["payload"] or "{}"))
        except Exception:
            return self._default_file_preferences()
        return self._normalize_file_preferences(payload)

    def _store_file_preferences(self, operator_id: str, preferences: dict[str, Any]) -> None:
        self._ensure_storage()
        normalized = self._normalize_file_preferences(preferences)
        with self._lock:
            with self._db_connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO host_file_preferences (operator_id, payload, updated_at) VALUES (?, ?, ?)",
                    (operator_id, json.dumps(normalized), datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()

    def _format_timestamp(self, value: Optional[float]) -> Optional[str]:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except Exception:
            return None

    def _list_operator_profiles(self, operator_id: str) -> list[dict[str, Any]]:
        self._ensure_storage()
        with self._db_connect() as connection:
            rows = connection.execute(
                "SELECT profile_id, payload, updated_at, is_default FROM host_profiles WHERE operator_id = ? ORDER BY is_default DESC, updated_at DESC",
                (operator_id,),
            ).fetchall()

        profiles: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(json.loads(str(row["payload"])))
            profiles.append(
                {
                    "profile_id": str(row["profile_id"]),
                    "name": str(payload.get("name") or ""),
                    "description": str(payload.get("description") or ""),
                    "host": str(payload.get("host") or HOST_ACCESS_HOST),
                    "username": str(payload.get("username") or ""),
                    "auth_method": str(payload.get("auth_method") or "password"),
                    "port": int(payload.get("port") or HOST_ACCESS_PORT),
                    "shell": str(payload.get("shell") or "/bin/bash"),
                    "is_default": bool(row["is_default"]),
                    "is_local": self._is_local_host_value(payload.get("host")),
                    "updated_at": str(row["updated_at"] or "") or None,
                    "has_password": bool(payload.get("password")),
                    "has_private_key": bool(payload.get("private_key")),
                }
            )

        if len(profiles) == 1 and not profiles[0]["is_default"]:
            self._mark_default_profile(operator_id, profiles[0]["profile_id"])
            profiles[0]["is_default"] = True

        return profiles

    def _load_saved_profile(self, operator_id: str, profile_id: str) -> Optional[dict[str, Any]]:
        self._ensure_storage()
        with self._db_connect() as connection:
            row = connection.execute(
                "SELECT payload, is_default FROM host_profiles WHERE operator_id = ? AND profile_id = ?",
                (operator_id, profile_id),
            ).fetchone()
        if row is None:
            return None
        payload = dict(json.loads(str(row["payload"])))
        payload["profile_id"] = profile_id
        payload["is_default"] = bool(row["is_default"])
        payload["remember"] = True
        if self._needs_working_directory_refresh(payload):
            refreshed_payload = dict(payload)
            refreshed_payload["working_directory"] = ""
            payload = self._verify_profile(refreshed_payload)
            payload["profile_id"] = profile_id
            payload["is_default"] = bool(row["is_default"])
            payload["remember"] = True
            self._store_operator_profile(operator_id, payload)
        return payload

    def _needs_working_directory_refresh(self, profile: dict[str, Any]) -> bool:
        username = str(profile.get("username") or "").strip()
        working_directory = str(profile.get("working_directory") or "").strip()
        if not working_directory:
            return True
        return username not in {"", "root"} and working_directory == "/root"

    def _store_operator_profile(self, operator_id: str, profile: dict[str, Any]) -> None:
        self._ensure_storage()
        payload = json.dumps(profile, ensure_ascii=True)
        with self._db_connect() as connection:
            if profile.get("is_default"):
                connection.execute("UPDATE host_profiles SET is_default = 0 WHERE operator_id = ?", (operator_id,))
            connection.execute(
                "INSERT OR REPLACE INTO host_profiles (profile_id, operator_id, payload, updated_at, is_default) VALUES (?, ?, ?, ?, ?)",
                (
                    str(profile["profile_id"]),
                    operator_id,
                    payload,
                    datetime.now(timezone.utc).isoformat(),
                    1 if profile.get("is_default") else 0,
                ),
            )
            connection.commit()

    def _ensure_remote_exists(self, sftp: paramiko.SFTPClient, path: str) -> Any:
        try:
            return sftp.stat(path)
        except IOError as exc:
            raise CustomException(400, "Invalid Path", f"The requested path does not exist: {exc}")

    def _remove_directory_tree(self, sftp: paramiko.SFTPClient, path: str) -> None:
        for entry in sftp.listdir_attr(path):
            child_path = self._join_remote_path(path, entry.filename)
            if stat.S_ISDIR(int(getattr(entry, "st_mode", 0) or 0)):
                self._remove_directory_tree(sftp, child_path)
            else:
                sftp.remove(child_path)
        sftp.rmdir(path)

    def _ensure_unique_profile_username(self, operator_id: str, profile: dict[str, Any]) -> None:
        self._ensure_storage()
        normalized_host = str(profile.get("host") or "").strip().casefold()
        normalized_username = str(profile.get("username") or "").strip().casefold()
        current_profile_id = str(profile.get("profile_id") or "").strip()
        if not normalized_host or not normalized_username:
            return

        with self._db_connect() as connection:
            rows = connection.execute(
                "SELECT profile_id, payload FROM host_profiles WHERE operator_id = ?",
                (operator_id,),
            ).fetchall()

        for row in rows:
            if str(row["profile_id"]) == current_profile_id:
                continue
            payload = dict(json.loads(str(row["payload"])))
            payload_host = str(payload.get("host") or "").strip().casefold()
            payload_username = str(payload.get("username") or "").strip().casefold()
            if payload_host == normalized_host and payload_username == normalized_username:
                raise CustomException(400, "Duplicate Host Access Profile", "A saved connection with this host and username already exists")

    def _mark_default_profile(self, operator_id: str, profile_id: str) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute("UPDATE host_profiles SET is_default = 0 WHERE operator_id = ?", (operator_id,))
            connection.execute("UPDATE host_profiles SET is_default = 1 WHERE operator_id = ? AND profile_id = ?", (operator_id, profile_id))
            connection.commit()

    def _ensure_storage(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._db_connect() as connection:
            self._initialize_schema(connection)

    def _get_active_profile_id(self, operator_id: str) -> Optional[str]:
        self._ensure_storage()
        with self._db_connect() as connection:
            row = connection.execute(
                "SELECT active_profile_id FROM host_profile_state WHERE operator_id = ?",
                (operator_id,),
            ).fetchone()
        if row is None:
            return None
        active_profile_id = str(row["active_profile_id"] or "").strip()
        return active_profile_id or None

    def _set_active_profile_id(self, operator_id: str, profile_id: str) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO host_profile_state (operator_id, active_profile_id, updated_at) VALUES (?, ?, ?)",
                (operator_id, profile_id, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()

    def _clear_active_profile_id(self, operator_id: str) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute("DELETE FROM host_profile_state WHERE operator_id = ?", (operator_id,))
            connection.commit()

    def _db_connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(host_profiles)").fetchall()
        }
        if existing_columns and "profile_id" not in existing_columns:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS host_profiles_v2 (
                    profile_id TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            legacy_rows = connection.execute("SELECT operator_id, payload, updated_at FROM host_profiles").fetchall()
            for operator_id, payload, updated_at in legacy_rows:
                profile_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT OR REPLACE INTO host_profiles_v2 (profile_id, operator_id, payload, updated_at, is_default) VALUES (?, ?, ?, ?, ?)",
                    (profile_id, operator_id, payload, updated_at, 1),
                )
            connection.execute("DROP TABLE host_profiles")
            connection.execute("ALTER TABLE host_profiles_v2 RENAME TO host_profiles")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS host_profiles (
                profile_id TEXT PRIMARY KEY,
                operator_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS host_profile_state (
                operator_id TEXT PRIMARY KEY,
                active_profile_id TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS host_file_preferences (
                operator_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_host_profiles_operator_id ON host_profiles (operator_id)")
        connection.commit()
