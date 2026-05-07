import json
import os
from dataclasses import dataclass
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


class IntegrationCredentialProvider:
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.gitea_credential_path = Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential"))
        self.portainer_credential_path = Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", "/data/portainer/credential"))
        self.npm_credential_path = Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", "/data/nginx-proxy-manager/credential.json"))

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

    def get_npm_credentials(self) -> NpmCredentials:
        payload = self._read_json_file(self.npm_credential_path)
        username = str(payload.get("username") or self._get_config_value("nginx_proxy_manager", "user_name"))
        nickname = str(payload.get("nickname") or self._get_config_value("nginx_proxy_manager", "nike_name", fallback=username.split("@")[0] if username else "admin"))
        return NpmCredentials(
            username=username,
            password=str(payload.get("password") or self._get_config_value("nginx_proxy_manager", "user_pwd")),
            nickname=nickname,
        )

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