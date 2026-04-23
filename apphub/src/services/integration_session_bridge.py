import os
import re
import json
from pathlib import Path
from typing import Literal, Optional

import requests

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger


IntegrationKey = Literal["gitea", "portainer", "npm"]


class IntegrationSessionBridge:
    def __init__(self, gateway_origin: Optional[str] = None):
        self.gateway_origin = gateway_origin or os.getenv(
            "WEBSOFT9_PLATFORM_GATEWAY_INTERNAL_ORIGIN",
            "http://127.0.0.1:8889",
        ).rstrip("/")
        self.gitea_credential_path = Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential"))
        self.gitea_direct_origin = os.getenv(
            "WEBSOFT9_GITEA_DIRECT_ORIGIN",
            "http://127.0.0.1:3001",
        ).rstrip("/")
        self.portainer_credential_path = Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", "/data/portainer/credential"))
        self.npm_credential_path = Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", "/data/nginx-proxy-manager/credential.json"))
        self.portainer_direct_origin = os.getenv(
            "WEBSOFT9_PORTAINER_DIRECT_ORIGIN",
            "http://127.0.0.1:9003",
        ).rstrip("/")

    def bootstrap(self, integration_key: IntegrationKey, locale: Optional[str] = None) -> list[dict[str, object]]:
        if integration_key == "gitea":
            return self.bootstrap_gitea(locale)
        if integration_key == "portainer":
            return self.bootstrap_portainer()
        if integration_key == "npm":
            return self.bootstrap_npm()

        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details=f"Unsupported integration: {integration_key}",
        )

    def bootstrap_gitea(self, locale: Optional[str] = None) -> list[dict[str, object]]:
        username, password = self._get_gitea_credentials()
        session = self._create_session()

        try:
            login_page = session.get(f"{self.gitea_direct_origin}/user/login", timeout=20)
            login_page.raise_for_status()

            csrf_match = re.search(r'name="_csrf" value="([^"]+)"', login_page.text)
            if not csrf_match:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Gitea login page did not expose a CSRF token",
                )

            login_response = session.post(
                f"{self.gitea_direct_origin}/user/login",
                data={
                    "_csrf": csrf_match.group(1),
                    "user_name": username,
                    "password": password,
                },
                allow_redirects=False,
                timeout=20,
            )
            if login_response.status_code >= 400:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details=f"Gitea login failed with status {login_response.status_code}",
                )

            if "Sign In - Gitea" in login_response.text:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Gitea credentials were rejected by the login form",
                )

            self._verify_gitea_session_cookie(session)

            cookies = self._export_session_cookies(session, default_path="/w9git/")
            if not cookies:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Gitea session bootstrap did not yield browser cookies",
                )

            self._upsert_cookie(
                cookies,
                name="lang",
                value=self._resolve_gitea_locale(locale),
                path="/w9git",
            )

            return cookies
        except CustomException:
            raise
        except Exception as exc:
            logger.error(f"Gitea session bootstrap failed: {exc}")
            raise CustomException(
                status_code=502,
                message="Integration Session Bootstrap Failed",
                details="Unable to establish Gitea session",
            )

    def _verify_gitea_session_cookie(self, session: requests.Session) -> None:
        cookie_names = {cookie.name for cookie in session.cookies}
        if "i_like_gitea" not in cookie_names:
            raise CustomException(
                status_code=502,
                message="Integration Session Bootstrap Failed",
                details="Gitea login did not yield the expected session cookie",
            )

    def bootstrap_portainer(self) -> list[dict[str, object]]:
        username, password = self._get_portainer_credentials()
        session = self._create_session()

        try:
            response = self._post_portainer_auth(session, username, password)

            jwt = response.json().get("jwt")
            if not jwt:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Portainer login returned no JWT token",
                )

            return [
                {
                    "name": "portainer_jwt",
                    "value": jwt,
                    "path": "/",
                    "httponly": False,
                }
            ]
        except CustomException:
            raise
        except Exception as exc:
            logger.error(f"Portainer session bootstrap failed: {exc}")
            raise CustomException(
                status_code=502,
                message="Integration Session Bootstrap Failed",
                details="Unable to establish Portainer session",
            )

    def _post_portainer_auth(self, session: requests.Session, username: str, password: str):
        response = session.post(
            f"{self.gateway_origin}/w9deployment/api/auth",
            json={"username": username, "password": password},
            timeout=20,
        )

        if response.ok:
            return response

        if response.status_code != 404:
            response.raise_for_status()

        fallback_response = session.post(
            f"{self.portainer_direct_origin}/api/auth",
            json={"username": username, "password": password},
            timeout=20,
        )
        fallback_response.raise_for_status()
        return fallback_response

    def bootstrap_npm(self) -> list[dict[str, object]]:
        username, password, nickname = self._get_npm_credentials()
        session = self._create_session()

        try:
            response = session.post(
                f"{self.gateway_origin}/w9proxy/api/tokens",
                json={"identity": username, "scope": "user", "secret": password},
                timeout=20,
            )
            response.raise_for_status()

            token = response.json().get("token")
            if not token:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Nginx Proxy Manager login returned no API token",
                )

            return [
                {
                    "name": "nginx_tokens",
                    "value": token,
                    "path": "/",
                    "httponly": False,
                },
                {
                    "name": "nginx_nikeName",
                    "value": nickname,
                    "path": "/",
                    "httponly": False,
                },
            ]
        except CustomException:
            raise
        except Exception as exc:
            logger.error(f"Nginx Proxy Manager session bootstrap failed: {exc}")
            raise CustomException(
                status_code=502,
                message="Integration Session Bootstrap Failed",
                details="Unable to establish Nginx Proxy Manager session",
            )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        return session

    def _get_gitea_credentials(self) -> tuple[str, str]:
        if self.gitea_credential_path.is_file():
            payload = json.loads(self.gitea_credential_path.read_text())
            return payload["username"], payload["password"]

        return (
            ConfigManager().get_value("gitea", "user_name"),
            ConfigManager().get_value("gitea", "user_pwd"),
        )

    def _get_portainer_credentials(self) -> tuple[str, str]:
        if self.portainer_credential_path.is_file():
            return os.getenv("WEBSOFT9_PORTAINER_ADMIN_USER", "admin"), self.portainer_credential_path.read_text().strip()

        return (
            ConfigManager().get_value("portainer", "user_name"),
            ConfigManager().get_value("portainer", "user_pwd"),
        )

    def _get_npm_credentials(self) -> tuple[str, str, str]:
        if self.npm_credential_path.is_file():
            payload = json.loads(self.npm_credential_path.read_text())
            username = payload["username"]
            return username, payload["password"], payload.get("nickname", username.split("@")[0])

        username = ConfigManager().get_value("nginx_proxy_manager", "user_name")
        return (
            username,
            ConfigManager().get_value("nginx_proxy_manager", "user_pwd"),
            ConfigManager().get_value("nginx_proxy_manager", "nike_name"),
        )

    def _export_session_cookies(self, session: requests.Session, default_path: str) -> list[dict[str, object]]:
        cookies: list[dict[str, object]] = []
        for cookie in session.cookies:
            path = self._normalize_cookie_path(cookie.path, default_path)
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "path": path,
                    "httponly": False,
                }
            )
        return cookies

    def _normalize_cookie_path(self, cookie_path: Optional[str], default_path: str) -> str:
        normalized_default = (default_path or "/").rstrip("/") or "/"
        normalized_cookie_path = (cookie_path or normalized_default).rstrip("/") or "/"

        duplicated_prefix = f"{normalized_default}{normalized_default}"
        if normalized_cookie_path == duplicated_prefix:
            return normalized_default

        if normalized_cookie_path.startswith(f"{duplicated_prefix}/"):
            suffix = normalized_cookie_path[len(duplicated_prefix):]
            return f"{normalized_default}{suffix}" or normalized_default

        return normalized_cookie_path

    def _resolve_gitea_locale(self, locale: Optional[str]) -> str:
        normalized_locale = (locale or "").strip().lower()
        if normalized_locale.startswith("zh"):
            return "zh-CN"

        return "en-US"

    def _upsert_cookie(self, cookies: list[dict[str, object]], name: str, value: str, path: str) -> None:
        for cookie in cookies:
            if cookie.get("name") == name:
                cookie["value"] = value
                cookie["path"] = path
                return

        cookies.append(
            {
                "name": name,
                "value": value,
                "path": path,
                "httponly": False,
            }
        )