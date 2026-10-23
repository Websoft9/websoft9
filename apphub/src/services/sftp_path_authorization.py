"""Path resolution, ACL authorization and session bookkeeping for app SFTP.

The platform owns a single dedicated host account (``websoft9-sftp``). Access
to one application directory is granted per session with a POSIX ACL and
restored from a snapshot when the session ends.
"""

import hashlib
import json
import logging
import os
import posixpath
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import docker

from src.core.exception import CustomException

logger = logging.getLogger(__name__)

ACCOUNT_NAME = "websoft9-sftp"
PLATFORM_ACCOUNT_PROFILE_ID = "platform-sftp"
SESSION_TTL_SECONDS = 1800

DENY_PREFIXES = (
    "/etc",
    "/root",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/var/run",
    "/var/lib/docker",
    "/var/lib/kubelet",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bind_volume_id(source: str) -> str:
    digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()
    return f"bind:{digest[:16]}"


def split_volume_id(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    if raw.startswith("volume:"):
        return "volume", raw[len("volume:"):]
    if raw.startswith("bind:"):
        return "bind", raw[len("bind:"):]
    return "volume", raw


def is_docker_volume_data(path: str) -> bool:
    return bool(re.match(r"^/var/lib/docker/volumes/[^/]+/_data$", posixpath.normpath(path)))


def rejected_path(path: str) -> bool:
    normalized = posixpath.normpath(path)
    if normalized in ("", "/"):
        return True
    if is_docker_volume_data(normalized):
        return False
    for prefix in DENY_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data").rstrip("/")
    for internal in (f"{data_root}/config", f"{data_root}/upgrade", f"{data_root}/repository"):
        if normalized == internal or normalized.startswith(internal + "/"):
            return True
    return False


class AppVolumeResolver:
    """Resolve an application volume identifier to its host source directory."""

    def __init__(self, docker_client: Any = None, docker_client_factory=None):
        self._docker_client = docker_client
        self._docker_client_factory = docker_client_factory

    def _client(self) -> Any:
        if self._docker_client_factory is not None:
            return self._docker_client_factory()
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def resolve(self, app_id: str, volume_id: str) -> dict[str, Any]:
        normalized_app_id = str(app_id or "").strip()
        normalized_volume_id = str(volume_id or "").strip()
        if not normalized_app_id or not normalized_volume_id:
            raise CustomException(400, "Invalid Request", "Application ID and volume ID are required")
        kind, identifier = split_volume_id(normalized_volume_id)
        if not identifier:
            raise CustomException(400, "Invalid Request", "Volume ID is required")

        try:
            containers = self._client().containers.list(filters={"label": f"com.docker.compose.project={normalized_app_id}"})
        except docker.errors.DockerException as exc:
            raise CustomException(503, "Docker Unavailable", f"Unable to list application containers: {exc}") from exc
        running = [container for container in containers if container.status == "running"] or containers
        if not running:
            raise CustomException(409, "SFTP Container Not Running", "The application is not running or does not expose any container")

        matches: list[dict[str, Any]] = []
        for container in running:
            attributes = container.attrs or {}
            user = str((attributes.get("Config") or {}).get("User") or "").strip()
            for mount in attributes.get("Mounts") or []:
                if kind == "volume":
                    if mount.get("Type") != "volume" or mount.get("Name") != identifier:
                        continue
                    source = str(mount.get("Source") or "")
                    volume = None
                    try:
                        volume = self._client().volumes.get(identifier)
                    except Exception:
                        volume = None
                    if volume is not None:
                        labels = (volume.attrs or {}).get("Labels") or {}
                        if labels.get("com.docker.compose.project") != normalized_app_id:
                            raise CustomException(403, "Volume Access Denied", "The volume does not belong to this application")
                        options = (volume.attrs or {}).get("Options") or {}
                        source = str((volume.attrs or {}).get("Mountpoint") or source)
                        if (volume.attrs or {}).get("Driver") not in (None, "local") or source.startswith("http"):
                            raise CustomException(422, "Unsupported Volume", "Application SFTP requires a local Docker volume")
                        if options and not options.get("device") and not options.get("o") and not options.get("type"):
                            raise CustomException(422, "Unsupported Volume", "Application SFTP does not support this volume driver")
                else:
                    if mount.get("Type") != "bind":
                        continue
                    source = str(mount.get("Source") or "")
                    if bind_volume_id(source).split(":", 1)[1] != identifier:
                        continue
                matches.append({
                    "source_path": source,
                    "destination": str(mount.get("Destination") or ""),
                    "container_name": str(container.name),
                    "container_user": user,
                    "container": container,
                    "volume_kind": kind,
                    "volume_identifier": identifier,
                })

        if not matches:
            raise CustomException(404, "Volume Not Found", "The requested volume is not mounted by this application")
        sources = {item["source_path"] for item in matches}
        if len(sources) > 1:
            raise CustomException(422, "Unsupported Mount", "The requested volume resolves to multiple host directories")
        chosen = sorted(matches, key=lambda item: item["container_name"])[0]
        source_path = posixpath.normpath(chosen["source_path"])
        if not source_path.startswith("/"):
            raise CustomException(422, "Unsupported Volume", "The application volume does not resolve to a host directory")
        if rejected_path(source_path):
            raise CustomException(422, "SFTP Path Unsupported", "This application directory cannot be opened through SFTP")
        chosen["source_path"] = source_path
        identity = self._resolve_container_identity(chosen["container_user"])
        if identity[0] <= 0:
            identity = self._probe_container_identity(chosen.get("container"), chosen.get("destination"))
            if identity[0] <= 0:
                identity = self._probe_directory_owner(source_path)
        chosen["container_uid"], chosen["container_gid"] = identity
        chosen.pop("container", None)
        return chosen

    @staticmethod
    def _probe_container_identity(container: Any, destination: str) -> tuple[int, int]:
        """Resolve the application identity inside the container when the image declares none.

        Most images (WordPress, Nextcloud, ...) start as root and drop privileges in
        their entrypoint, so ``Config.User`` stays empty. The owner of the mounted
        directory is the identity the application really runs as.
        """
        if container is None or not destination:
            return 0, 0
        try:
            result = container.exec_run(["stat", "-c", "%u:%g", destination], user="0")
        except Exception:
            return 0, 0
        if int(getattr(result, "exit_code", 1) or 0) != 0:
            return 0, 0
        output = (getattr(result, "output", b"") or b"").decode("utf-8", "ignore").strip()
        parts = output.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return 0, 0
        uid, gid = int(parts[0]), int(parts[1])
        return (uid, gid) if uid > 0 else (0, 0)

    @staticmethod
    def _probe_directory_owner(source_path: str) -> tuple[int, int]:
        """Last resort: read the host-side directory owner when the container cannot be probed."""
        try:
            attributes = os.stat(source_path)
        except OSError:
            return 0, 0
        return (attributes.st_uid, attributes.st_gid) if attributes.st_uid > 0 else (0, 0)

    @staticmethod
    def _resolve_container_identity(raw_user: str) -> tuple[int, int]:
        raw = str(raw_user or "").strip()
        if not raw:
            return 0, 0
        parts = raw.split(":", 1)
        try:
            uid = int(parts[0])
            gid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else uid
            return uid, gid
        except ValueError:
            return 0, 0


class SftpAclAuthorizer:
    """Run the host ACL helper inside a short-lived privileged container."""

    def __init__(self, data_dir: Optional[Path] = None, docker_client: Any = None, docker_client_factory=None):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or f"{data_root}/config/host-access")
        self.data_root = str(data_root)
        self._docker_client = docker_client
        self._docker_client_factory = docker_client_factory

    def _client(self) -> Any:
        if self._docker_client_factory is not None:
            return self._docker_client_factory()
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def _run(self, arguments: list[str], timeout: int = 120) -> dict[str, Any]:
        script = Path(__file__).with_name("app_sftp_acl.py").read_text()
        command = ["-c", script, *arguments]
        container = None
        client = None
        try:
            client = self._client()
            image = client.containers.get(os.environ["HOSTNAME"]).image.id
            container = client.containers.run(
                image=image,
                entrypoint=["python3"],
                command=command,
                volumes={"/": {"bind": "/host", "mode": "rslave"}},
                privileged=True,
                user="0",
                detach=True,
                labels={"owner": "websoft9", "websoft9.operation": "app-sftp-acl"},
            )
            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace").strip()
            errors = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace").strip()
            if int(result.get("StatusCode", 1)) != 0:
                detail = errors or logs or "The host ACL helper failed"
                raise CustomException(409, "SFTP Authorization Failed", detail)
            try:
                return json.loads(logs.splitlines()[-1]) if logs else {}
            except (ValueError, IndexError) as exc:
                raise CustomException(500, "SFTP Authorization Failed", "The host ACL helper returned an invalid response") from exc
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(500, "SFTP Authorization Failed", f"Unable to prepare host ACL authorization: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    def apply(self, session_id: str, path: str, container_uid: int, recursive: bool = True) -> dict[str, Any]:
        arguments = ["apply", self.data_root, session_id, path, ACCOUNT_NAME, str(int(container_uid))]
        if recursive:
            arguments.append("--recursive")
        return self._run(arguments)

    def grant(self, session_id: str, path: str) -> dict[str, Any]:
        return self._run(["grant", self.data_root, session_id, path])

    def release(self, session_id: str) -> dict[str, Any]:
        return self._run(["release", self.data_root, session_id], timeout=90)


class SftpAuthorizationStore:
    def __init__(self, data_dir: Optional[Path] = None):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or f"{data_root}/config/host-access")
        self.database_file = self.data_dir / "sftp-authorization.sqlite"
        self._lock = threading.RLock()

    @contextmanager
    def _connect(self):
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sftp_sessions (
                    session_id TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    volume_id TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    container_uid INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    released_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sftp_grants (
                    grant_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    volume_id TEXT NOT NULL,
                    container_uid INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(app_id, root_path)
                )
                """
            )
            connection.commit()
            yield connection
        finally:
            connection.close()

    def session(self, session_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM sftp_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def find_grant(self, app_id: str, root_path: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sftp_grants WHERE app_id = ? AND root_path = ?",
                (app_id, root_path),
            ).fetchone()
        return dict(row) if row else None

    def create_grant(self, *, grant_id: str, app_id: str, root_path: str, target_kind: str, volume_id: str, container_uid: int) -> None:
        with self._lock, self._connect() as connection:
            now = utc_now()
            connection.execute(
                "INSERT OR REPLACE INTO sftp_grants (grant_id, app_id, root_path, target_kind, volume_id, container_uid, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (grant_id, app_id, root_path, target_kind, volume_id, int(container_uid), now, now),
            )
            connection.commit()

    def grants_for_app(self, app_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM sftp_grants WHERE app_id = ?", (app_id,)).fetchall()
        return [dict(row) for row in rows]

    def all_grants(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM sftp_grants").fetchall()
        return [dict(row) for row in rows]

    def delete_grant(self, grant_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM sftp_grants WHERE grant_id = ?", (grant_id,))
            connection.commit()

    def create(self, *, session_id: str, operator_id: str, app_id: str, volume_id: str, root_path: str, container_uid: int) -> None:
        with self._lock, self._connect() as connection:
            now = utc_now()
            connection.execute(
                "INSERT OR REPLACE INTO sftp_sessions (session_id, operator_id, app_id, volume_id, root_path, container_uid, state, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (session_id, operator_id, app_id, volume_id, root_path, int(container_uid), now, now),
            )
            connection.commit()

    def touch(self, session_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE sftp_sessions SET last_seen_at = ? WHERE session_id = ?", (utc_now(), session_id))
            connection.commit()

    def release(self, session_id: str, state: str = "released") -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE sftp_sessions SET state = ?, released_at = ? WHERE session_id = ? AND state = 'active'",
                (state, utc_now(), session_id),
            )
            connection.commit()

    def active_sessions(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM sftp_sessions WHERE state = 'active'").fetchall()
        return [dict(row) for row in rows]


class AppSftpAuthority:
    """Facade used by :class:`AppSftpService`."""

    def __init__(self, data_dir: Optional[Path] = None, docker_client: Any = None, docker_client_factory=None):
        self.resolver = AppVolumeResolver(docker_client=docker_client, docker_client_factory=docker_client_factory)
        self.authorizer = SftpAclAuthorizer(data_dir=data_dir, docker_client=docker_client, docker_client_factory=docker_client_factory)
        self.store = SftpAuthorizationStore(data_dir=data_dir)

    def new_session_id(self) -> str:
        return uuid.uuid4().hex

    def resolve(self, app_id: str, volume_id: str) -> dict[str, Any]:
        return self.resolver.resolve(app_id, volume_id)

    def authorize(self, *, session_id: str, operator_id: str, app_id: str, volume_id: str, target: dict[str, Any]) -> dict[str, Any]:
        root = target["source_path"]
        container_uid = int(target.get("container_uid") or 0)
        grant = self.store.find_grant(app_id, root)
        if grant is None:
            # First access to this application directory: authorize it once and
            # keep the grant until the application is removed.
            grant_id = uuid.uuid4().hex
            result = self.authorizer.apply(grant_id, root, container_uid, recursive=False)
            self.store.create_grant(
                grant_id=grant_id,
                app_id=app_id,
                root_path=root,
                target_kind=str(target.get("volume_kind") or "volume"),
                volume_id=volume_id,
                container_uid=container_uid,
            )
        else:
            result = {"path": root, "reused": True}
        self.store.create(
            session_id=session_id,
            operator_id=operator_id,
            app_id=app_id,
            volume_id=volume_id,
            root_path=root,
            container_uid=container_uid,
        )
        return result

    def grant(self, session_id: str, path: str) -> Optional[dict[str, Any]]:
        session = self.store.session(session_id)
        if session is None:
            return None
        grant = self.store.find_grant(str(session["app_id"]), str(session["root_path"]))
        if grant is None:
            return None
        return self.authorizer.grant(str(grant["grant_id"]), path)

    def release(self, session_id: str) -> None:
        # Closing a session no longer changes host permissions; grants live until
        # the application is removed.
        self.store.release(session_id)

    def release_app(self, app_id: str) -> dict[str, Any]:
        released = 0
        for grant in self.store.grants_for_app(app_id):
            try:
                self.authorizer.release(str(grant["grant_id"]))
            except CustomException as exc:
                logger.warning(f"SFTP grant release failed for {grant['root_path']}: {exc.details or exc.message}")
                continue
            self.store.delete_grant(str(grant["grant_id"]))
            released += 1
        return {"app_id": app_id, "released": released}

    def release_all(self) -> None:
        for grant in self.store.all_grants():
            try:
                self.authorizer.release(str(grant["grant_id"]))
            except CustomException as exc:
                logger.warning(f"SFTP grant release failed for {grant['root_path']}: {exc.details or exc.message}")
                continue
            self.store.delete_grant(str(grant["grant_id"]))

    def reconcile(self) -> None:
        for session in self.store.active_sessions():
            self.store.release(session["session_id"])
        for grant in self.store.all_grants():
            if self._application_exists(str(grant["app_id"])):
                continue
            logger.info(f"Releasing orphan application SFTP grant for {grant['app_id']} ({grant['root_path']})")
            self.release_app(str(grant["app_id"]))

    def _application_exists(self, app_id: str) -> bool:
        try:
            client = self.resolver._client()
            containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.project={app_id}"})
            if containers:
                return True
            volumes = client.volumes.list(filters={"label": f"com.docker.compose.project={app_id}"})
            return bool(volumes)
        except Exception:
            # Never revoke permissions because Docker was temporarily unavailable.
            return True


def revoke_application_grants(app_id: str) -> dict[str, Any]:
    """Remove the host ACL grants of an application (used on uninstall)."""
    if not str(app_id or "").strip():
        return {"app_id": app_id, "released": 0}
    try:
        return AppSftpAuthority().release_app(str(app_id))
    except Exception as exc:
        logger.warning(f"Unable to revoke application SFTP grants for {app_id}: {exc}")
        return {"app_id": app_id, "released": 0}
