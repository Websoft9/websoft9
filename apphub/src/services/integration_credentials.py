import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.core.config import ConfigManager


@dataclass(frozen=True)
class GiteaCredentials:
    username: str
    password: str
    email: str


@dataclass(frozen=True)
class PortainerCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class NpmCredentials:
    username: str
    password: str
    nickname: str
    display_name: str


class IntegrationCredentialProvider:
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.gitea_credential_path = Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential"))
        self.portainer_credential_path = Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", "/data/portainer/credential"))
        self.npm_credential_path = Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", "/data/nginx-proxy-manager/credential.json"))
        self.npm_database_path = Path(os.getenv("WEBSOFT9_NPM_DATABASE_PATH", "/data/database.sqlite"))

    def get_gitea_credentials(self) -> GiteaCredentials:
        payload = self._read_json_file(self.gitea_credential_path)
        return GiteaCredentials(
            username=str(payload.get("username") or self._get_config_value("gitea", "user_name")),
            password=str(payload.get("password") or self._get_config_value("gitea", "user_pwd")),
            email=str(payload.get("email") or self._get_config_value("gitea", "user_email")),
        )

    def get_portainer_credentials(self) -> PortainerCredentials:
        file_password = ""
        if self.portainer_credential_path.is_file():
            file_password = self.portainer_credential_path.read_text(encoding="utf-8").strip()

        return PortainerCredentials(
            username=os.getenv("WEBSOFT9_PORTAINER_ADMIN_USER", "admin") if file_password else self._get_config_value("portainer", "user_name", fallback=os.getenv("WEBSOFT9_PORTAINER_ADMIN_USER", "admin")),
            password=file_password or self._get_config_value("portainer", "user_pwd"),
        )

    def get_portainer_config_credentials(self) -> PortainerCredentials:
        return PortainerCredentials(
            username=self._get_config_value("portainer", "user_name", fallback=os.getenv("WEBSOFT9_PORTAINER_ADMIN_USER", "admin")),
            password=self._get_config_value("portainer", "user_pwd"),
        )

    def get_npm_credentials(self) -> NpmCredentials:
        payload = self._read_json_file(self.npm_credential_path)
        username = str(payload.get("username") or self._get_config_value("nginx_proxy_manager", "user_name")).strip()
        fallback_name = username.split("@")[0] if username else "admin"
        nickname = str(payload.get("nickname") or self._get_config_value("nginx_proxy_manager", "nike_name", fallback=fallback_name)).strip() or fallback_name
        display_name = str(
            payload.get("display_name")
            or payload.get("name")
            or self._get_config_value("nginx_proxy_manager", "name", fallback=nickname or fallback_name)
        ).strip() or nickname or fallback_name

        return NpmCredentials(
            username=username,
            password=str(payload.get("password") or self._get_config_value("nginx_proxy_manager", "user_pwd")),
            nickname=nickname,
            display_name=display_name,
        )

    def get_npm_config_credentials(self) -> NpmCredentials:
        username = str(self._get_config_value("nginx_proxy_manager", "user_name")).strip()
        fallback_name = username.split("@")[0] if username else "admin"
        nickname = str(self._get_config_value("nginx_proxy_manager", "nike_name", fallback=fallback_name)).strip() or fallback_name
        display_name = str(self._get_config_value("nginx_proxy_manager", "name", fallback=nickname or fallback_name)).strip() or nickname or fallback_name
        return NpmCredentials(
            username=username,
            password=str(self._get_config_value("nginx_proxy_manager", "user_pwd")),
            nickname=nickname,
            display_name=display_name,
        )

    def write_portainer_credentials(self, credentials: PortainerCredentials) -> None:
        if not credentials.password:
            return
        self.portainer_credential_path.parent.mkdir(parents=True, exist_ok=True)
        self.portainer_credential_path.write_text(credentials.password, encoding="utf-8")
        os.chmod(self.portainer_credential_path, 0o600)

    def write_npm_credentials(self, credentials: NpmCredentials) -> None:
        payload = {
            "username": credentials.username,
            "password": credentials.password,
            "nickname": credentials.nickname,
            "display_name": credentials.display_name,
        }
        self.npm_credential_path.parent.mkdir(parents=True, exist_ok=True)
        self.npm_credential_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        os.chmod(self.npm_credential_path, 0o600)

    def sync_npm_credentials(self, credentials: NpmCredentials) -> bool:
        if not self.npm_database_path.is_file():
            return False

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.npm_database_path)
            connection.row_factory = sqlite3.Row
            user_row = connection.execute(
                'SELECT id, email, name, nickname FROM "user" WHERE lower(email) = lower(?) AND is_deleted = 0 ORDER BY id LIMIT 1',
                (credentials.username,),
            ).fetchone()
            if user_row is None:
                user_row = connection.execute(
                    'SELECT id, email, name, nickname FROM "user" WHERE is_deleted = 0 ORDER BY id LIMIT 1'
                ).fetchone()
            if user_row is None:
                return False

            modified_on = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            target_display_name = credentials.display_name.strip() or credentials.nickname.strip() or credentials.username.split("@")[0] or "admin"
            target_nickname = credentials.nickname.strip() or target_display_name
            changed = False

            if str(user_row["email"] or "").strip() != credentials.username:
                changed = True
            if str(user_row["name"] or "").strip() != target_display_name:
                changed = True
            if str(user_row["nickname"] or "").strip() != target_nickname:
                changed = True

            if changed:
                connection.execute(
                    'UPDATE "user" SET email = ?, name = ?, nickname = ?, modified_on = ? WHERE id = ?',
                    (credentials.username, target_display_name, target_nickname, modified_on, user_row["id"]),
                )

            auth_row = connection.execute(
                "SELECT id, secret FROM auth WHERE user_id = ? AND type = 'password' AND is_deleted = 0 ORDER BY id DESC LIMIT 1",
                (user_row["id"],),
            ).fetchone()
            password_changed = False
            if auth_row is not None and credentials.password:
                password_changed = self._repair_npm_password_secret(
                    connection,
                    auth_id=int(auth_row["id"]),
                    stored_secret=str(auth_row["secret"] or ""),
                    password=credentials.password,
                    modified_on=modified_on,
                )

            if changed or password_changed:
                connection.commit()

            return changed or password_changed
        except Exception:
            return False
        finally:
            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    def _repair_npm_password_secret(
        self,
        connection: sqlite3.Connection,
        auth_id: int,
        stored_secret: str,
        password: str,
        modified_on: str,
    ) -> bool:
        try:
            import bcrypt  # type: ignore
        except Exception:
            return False

        if stored_secret and bcrypt.checkpw(password.encode("utf-8"), stored_secret.encode("utf-8")):
            return False

        repaired_secret = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=13)).decode("utf-8")
        connection.execute(
            "UPDATE auth SET secret = ?, modified_on = ? WHERE id = ?",
            (repaired_secret, modified_on, auth_id),
        )
        return True

    def _get_config_value(self, section: str, key: str, fallback: str = "") -> str:
        try:
            return self.config.get_value(section, key)
        except Exception:
            return fallback

    def _read_json_file(self, path: Path) -> dict:
        if not path.is_file():
            return {}

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}