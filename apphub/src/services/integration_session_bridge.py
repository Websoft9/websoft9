import os
import re
import json
from pathlib import Path
from typing import Literal, Optional

import requests

from src.core.exception import CustomException
from src.core.logger import logger
from src.services.integration_credentials import IntegrationCredentialProvider


IntegrationKey = Literal["gitea", "portainer", "npm"]


class IntegrationSessionBridge:
    def __init__(self, gateway_origin: Optional[str] = None):
        self.credential_provider = IntegrationCredentialProvider()
        self.gateway_origin = gateway_origin or os.getenv(
            "WEBSOFT9_PLATFORM_GATEWAY_INTERNAL_ORIGIN",
            "http://127.0.0.1:9000",
        ).rstrip("/")
        self.gitea_credential_path = Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential"))
        self.gitea_direct_origin = os.getenv(
            "WEBSOFT9_GITEA_DIRECT_ORIGIN",
            "http://127.0.0.1:3001",
        ).rstrip("/")
        self.portainer_credential_path = Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", "/data/portainer/credential"))
        self.portainer_direct_origin = os.getenv(
            "WEBSOFT9_PORTAINER_DIRECT_ORIGIN",
            "http://127.0.0.1:9004",
        ).rstrip("/")
        self.npm_credential_path = Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", "/data/nginx-proxy-manager/credential.json"))
        self.npm_database_path = Path(os.getenv("WEBSOFT9_NPM_DATABASE_PATH", "/data/database.sqlite"))

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

    def bootstrap_all(self, locale: Optional[str] = None) -> dict[str, object]:
        integrations: dict[str, dict[str, object]] = {}
        cookies: list[dict[str, object]] = []

        for integration_key in ("gitea", "portainer", "npm"):
            try:
                next_cookies = self.bootstrap(integration_key, locale=locale)
                integrations[integration_key] = {
                    "status": "ok",
                    "cookies": len(next_cookies),
                }
                cookies.extend(next_cookies)
            except CustomException as exc:
                integrations[integration_key] = {
                    "status": "error",
                    "message": exc.details or exc.message,
                }
            except Exception as exc:
                logger.error(f"{integration_key} bulk bootstrap failed: {exc}")
                integrations[integration_key] = {
                    "status": "error",
                    "message": "Unexpected integration bootstrap failure",
                }

        status = "ok" if all(result["status"] == "ok" for result in integrations.values()) else "partial"
        return {
            "status": status,
            "integrations": integrations,
            "cookies": cookies,
        }

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
            response = session.post(
                f"{self.portainer_direct_origin}/api/auth",
                json={"username": username, "password": password},
                timeout=20,
            )
            response.raise_for_status()

            token = response.json().get("jwt")
            if not token:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Portainer login returned no JWT token",
                )

            return [
                {
                    "name": "portainer_jwt",
                    "value": token,
                    "path": "/",
                    "httponly": True,
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

    def bootstrap_npm(self) -> list[dict[str, object]]:
        username, password, nickname = self._get_npm_credentials()
        session = self._create_session()

        try:
            if self.credential_provider.sync_npm_credentials(self.credential_provider.get_npm_credentials()):
                logger.warning("Nginx Proxy Manager credential drift detected; runtime user profile was synchronized from stored credential source")

            response = self._request_npm_token(session, username, password)

            if response.status_code in {401, 403} and self.credential_provider.sync_npm_credentials(self.credential_provider.get_npm_credentials()):
                logger.warning("Nginx Proxy Manager authentication recovered after synchronizing stored credentials into the runtime database")
                response = self._request_npm_token(session, username, password)

            if response.status_code in {401, 403}:
                raise CustomException(
                    status_code=502,
                    message="Integration Session Bootstrap Failed",
                    details="Unable to restore the embedded gateway session automatically",
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
                details="Unable to restore the embedded gateway session automatically",
            )

    def _request_npm_token(self, session: requests.Session, username: str, password: str) -> requests.Response:
        return session.post(
            f"{self.gateway_origin}/w9proxy/api/tokens",
            json={"identity": username, "scope": "user", "secret": password},
            timeout=20,
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        return session

    def _get_gitea_credentials(self) -> tuple[str, str]:
        credentials = self.credential_provider.get_gitea_credentials()
        return credentials.username, credentials.password

    def _get_portainer_credentials(self) -> tuple[str, str]:
        credentials = self.credential_provider.get_portainer_credentials()
        return credentials.username, credentials.password

    def _get_npm_credentials(self) -> tuple[str, str, str]:
        credentials = self.credential_provider.get_npm_credentials()
        return credentials.username, credentials.password, credentials.nickname

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