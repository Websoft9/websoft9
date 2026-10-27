"""Platform-owned host account used for application-file SFTP.

A single dedicated system account (``websoft9-sftp``) is prepared once on the
host through a short-lived privileged helper container. It has no password, no
login shell, no sudo rule and no docker group membership.
"""

import fcntl
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import docker

from src.core.exception import CustomException
from src.services.host_access import HOST_ACCESS_HOST, HOST_ACCESS_PORT

logger = logging.getLogger(__name__)

ACCOUNT_NAME = "websoft9-sftp"
APP_ACCOUNT_PREFIX = "websoft9-"
STATE_VERSION = 3


class AppSftpAccountService:
    def __init__(self, data_dir: Optional[str] = None, docker_client: Any = None, docker_client_factory=None):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or f"{data_root}/config/host-access")
        self.data_root = str(data_root)
        self.state_file = self.data_dir / "app-sftp-account.json"
        self.key_file = self.data_dir / "sftp.key"
        self.lock_file = self.data_dir / ".app-sftp.lock"
        self._docker_client = docker_client
        self._docker_client_factory = docker_client_factory

    def _client(self) -> Any:
        if self._docker_client_factory is not None:
            return self._docker_client_factory()
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def status(self) -> dict[str, Any]:
        state = self._read_state()
        username = str(state.get("username") or "")
        ready = (
            bool(state)
            and self.key_file.is_file()
            and username.startswith(APP_ACCOUNT_PREFIX)
            and int(state.get("version") or 0) == STATE_VERSION
        )
        return {
            "state": "ready" if ready else "missing",
            "account": username or ACCOUNT_NAME,
            "uid": state.get("uid") if state else None,
            "sshd_mode": state.get("sshd_mode") if state else None,
            "version": state.get("version") if state else None,
            "key_present": self.key_file.is_file(),
        }

    def credentials(self) -> dict[str, Any]:
        state = self._read_state()
        username = str(state.get("username") or "") if state else ""
        if not state or not self.key_file.is_file() or not username:
            raise CustomException(409, "SFTP Account Unavailable", "The platform SFTP account is not prepared yet")
        private_key = self._read_private_key()
        return {
            "profile_id": "platform-sftp",
            "name": username,
            "host": HOST_ACCESS_HOST,
            "port": int(state.get("port") or HOST_ACCESS_PORT),
            "username": username,
            "auth_method": "key",
            "private_key": private_key,
            "passphrase": "",
            "remember": True,
        }

    def ensure(self, force: bool = False) -> dict[str, Any]:
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._file_lock():
            if not force and self.status()["state"] == "ready":
                return self.status()
            state = self._prepare()
            if int(state.get("version") or 0) != STATE_VERSION:
                raise CustomException(500, "SFTP Account Unavailable", "The host SFTP account state is not supported")
            self._verify()
            return self.status()

    def _file_lock(self):
        descriptor = os.open(self.lock_file, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)

        class _Lock:
            def __enter__(inner_self):
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                return inner_self

            def __exit__(inner_self, *exc_info):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
                return False

        return _Lock()

    def _read_state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return {}
        try:
            attributes = self.state_file.lstat()
            if attributes.st_uid != os.geteuid() or attributes.st_mode & 0o077:
                return {}
            return json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            return {}

    def _read_private_key(self) -> str:
        attributes = self.key_file.lstat()
        if attributes.st_mode & 0o077 or attributes.st_uid != os.geteuid():
            raise CustomException(500, "SFTP Account Unavailable", "The prepared SFTP key has unsafe permissions")
        return self.key_file.read_text()

    def revoke(self) -> dict[str, Any]:
        self._run_helper("revoke")
        return self.status()

    def _prepare(self) -> dict[str, Any]:
        return self._run_helper("prepare")

    def _run_helper(self, operation: str) -> dict[str, Any]:
        script = Path(__file__).with_name("app_sftp_prepare.py").read_text()
        container = None
        client = None
        try:
            client = self._client()
            image = client.containers.get(os.environ["HOSTNAME"]).image.id
            container = client.containers.run(
                image=image,
                command=["python3", "-c", script, operation, self.data_root],
                entrypoint=["nsenter", "--target", "1", "--mount", "--net", "--pid", "--root", "--wd", "--"],
                pid_mode="host",
                network_mode="host",
                privileged=True,
                user="0",
                detach=True,
                labels={"owner": "websoft9", "websoft9.operation": "prepare-app-sftp"},
            )
            result = container.wait(timeout=120)
            output = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace").strip()
            errors = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace").strip()
            if int(result.get("StatusCode", 1)) != 0:
                detail = errors or output or "Host SFTP account preparation failed"
                lowered = detail.lower()
                if (
                    'refusing to use it' in lowered
                    or 'unexpected home directory' in lowered
                    or 'privileged groups' in lowered
                    or 'unexpected owner' in lowered
                ):
                    # A local account with our reserved name already exists but was
                    # not created by the platform: never reuse or modify it.
                    raise CustomException(
                        409,
                        "SFTP Account Conflict",
                        "A local account named websoft9-sftp already exists but was not created by the platform. Remove or rename it, or use a local connection instead.",
                    )
                raise CustomException(409, "SFTP Account Unavailable", detail)
            try:
                return json.loads(output.splitlines()[-1])
            except (ValueError, IndexError) as exc:
                raise CustomException(500, "SFTP Account Unavailable", "The host SFTP helper returned an invalid response") from exc
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(409, "SFTP Account Unavailable", f"Unable to prepare the platform SFTP account: {exc}") from exc
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

    def _verify(self) -> None:
        import paramiko

        profile = self.credentials()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            key = paramiko.RSAKey.from_private_key_file(str(self.key_file))
            client.connect(
                hostname=profile["host"],
                port=profile["port"],
                username=profile["username"],
                pkey=key,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            sftp = client.open_sftp()
            try:
                sftp.stat("/")
            finally:
                sftp.close()
        except CustomException:
            raise
        except Exception as exc:
            raise CustomException(500, "SFTP Account Unavailable", f"The prepared SFTP account cannot log in: {exc}") from exc
        finally:
            client.close()
