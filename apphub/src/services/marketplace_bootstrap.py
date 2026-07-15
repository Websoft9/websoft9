from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_BOOTSTRAP_PATH = Path("/websoft9/marketplace/bootstrap.json")
REPO_BOOTSTRAP_PATH = REPO_ROOT / "marketplace" / "bootstrap.json"


def get_marketplace_bootstrap_path() -> Path:
    if RUNTIME_BOOTSTRAP_PATH.exists() or RUNTIME_BOOTSTRAP_PATH.parent.exists():
        return RUNTIME_BOOTSTRAP_PATH
    return REPO_BOOTSTRAP_PATH


class MarketplaceBootstrapService:
    def __init__(self, file_path: Path | None = None):
        self.file_path = file_path or get_marketplace_bootstrap_path()

    def read(self) -> dict[str, Any]:
        try:
            raw = self.file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}

        if not isinstance(payload, dict):
            return {}

        app_slug = str(payload.get("app_slug") or "").strip().lower()
        if not app_slug:
            return {}

        result: dict[str, Any] = {"app_slug": app_slug}
        locale = str(payload.get("default_locale") or "").strip()
        if locale:
            result["default_locale"] = locale
        return result

    def write(self, app_slug: str, locale: str | None = None) -> dict[str, str]:
        payload: dict[str, str] = {
            "app_slug": str(app_slug or "").strip().lower(),
        }
        if locale and str(locale).strip():
            payload["default_locale"] = str(locale).strip()
        if not payload["app_slug"]:
            raise ValueError("app_slug cannot be empty")
            raise ValueError("app_slug cannot be empty")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return payload