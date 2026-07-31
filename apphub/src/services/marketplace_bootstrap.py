from __future__ import annotations

from typing import Any

from src.core.config import ConfigManager


class MarketplaceBootstrapService:
    """Read/write marketplace setup-wizard config from config.ini."""

    def __init__(self):
        self._config = ConfigManager()

    def is_cloud_marketplace(self) -> bool:
        """Check whether this runtime is a cloud marketplace instance."""
        try:
            val = self._config.get_value("marketplace", "app_slug")
            return bool(val.strip())
        except Exception:
            return False

    def read(self) -> dict[str, Any]:
        """Return marketplace config as a dict, same contract as the old JSON reader."""
        try:
            app_slug = self._config.get_value("marketplace", "app_slug")
        except Exception:
            return {}

        app_slug = str(app_slug or "").strip().lower()
        if not app_slug:
            return {}

        result: dict[str, Any] = {"app_slug": app_slug}
        try:
            locale = self._config.get_value("marketplace", "default_locale")
            locale = str(locale or "").strip()
            if locale:
                result["default_locale"] = locale
        except Exception:
            pass

        return result

    def write(self, app_slug: str, locale: str | None = None) -> dict[str, str]:
        """Persist marketplace parameters to config.ini."""
        app_slug = str(app_slug or "").strip().lower()
        if not app_slug:
            raise ValueError("app_slug cannot be empty")

        self._config.set_value("marketplace", "app_slug", app_slug)
        if locale and str(locale).strip():
            self._config.set_value("marketplace", "default_locale", str(locale).strip())

        return {
            "app_slug": app_slug,
            "default_locale": str(locale).strip() if locale else "",
        }