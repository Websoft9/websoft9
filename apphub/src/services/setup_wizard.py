from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.exception import CustomException
from src.schemas.appInstall import Edition, appInstall
from src.schemas.setupWizard import SetupWizardError
from src.services.app_manager import AppManger
from src.services.app_status import appInstalling, appInstallingError
from src.services.common_check import install_validate
from src.services.marketplace_bootstrap import MarketplaceBootstrapService
from src.services.product_auth import ProductAuthService


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_app_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())
    if not normalized:
        normalized = "app"
    if not normalized[0].isalpha():
        normalized = f"app{normalized}"
    return normalized[:20]


class SetupWizardService:
    _lock = threading.RLock()

    def __init__(self, data_dir: str | None = None):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_SETUP_WIZARD_DATA_DIR") or f"{data_root}/config/setup-wizard")
        self.state_file = self.data_dir / "state.json"
        self.bootstrap = MarketplaceBootstrapService()

    def should_use_wizard(self) -> bool:
        metadata = self._read_marketplace_app_metadata()
        return bool(metadata.get("app_slug"))

    def require_enabled(self) -> None:
        if not self.should_use_wizard():
            raise CustomException(404, "Not Found", "The setup wizard is not available for this runtime")

    def is_pending_setup(self) -> bool:
        if not self.should_use_wizard():
            return False
        state = self._load_state()
        return not bool(state.get("completed"))

    def get_state(self, session_token: str | None = None) -> dict[str, Any]:
        base_state = self._load_state()
        app_slug = self.get_app_slug()
        if not self.should_use_wizard():
            return {
                "enabled": False,
                "current_step": "welcome",
                "app_slug": app_slug,
                "installed_app_id": None,
                "completed": False,
                "tracking_id": None,
                "pending_app_id": None,
                "last_error": None,
                "updated_at": _utc_now(),
                "completed_at": None,
            }

        status = ProductAuthService().get_status(session_token=session_token)
        current_step = str(base_state.get("current_step") or "welcome")
        completed = bool(base_state.get("completed"))

        if completed:
            current_step = "complete"
        elif status.get("authenticated"):
            if current_step not in {"app_init_running", "app_init_failed", "complete"}:
                current_step = "app_init_ready"
        elif current_step not in {"welcome", "platform_init"}:
            current_step = "welcome"

        last_error = base_state.get("last_error")
        return {
            "enabled": True,
            "current_step": current_step,
            "app_slug": app_slug,
            "installed_app_id": base_state.get("installed_app_id"),
            "completed": completed,
            "tracking_id": base_state.get("tracking_id"),
            "pending_app_id": base_state.get("pending_app_id"),
            "last_error": last_error,
            "updated_at": base_state.get("updated_at") or _utc_now(),
            "completed_at": base_state.get("completed_at"),
        }

    def get_app(self, locale: str | None = None) -> dict[str, Any]:
        self.require_enabled()
        app_slug = self.get_app_slug()
        if not app_slug:
            raise CustomException(404, "Marketplace App Not Found", "The marketplace app metadata is unavailable")

        app = None
        for catalog_locale in self._resolve_catalog_locales(locale):
            apps = AppManger().get_available_apps(catalog_locale)
            app = next((item for item in apps if str(item.get("key") or "").strip().lower() == app_slug), None)
            if app is not None:
                break
        if app is None:
            raise CustomException(404, "Marketplace App Not Found", f"The app '{app_slug}' was not found in the app catalog")

        settings = {
            str(key): "" if value is None else str(value)
            for key, value in (app.get("settings") or {}).items()
            if str(key).strip()
        }
        required_inputs = [
            {
                "name": key,
                "label": key,
                "type": "password" if "PASSWORD" in key.upper() else "number" if "PORT" in key.upper() else "text",
                "required": True,
                "default_value": value or None,
                "placeholder": None,
                "description": None,
            }
            for key, value in settings.items()
            if not str(value).strip()
        ]

        distribution = (app.get("distribution") or [{}])[0] or {}
        raw_version = distribution.get("value")
        edition = raw_version[0] if isinstance(raw_version, list) and raw_version else str(raw_version or "latest")

        return {
            "app_slug": app_slug,
            "display_name": str(app.get("trademark") or app_slug),
            "logo_url": str(((app.get("logo") or {}).get("imageurl") or "")).strip() or None,
            "edition": edition,
            "default_app_id": _normalize_app_id(app_slug),
            "is_web_app": bool(app.get("is_web_app")),
            "requires_user_inputs": len(required_inputs) > 0,
            "required_inputs": required_inputs,
            "settings": settings,
        }

    def mark_platform_init_complete(self, session_token: str | None = None) -> dict[str, Any]:
        self.require_enabled()
        self._require_authenticated(session_token)
        state = self._update_state(current_step="app_init_ready", last_error=None)
        return {
            "current_step": state["current_step"],
            "updated_at": state["updated_at"],
        }

    def install_app(self, payload: dict[str, Any], session_token: str | None = None, endpoint_id: int | None = None) -> dict[str, Any]:
        self.require_enabled()
        self._require_authenticated(session_token)
        app_info = self.get_app()
        settings = dict(app_info.get("settings") or {})
        for key, value in (payload.get("user_inputs") or {}).items():
            settings[str(key)] = str(value)

        install_payload = appInstall(
            app_name=app_info["app_slug"],
            edition=Edition(dist="community", version=str(payload.get("edition") or app_info["edition"])),
            app_id=str(payload.get("app_id") or app_info["default_app_id"]),
            proxy_enabled=False,
            domain_names=[str(payload.get("domain_name"))],
            settings=settings,
        )

        # Reuse the same precheck pipeline as /apps/install to fail fast
        # before long-running image pull and stack creation steps.
        install_validate(install_payload, endpoint_id)

        app_manager = AppManger()
        tracked_app_id, tracking_id = app_manager.create_installation_tracking(install_payload)

        from threading import Thread

        Thread(target=app_manager.install_app, args=(install_payload, endpoint_id, tracked_app_id, tracking_id), daemon=True).start()
        self._update_state(
            current_step="app_init_running",
            tracking_id=tracking_id,
            pending_app_id=tracked_app_id,
            installed_app_id=None,
            last_error=None,
        )
        return {
            "tracking_id": tracking_id,
            "current_step": "app_init_running",
        }

    def get_install_status(self, tracking_id: str) -> dict[str, Any]:
        self.require_enabled()
        state = self._load_state()
        pending_app_id = state.get("pending_app_id")
        if state.get("tracking_id") != tracking_id:
            raise CustomException(404, "Install Task Not Found", "The requested setup-wizard install task was not found")

        running_task = appInstalling.get(tracking_id)
        if running_task is not None:
            return {
                "status": "running",
                "current_step": "app_init_running",
                "installed_app_id": None,
                "last_error": None,
            }

        failed_task = appInstallingError.get(tracking_id)
        if failed_task is not None:
            error = {
                "code": "INSTALL_TASK_FAILED",
                "message": str(failed_task.get("error") or "准备失败，请重试。"),
                "retryable": True,
                "field_names": [],
            }
            self._update_state(current_step="app_init_failed", last_error=error)
            return {
                "status": "failed",
                "current_step": "app_init_failed",
                "installed_app_id": None,
                "last_error": error,
            }

        app_id = str(state.get("installed_app_id") or pending_app_id or "").strip()
        if app_id:
            try:
                AppManger().get_app_by_id(app_id)
                return {
                    "status": "succeeded",
                    "current_step": "complete",
                    "installed_app_id": app_id,
                    "last_error": None,
                }
            except Exception:
                pass

        return {
            "status": "running",
            "current_step": "app_init_running",
            "installed_app_id": None,
            "last_error": None,
        }

    def complete(self, session_token: str | None = None) -> dict[str, Any]:
        self.require_enabled()
        self._require_authenticated(session_token)
        state = self._load_state()
        installed_app_id = str(state.get("installed_app_id") or state.get("pending_app_id") or "").strip()
        if not installed_app_id:
            raise CustomException(400, "Invalid Request", "The setup wizard has no installed app to complete")

        completed_at = _utc_now()
        next_state = self._update_state(
            current_step="complete",
            completed=True,
            installed_app_id=installed_app_id,
            completed_at=completed_at,
            tracking_id=state.get("tracking_id"),
            pending_app_id=installed_app_id,
            last_error=None,
        )
        return {
            "current_step": next_state["current_step"],
            "installed_app_id": installed_app_id,
            "completed": True,
            "completed_at": completed_at,
        }

    def get_app_slug(self) -> str | None:
        metadata = self._read_marketplace_app_metadata()
        app_slug = str(metadata.get("app_slug") or "").strip().lower()
        return app_slug or None

    def _require_authenticated(self, session_token: str | None) -> dict[str, Any]:
        status = ProductAuthService().get_status(session_token=session_token)
        if not status.get("authenticated"):
            raise CustomException(401, "Authentication Required", "Sign in before continuing the setup wizard")
        return status

    def _read_marketplace_app_metadata(self) -> dict[str, Any]:
        return self.bootstrap.read()

    def _resolve_catalog_locales(self, locale: str | None) -> list[str]:
        preferred_locale = "zh" if str(locale or "").strip().lower().startswith("zh") else "en"
        locales = [preferred_locale]
        for fallback_locale in ("en", "zh"):
            if fallback_locale not in locales:
                locales.append(fallback_locale)
        return locales

    def _default_state(self) -> dict[str, Any]:
        return {
            "current_step": "welcome",
            "installed_app_id": None,
            "completed": False,
            "tracking_id": None,
            "pending_app_id": None,
            "last_error": None,
            "updated_at": _utc_now(),
            "completed_at": None,
        }

    def _load_state(self) -> dict[str, Any]:
        with self._lock:
            if not self.state_file.exists():
                return self._default_state()
            try:
                payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                return self._default_state()
            if not isinstance(payload, dict):
                return self._default_state()
            state = self._default_state()
            state.update(payload)
            return state

    def _write_state(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return state

    def _update_state(self, **changes: Any) -> dict[str, Any]:
        state = self._load_state()
        state.update(changes)
        state["updated_at"] = _utc_now()
        return self._write_state(state)