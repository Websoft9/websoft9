import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger


DEFAULT_PRODUCT_AUTH_PROTECTED_MODULES = ["users", "files", "terminal", "services", "logs"]


def _resolve_product_auth_cookie_name() -> str:
    base_name = "websoft9_operator_session"

    platform_port = (os.getenv("WEBSOFT9_PLATFORM_HTTP_PORT") or "").strip()
    if platform_port.isdigit():
        return f"{base_name}_{platform_port}"

    public_origin = (os.getenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN") or "").strip()
    if public_origin:
        parsed_origin = urlparse(public_origin)
        cookie_suffix = "".join(char if char.isalnum() else "_" for char in parsed_origin.netloc).strip("_")
        if cookie_suffix:
            return f"{base_name}_{cookie_suffix}"

    return base_name


PRODUCT_AUTH_COOKIE_NAME = _resolve_product_auth_cookie_name()
SESSION_TTL_DAYS = 30
PASSWORD_HASH_ITERATIONS = 310_000
DOCKER_BOOTSTRAP_ACTOR = "docker-bootstrap"


class ProductAuthService:
    _lock = threading.RLock()

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR") or "/etc/custom/product-auth")
        self.database_file = self.data_dir / "product-auth.sqlite"

    def get_status(self, session_token: Optional[str] = None) -> dict[str, Any]:
        status_payload, _ = self.get_status_with_auto_session(session_token=session_token)
        return status_payload

    def get_status_with_auto_session(
        self,
        session_token: Optional[str] = None,
        trusted_internal_request: bool = False,
    ) -> Tuple[dict[str, Any], Optional[str]]:
        enabled = self.is_enabled()
        current_user = None
        issued_session_token = None
        if enabled and session_token:
            current_user = self._resolve_session(session_token)

        if enabled and current_user is None and trusted_internal_request:
            with self._lock:
                auto_login_operator = self._get_internal_auto_login_operator()
                if auto_login_operator is not None:
                    issued_session_token = self._create_session(auto_login_operator["id"])
                    current_user = self._public_operator(auto_login_operator)
                    self._append_audit(
                        event="auto_login",
                        operator_id=auto_login_operator["id"],
                        username=auto_login_operator["username"],
                        reason="trusted-internal-request",
                    )

        return {
            "enabled": enabled,
            "initialization_required": enabled and not self._has_active_operator(),
            "authenticated": current_user is not None,
            "protected_modules": self.get_protected_modules(),
            "current_user": current_user,
            "storage_boundary": self._build_storage_boundary(),
        }, issued_session_token

    def bootstrap_operator_if_missing(
        self,
        username: str,
        password: str,
        display_name: str,
        locale: str = "en",
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[dict[str, Any], bool]:
        self._assert_enabled()

        with self._lock:
            self._ensure_storage()
            operators = self._load_operators()
            existing_operator = self._get_internal_auto_login_operator(operators=operators)
            if existing_operator is not None:
                return self._public_operator(existing_operator), False

            if any(not item.get("deleted", False) for item in operators):
                surviving_operator = next(item for item in operators if not item.get("deleted", False))
                return self._public_operator(surviving_operator), False

            operator = self._build_operator(
                username=username,
                password=password,
                display_name=display_name,
                locale=locale,
                created_by=DOCKER_BOOTSTRAP_ACTOR,
            )
            operators.append(operator)
            self._store_operators(operators)
            self._append_audit(
                event="docker_bootstrap",
                operator_id=operator["id"],
                username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator), True

    def initialize_first_operator(
        self,
        username: str,
        password: str,
        display_name: str,
        locale: str = "en",
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[dict[str, Any], str]:
        self._assert_enabled()

        with self._lock:
            self._ensure_storage()
            operators = self._load_operators()
            if any(not item.get("deleted", False) for item in operators):
                raise CustomException(
                    status_code=409,
                    message="Initialization Not Allowed",
                    details="Product-side operator initialization has already been completed",
                )

            operator = self._build_operator(username=username, password=password, display_name=display_name, locale=locale)
            operators.append(operator)
            self._store_operators(operators)
            session_token = self._create_session(operator_id=operator["id"])
            self._append_audit(
                event="bootstrap",
                operator_id=operator["id"],
                username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self.get_status(session_token=session_token), session_token

    def login(
        self,
        username: str,
        password: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[dict[str, Any], str]:
        self._assert_enabled()

        with self._lock:
            operator = self._get_operator_by_username(username)
            if operator is None or operator.get("deleted"):
                self._append_audit(
                    event="login_denied",
                    username=username.strip().lower(),
                    client_host=client_host,
                    user_agent=user_agent,
                )
                raise CustomException(
                    status_code=401,
                    message="Authentication Failed",
                    details="Invalid username or password",
                )

            if operator.get("disabled"):
                self._append_audit(
                    event="login_denied",
                    operator_id=operator["id"],
                    username=operator["username"],
                    client_host=client_host,
                    user_agent=user_agent,
                )
                raise CustomException(
                    status_code=403,
                    message="Authentication Failed",
                    details="User account is disabled",
                )

            if not self._verify_password(password, operator["password_hash"]):
                self._append_audit(
                    event="login_denied",
                    operator_id=operator["id"],
                    username=operator["username"],
                    client_host=client_host,
                    user_agent=user_agent,
                )
                raise CustomException(
                    status_code=401,
                    message="Authentication Failed",
                    details="Invalid username or password",
                )

            session_token = self._create_session(operator_id=operator["id"])
            self._append_audit(
                event="login",
                operator_id=operator["id"],
                username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self.get_status(session_token=session_token), session_token

    def logout(
        self,
        session_token: Optional[str],
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        self._assert_enabled()

        if not session_token:
            return self.get_status(session_token=None)

        with self._lock:
            sessions = self._load_sessions()
            token_hash = self._hash_session_token(session_token)
            operator_id = None
            for session in sessions:
                if session.get("token_hash") != token_hash or session.get("invalidated_at"):
                    continue
                session["invalidated_at"] = self._now_iso()
                operator_id = session.get("operator_id")
                break

            self._store_sessions(sessions)
            self._append_audit(
                event="logout",
                operator_id=operator_id,
                client_host=client_host,
                user_agent=user_agent,
            )

        return self.get_status(session_token=None)

    def invalidate_sessions_for_operator(self, operator_id: str, reason: str) -> None:
        with self._lock:
            sessions = self._load_sessions()
            updated = False
            for session in sessions:
                if session.get("operator_id") != operator_id or session.get("invalidated_at"):
                    continue
                session["invalidated_at"] = self._now_iso()
                updated = True

            if updated:
                self._store_sessions(sessions)
                self._append_audit(event="session_invalidation", operator_id=operator_id, reason=reason)

    def list_operators(self, session_token: Optional[str]) -> list[dict[str, Any]]:
        actor = self._require_authenticated_operator(session_token)
        operators = self._load_operators()
        visible_operators = [item for item in operators if not item.get("deleted", False)]

        if not self._is_system_user(actor):
            visible_operators = [item for item in visible_operators if item.get("id") == actor.get("id")]

        return [self._public_operator(item) for item in sorted(visible_operators, key=lambda item: item.get("created_at", ""))]

    def create_operator(
        self,
        session_token: Optional[str],
        username: str,
        password: str,
        display_name: str,
        email: Optional[str] = None,
        locale: str = "en",
        disabled: bool = False,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)
        self._assert_can_manage_users(actor)

        with self._lock:
            self._ensure_storage()
            operators = self._load_operators()
            normalized_username = username.strip().lower()
            if any(item.get("username") == normalized_username for item in operators):
                raise CustomException(
                    status_code=409,
                    message="Operator Already Exists",
                    details="Username is already in use",
                )

            operator = self._build_operator(
                username=username,
                password=password,
                display_name=display_name,
                email=email,
                locale=locale,
                disabled=disabled,
                created_by=actor["username"],
            )
            operators.append(operator)
            self._store_operators(operators)
            self._append_audit(
                event="user_create",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def disable_operator(
        self,
        session_token: Optional[str],
        target_operator_id: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)

        with self._lock:
            operators = self._load_operators()
            operator = self._find_manageable_operator(operators, target_operator_id)
            self._assert_can_manage_target_operator(actor, operator, allow_self=False)
            self._assert_not_last_active_operator(operators, operator, action="disable")

            operator["disabled"] = True
            operator["updated_at"] = self._now_iso()
            self._store_operators(operators)
            self.invalidate_sessions_for_operator(operator["id"], "disabled")
            self._append_audit(
                event="user_disable",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def enable_operator(
        self,
        session_token: Optional[str],
        target_operator_id: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)
        self._assert_can_manage_users(actor)

        with self._lock:
            operators = self._load_operators()
            operator = self._find_manageable_operator(operators, target_operator_id)
            self._assert_not_protected_bootstrap_operator(operator, action="enable")
            operator["disabled"] = False
            operator["updated_at"] = self._now_iso()
            self._store_operators(operators)
            self._append_audit(
                event="user_enable",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def update_operator(
        self,
        session_token: Optional[str],
        target_operator_id: str,
        display_name: str,
        email: Optional[str] = None,
        locale: str = "en",
        disabled: Optional[bool] = None,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)

        with self._lock:
            operators = self._load_operators()
            operator = self._find_manageable_operator(operators, target_operator_id)
            self._assert_can_manage_target_operator(actor, operator, allow_self=True)
            normalized_display_name = display_name.strip()

            if not normalized_display_name:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="Display name cannot be empty",
                )

            operator["display_name"] = normalized_display_name
            operator["email"] = email or None
            operator["locale"] = locale
            if disabled is not None and bool(disabled) != bool(operator.get("disabled", False)):
                if disabled:
                    self._assert_can_manage_target_operator(actor, operator, allow_self=False)
                    self._assert_not_last_active_operator(operators, operator, action="disable")
                else:
                    self._assert_can_manage_users(actor)
                    self._assert_not_protected_bootstrap_operator(operator, action="enable")
                operator["disabled"] = bool(disabled)
            operator["updated_at"] = self._now_iso()
            self._store_operators(operators)
            self._append_audit(
                event="user_update",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def reset_operator_password(
        self,
        session_token: Optional[str],
        target_operator_id: str,
        password: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)

        with self._lock:
            operators = self._load_operators()
            operator = self._find_manageable_operator(operators, target_operator_id)
            self._assert_can_manage_target_operator(actor, operator, allow_self=True)
            if not operator.get("reset_password_eligible", True):
                raise CustomException(
                    status_code=409,
                    message="Password Reset Not Allowed",
                    details="Operator password reset is not allowed for this account",
                )

            operator["password_hash"] = self._hash_password(password)
            operator["updated_at"] = self._now_iso()
            self._store_operators(operators)
            self.invalidate_sessions_for_operator(operator["id"], "password-reset")
            self._append_audit(
                event="user_password_reset",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def delete_operator(
        self,
        session_token: Optional[str],
        target_operator_id: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        actor = self._require_authenticated_operator(session_token)

        with self._lock:
            operators = self._load_operators()
            operator = self._find_manageable_operator(operators, target_operator_id)
            self._assert_can_manage_target_operator(actor, operator, allow_self=False)
            self._assert_not_protected_bootstrap_operator(operator, action="delete")
            self._assert_not_last_active_operator(operators, operator, action="delete")

            operator["deleted"] = True
            operator["disabled"] = True
            operator["updated_at"] = self._now_iso()
            self._store_operators(operators)
            self.invalidate_sessions_for_operator(operator["id"], "deleted")
            self._append_audit(
                event="user_delete",
                operator_id=actor["id"],
                username=actor["username"],
                target_operator_id=operator["id"],
                target_username=operator["username"],
                client_host=client_host,
                user_agent=user_agent,
            )

        return self._public_operator(operator)

    def list_favorites(self, session_token: Optional[str]) -> list[str]:
        actor = self._require_authenticated_operator(session_token)
        return self._load_favorites(actor["id"])

    def add_favorite(
        self,
        session_token: Optional[str],
        app_key: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> list[str]:
        actor = self._require_authenticated_operator(session_token)
        normalized_app_key = app_key.strip().lower()
        if not normalized_app_key:
            raise CustomException(status_code=400, message="Invalid Request", details="App key cannot be empty")

        with self._lock:
            self._ensure_storage()
            with self._db_connect() as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO favorites (operator_id, app_key, created_at) VALUES (?, ?, ?)",
                    (actor["id"], normalized_app_key, self._now_iso()),
                )
                connection.commit()
            self._append_audit(
                event="favorite_add",
                operator_id=actor["id"],
                username=actor["username"],
                app_key=normalized_app_key,
                client_host=client_host,
                user_agent=user_agent,
            )
        return self._load_favorites(actor["id"])

    def remove_favorite(
        self,
        session_token: Optional[str],
        app_key: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> list[str]:
        actor = self._require_authenticated_operator(session_token)
        normalized_app_key = app_key.strip().lower()

        with self._lock:
            self._ensure_storage()
            with self._db_connect() as connection:
                connection.execute(
                    "DELETE FROM favorites WHERE operator_id = ? AND app_key = ?",
                    (actor["id"], normalized_app_key),
                )
                connection.commit()
            self._append_audit(
                event="favorite_remove",
                operator_id=actor["id"],
                username=actor["username"],
                app_key=normalized_app_key,
                client_host=client_host,
                user_agent=user_agent,
            )
        return self._load_favorites(actor["id"])

    def is_enabled(self) -> bool:
        env_value = os.getenv("WEBSOFT9_PRODUCT_AUTH_ENABLED")
        if env_value is not None:
            return env_value.strip().lower() in {"1", "true", "yes", "on"}

        try:
            config_value = ConfigManager().get_value("product_auth", "enabled")
        except Exception:
            config_value = "true"

        return str(config_value).strip().lower() in {"1", "true", "yes", "on"}

    def get_protected_modules(self) -> list[str]:
        env_value = os.getenv("WEBSOFT9_PRODUCT_AUTH_PROTECTED_MODULES")
        if env_value is not None:
            return [item.strip() for item in env_value.split(",") if item.strip()]

        try:
            config_value = ConfigManager().get_value("product_auth", "protected_modules")
        except Exception:
            return list(DEFAULT_PRODUCT_AUTH_PROTECTED_MODULES)

        modules = [item.strip() for item in str(config_value).split(",") if item.strip()]
        return modules or list(DEFAULT_PRODUCT_AUTH_PROTECTED_MODULES)

    def _assert_enabled(self) -> None:
        if not self.is_enabled():
            raise CustomException(
                status_code=403,
                message="Product Authentication Disabled",
                details="Product-side authentication is currently disabled",
            )

    def _has_active_operator(self) -> bool:
        operators = self._load_operators()
        return any(not item.get("deleted", False) for item in operators)

    def _get_internal_auto_login_operator(self, operators: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
        active_operators = [
            item
            for item in (operators if operators is not None else self._load_operators())
            if not item.get("deleted", False) and not item.get("disabled", False)
        ]
        if len(active_operators) != 1:
            return None

        operator = active_operators[0]
        if operator.get("created_by") != DOCKER_BOOTSTRAP_ACTOR:
            return None

        return operator

    def _is_protected_bootstrap_operator(self, operator: dict[str, Any]) -> bool:
        return operator.get("created_by") in {DOCKER_BOOTSTRAP_ACTOR, "bootstrap"}

    def _assert_not_protected_bootstrap_operator(self, operator: dict[str, Any], action: str) -> None:
        if self._is_protected_bootstrap_operator(operator):
            raise CustomException(
                status_code=409,
                message="Protected User",
                details=f"Cannot {action} the initialized Websoft9 user",
            )

    def _is_system_user(self, operator: dict[str, Any]) -> bool:
        if operator.get("delete_eligible") is False:
            return True
        return self._is_protected_bootstrap_operator(operator)

    def _assert_can_manage_users(self, actor: dict[str, Any]) -> None:
        if not self._is_system_user(actor):
            raise CustomException(
                status_code=403,
                message="Permission Denied",
                details="Only the system user can manage other users",
            )

    def _assert_can_manage_target_operator(self, actor: dict[str, Any], target_operator: dict[str, Any], allow_self: bool) -> None:
        if self._is_system_user(actor):
            return

        if allow_self and actor.get("id") == target_operator.get("id"):
            return

        raise CustomException(
            status_code=403,
            message="Permission Denied",
            details="You can only edit your own profile and password",
        )

    def _resolve_session(self, session_token: str) -> Optional[dict[str, Any]]:
        if not session_token:
            return None

        with self._lock:
            sessions = self._load_sessions()
            token_hash = self._hash_session_token(session_token)
            now = self._now()
            matched_session = None
            for session in sessions:
                if session.get("token_hash") != token_hash:
                    continue
                matched_session = session
                break

            if matched_session is None:
                return None

            if matched_session.get("invalidated_at"):
                return None

            expires_at = self._parse_iso(matched_session["expires_at"])
            if expires_at <= now:
                matched_session["invalidated_at"] = self._now_iso()
                self._store_sessions(sessions)
                self._append_audit(event="session_expired", operator_id=matched_session.get("operator_id"))
                return None

            operator = self._get_operator_by_id(matched_session["operator_id"])
            if operator is None or operator.get("deleted") or operator.get("disabled"):
                matched_session["invalidated_at"] = self._now_iso()
                self._store_sessions(sessions)
                self._append_audit(
                    event="session_invalidation",
                    operator_id=matched_session.get("operator_id"),
                    reason="operator-unavailable",
                )
                return None

            matched_session["last_seen_at"] = self._now_iso()
            self._store_sessions(sessions)
            return self._public_operator(operator)

    def _build_operator(
        self,
        username: str,
        password: str,
        display_name: str,
        email: Optional[str] = None,
        locale: str = "en",
        disabled: bool = False,
        created_by: str = "bootstrap",
    ) -> dict[str, Any]:
        normalized_username = username.strip().lower()
        normalized_display_name = display_name.strip()
        if not normalized_username.replace("-", "").replace("_", "").isalnum():
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Username must be alphanumeric and may include '-' or '_'",
            )
        if not normalized_display_name:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Display name cannot be empty",
            )

        now = self._now_iso()
        return {
            "id": str(uuid.uuid4()),
            "username": normalized_username,
            "display_name": normalized_display_name,
            "email": email or None,
            "locale": locale,
            "password_hash": self._hash_password(password),
            "disabled": bool(disabled),
            "deleted": False,
            "created_by": created_by,
            "reset_password_eligible": True,
            "created_at": now,
            "updated_at": now,
        }

    def _require_authenticated_operator(self, session_token: Optional[str]) -> dict[str, Any]:
        self._assert_enabled()
        current_user = self._resolve_session(session_token or "")
        if current_user is None:
            raise CustomException(
                status_code=401,
                message="Authentication Required",
                details="A valid product-side session is required for this operation",
            )
        return current_user

    def _find_manageable_operator(self, operators: list[dict[str, Any]], operator_id: str) -> dict[str, Any]:
        for operator in operators:
            if operator.get("id") == operator_id and not operator.get("deleted", False):
                return operator

        raise CustomException(
            status_code=404,
            message="Operator Not Found",
            details="The requested product-side operator does not exist",
        )

    def _assert_not_last_active_operator(self, operators: list[dict[str, Any]], target_operator: dict[str, Any], action: str) -> None:
        target_is_active = not target_operator.get("deleted", False) and not target_operator.get("disabled", False)
        active_count = sum(1 for operator in operators if not operator.get("deleted", False) and not operator.get("disabled", False))
        if target_is_active and active_count <= 1:
            raise CustomException(
                status_code=409,
                message="Last Active Operator Protected",
                details=f"Cannot {action} the last active product-side operator account",
            )

    def _create_session(self, operator_id: str) -> str:
        sessions = self._load_sessions()
        session_token = secrets.token_urlsafe(32)
        now = self._now()
        sessions.append(
            {
                "id": str(uuid.uuid4()),
                "operator_id": operator_id,
                "token_hash": self._hash_session_token(session_token),
                "created_at": self._iso(now),
                "last_seen_at": self._iso(now),
                "expires_at": self._iso(now + timedelta(days=SESSION_TTL_DAYS)),
                "invalidated_at": None,
            }
        )
        self._store_sessions(sessions)
        return session_token

    def _get_operator_by_username(self, username: str) -> Optional[dict[str, Any]]:
        normalized_username = username.strip().lower()
        for operator in self._load_operators():
            if operator.get("username") == normalized_username:
                return operator
        return None

    def _get_operator_by_id(self, operator_id: str) -> Optional[dict[str, Any]]:
        for operator in self._load_operators():
            if operator.get("id") == operator_id:
                return operator
        return None

    def _public_operator(self, operator: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": operator["id"],
            "username": operator["username"],
            "display_name": operator["display_name"],
            "email": operator.get("email") or None,
            "locale": operator.get("locale", "en"),
            "disabled": bool(operator.get("disabled", False)),
            "deleted": bool(operator.get("deleted", False)),
            "reset_password_eligible": bool(operator.get("reset_password_eligible", True)),
            "delete_eligible": not self._is_protected_bootstrap_operator(operator),
            "created_at": operator["created_at"],
        }

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
        return "$".join(
            [
                "pbkdf2_sha256",
                str(PASSWORD_HASH_ITERATIONS),
                base64.b64encode(salt).decode("utf-8"),
                base64.b64encode(digest).decode("utf-8"),
            ]
        )

    def _verify_password(self, password: str, encoded_hash: str) -> bool:
        try:
            _, iterations, salt_b64, digest_b64 = encoded_hash.split("$")
        except ValueError as exc:
            logger.error(f"Invalid password hash format: {exc}")
            return False

        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt_b64.encode("utf-8")),
            int(iterations),
        )
        return hmac.compare_digest(base64.b64encode(derived).decode("utf-8"), digest_b64)

    def _hash_session_token(self, session_token: str) -> str:
        session_secret = self._get_session_secret()
        return hmac.new(session_secret.encode("utf-8"), session_token.encode("utf-8"), hashlib.sha256).hexdigest()

    def _get_session_secret(self) -> str:
        self._ensure_storage()
        with self._db_connect() as connection:
            payload = connection.execute(
                "SELECT value FROM metadata WHERE key = ?",
                ("session_secret_payload",),
            ).fetchone()

        if payload is not None:
            decoded = self._decode_metadata_json(payload["value"], key="session_secret_payload")
            if isinstance(decoded, dict) and decoded.get("secret"):
                return str(decoded["secret"])

        secret = secrets.token_urlsafe(48)
        with self._db_connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("session_secret_payload", json.dumps({"secret": secret, "created_at": self._now_iso()}, ensure_ascii=True)),
            )
            connection.commit()
        return secret

    def _build_storage_boundary(self) -> dict[str, str]:
        return {
            "asset_group": "product-auth",
            "backup_scope": "product-owned",
            "separated_from_integrations": True,
        }

    def _append_audit(self, event: str, **payload: Any) -> None:
        self._ensure_storage()
        timestamp = self._now_iso()
        with self._db_connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (event, timestamp, payload) VALUES (?, ?, ?)",
                (event, timestamp, json.dumps(payload, ensure_ascii=True)),
            )
            connection.commit()

    def _ensure_storage(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._db_connect() as connection:
            self._initialize_schema(connection)

    def _db_connect(self) -> sqlite3.Connection:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS operators (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                locale TEXT NOT NULL DEFAULT 'en',
                password_hash TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0,
                created_by TEXT NOT NULL,
                reset_password_eligible INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                operator_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                invalidated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS favorites (
                operator_id TEXT NOT NULL,
                app_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (operator_id, app_key)
            );
            """
        )
        connection.execute("ALTER TABLE operators ADD COLUMN locale TEXT NOT NULL DEFAULT 'en'") if not self._column_exists(connection, "operators", "locale") else None
        connection.commit()

    def _load_operators(self) -> list[dict[str, Any]]:
        self._ensure_storage()
        with self._db_connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, display_name, password_hash, disabled, deleted,
                      created_by, reset_password_eligible, created_at, updated_at, locale
                FROM operators
                ORDER BY created_at, username
                """
            ).fetchall()
        return [self._operator_row_to_dict(row) for row in rows]

    def _store_operators(self, operators: list[dict[str, Any]]) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute("DELETE FROM operators")
            connection.executemany(
                """
                INSERT INTO operators (
                    id, username, display_name, locale, password_hash, disabled, deleted,
                    created_by, reset_password_eligible, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["username"],
                        item["display_name"],
                        item.get("locale", "en"),
                        item["password_hash"],
                        int(bool(item.get("disabled", False))),
                        int(bool(item.get("deleted", False))),
                        item.get("created_by", "bootstrap"),
                        int(bool(item.get("reset_password_eligible", True))),
                        item["created_at"],
                        item["updated_at"],
                    )
                    for item in operators
                ],
            )
            connection.commit()

    def _load_sessions(self) -> list[dict[str, Any]]:
        self._ensure_storage()
        with self._db_connect() as connection:
            rows = connection.execute(
                """
                SELECT id, operator_id, token_hash, created_at, last_seen_at, expires_at, invalidated_at
                FROM sessions
                ORDER BY created_at, id
                """
            ).fetchall()
        return [self._session_row_to_dict(row) for row in rows]

    def _store_sessions(self, sessions: list[dict[str, Any]]) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute("DELETE FROM sessions")
            connection.executemany(
                """
                INSERT INTO sessions (
                    id, operator_id, token_hash, created_at, last_seen_at, expires_at, invalidated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["operator_id"],
                        item["token_hash"],
                        item["created_at"],
                        item["last_seen_at"],
                        item["expires_at"],
                        item.get("invalidated_at"),
                    )
                    for item in sessions
                ],
            )
            connection.commit()

    def _decode_metadata_json(self, value: str, key: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse product auth metadata {key}: {exc}")
            raise CustomException(
                status_code=500,
                message="Product Authentication Storage Error",
                details=f"Unable to parse {key}",
            )

    def _operator_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "locale": row["locale"] if "locale" in row.keys() else "en",
            "password_hash": row["password_hash"],
            "disabled": bool(row["disabled"]),
            "deleted": bool(row["deleted"]),
            "created_by": row["created_by"],
            "reset_password_eligible": bool(row["reset_password_eligible"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _session_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "operator_id": row["operator_id"],
            "token_hash": row["token_hash"],
            "created_at": row["created_at"],
            "last_seen_at": row["last_seen_at"],
            "expires_at": row["expires_at"],
            "invalidated_at": row["invalidated_at"],
        }

    def _load_favorites(self, operator_id: str) -> list[str]:
        self._ensure_storage()
        with self._db_connect() as connection:
            rows = connection.execute(
                "SELECT app_key FROM favorites WHERE operator_id = ? ORDER BY created_at, app_key",
                (operator_id,),
            ).fetchall()
        return [str(row["app_key"]) for row in rows]

    def _column_exists(self, connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(str(row[1]) == column_name for row in rows)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._iso(self._now())

    def _iso(self, value: datetime) -> str:
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _parse_iso(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))