import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger


DEFAULT_PRODUCT_AUTH_PROTECTED_MODULES = ["users", "files", "terminal", "services", "logs"]
PRODUCT_AUTH_COOKIE_NAME = "websoft9_operator_session"
SESSION_TTL_DAYS = 30
PASSWORD_HASH_ITERATIONS = 310_000


class ProductAuthService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR") or "/etc/custom/product-auth")
        self.operators_file = self.data_dir / "operators.json"
        self.sessions_file = self.data_dir / "sessions.json"
        self.session_secret_file = self.data_dir / "session-secret.json"
        self.audit_log_file = self.data_dir / "audit.log"

    def get_status(self, session_token: Optional[str] = None) -> dict[str, Any]:
        enabled = self.is_enabled()
        current_user = None
        if enabled and session_token:
            current_user = self._resolve_session(session_token)

        return {
            "enabled": enabled,
            "initialization_required": enabled and not self._has_active_operator(),
            "authenticated": current_user is not None,
            "protected_modules": self.get_protected_modules(),
            "current_user": current_user,
            "storage_boundary": self._build_storage_boundary(),
        }

    def initialize_first_operator(
        self,
        username: str,
        password: str,
        display_name: str,
        client_host: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[dict[str, Any], str]:
        self._assert_enabled()

        with self._lock:
            self._ensure_storage()
            operators = self._read_json(self.operators_file, default=[])
            if any(not item.get("deleted", False) for item in operators):
                raise CustomException(
                    status_code=409,
                    message="Initialization Not Allowed",
                    details="Product-side operator initialization has already been completed",
                )

            operator = self._build_operator(username=username, password=password, display_name=display_name)
            operators.append(operator)
            self._write_json(self.operators_file, operators)
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
            if operator is None or operator.get("deleted") or operator.get("disabled"):
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
            sessions = self._read_json(self.sessions_file, default=[])
            token_hash = self._hash_session_token(session_token)
            operator_id = None
            for session in sessions:
                if session.get("token_hash") != token_hash or session.get("invalidated_at"):
                    continue
                session["invalidated_at"] = self._now_iso()
                operator_id = session.get("operator_id")
                break

            self._write_json(self.sessions_file, sessions)
            self._append_audit(
                event="logout",
                operator_id=operator_id,
                client_host=client_host,
                user_agent=user_agent,
            )

        return self.get_status(session_token=None)

    def invalidate_sessions_for_operator(self, operator_id: str, reason: str) -> None:
        with self._lock:
            sessions = self._read_json(self.sessions_file, default=[])
            updated = False
            for session in sessions:
                if session.get("operator_id") != operator_id or session.get("invalidated_at"):
                    continue
                session["invalidated_at"] = self._now_iso()
                updated = True

            if updated:
                self._write_json(self.sessions_file, sessions)
                self._append_audit(event="session_invalidation", operator_id=operator_id, reason=reason)

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
        operators = self._read_json(self.operators_file, default=[])
        return any(not item.get("deleted", False) for item in operators)

    def _resolve_session(self, session_token: str) -> Optional[dict[str, Any]]:
        if not session_token:
            return None

        with self._lock:
            sessions = self._read_json(self.sessions_file, default=[])
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
                self._write_json(self.sessions_file, sessions)
                self._append_audit(event="session_expired", operator_id=matched_session.get("operator_id"))
                return None

            operator = self._get_operator_by_id(matched_session["operator_id"])
            if operator is None or operator.get("deleted") or operator.get("disabled"):
                matched_session["invalidated_at"] = self._now_iso()
                self._write_json(self.sessions_file, sessions)
                self._append_audit(
                    event="session_invalidation",
                    operator_id=matched_session.get("operator_id"),
                    reason="operator-unavailable",
                )
                return None

            matched_session["last_seen_at"] = self._now_iso()
            self._write_json(self.sessions_file, sessions)
            return self._public_operator(operator)

    def _build_operator(self, username: str, password: str, display_name: str) -> dict[str, Any]:
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
            "password_hash": self._hash_password(password),
            "disabled": False,
            "deleted": False,
            "created_by": "bootstrap",
            "reset_password_eligible": True,
            "created_at": now,
            "updated_at": now,
        }

    def _create_session(self, operator_id: str) -> str:
        sessions = self._read_json(self.sessions_file, default=[])
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
        self._write_json(self.sessions_file, sessions)
        return session_token

    def _get_operator_by_username(self, username: str) -> Optional[dict[str, Any]]:
        normalized_username = username.strip().lower()
        for operator in self._read_json(self.operators_file, default=[]):
            if operator.get("username") == normalized_username:
                return operator
        return None

    def _get_operator_by_id(self, operator_id: str) -> Optional[dict[str, Any]]:
        for operator in self._read_json(self.operators_file, default=[]):
            if operator.get("id") == operator_id:
                return operator
        return None

    def _public_operator(self, operator: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": operator["id"],
            "username": operator["username"],
            "display_name": operator["display_name"],
            "disabled": bool(operator.get("disabled", False)),
            "deleted": bool(operator.get("deleted", False)),
            "reset_password_eligible": bool(operator.get("reset_password_eligible", True)),
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
        payload = self._read_json(self.session_secret_file, default=None)
        if isinstance(payload, dict) and payload.get("secret"):
            return str(payload["secret"])

        secret = secrets.token_urlsafe(48)
        self._write_json(self.session_secret_file, {"secret": secret, "created_at": self._now_iso()})
        return secret

    def _build_storage_boundary(self) -> dict[str, str]:
        return {
            "asset_group": "product-auth",
            "backup_scope": "product-owned",
            "separated_from_integrations": True,
        }

    def _append_audit(self, event: str, **payload: Any) -> None:
        self._ensure_storage()
        record = {"event": event, "timestamp": self._now_iso(), **payload}
        with self.audit_log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _ensure_storage(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.operators_file.exists():
            self._write_json(self.operators_file, [])
        if not self.sessions_file.exists():
            self._write_json(self.sessions_file, [])

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse product auth file {path}: {exc}")
            raise CustomException(
                status_code=500,
                message="Product Authentication Storage Error",
                details=f"Unable to parse {path.name}",
            )

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._iso(self._now())

    def _iso(self, value: datetime) -> str:
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _parse_iso(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))