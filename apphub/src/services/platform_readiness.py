from __future__ import annotations

import configparser
import json
import os
import sqlite3
from pathlib import Path
from typing import Callable, Optional

import requests

from src.services.marketplace_bootstrap import MarketplaceBootstrapService

READINESS_PROBE_TIMEOUT_SECONDS = 2.0

# Keys reported in the `pending` list when a component is not ready yet.
SQLITE_PRODUCT_AUTH = "product-auth"
SQLITE_INSTALL_TRACKING = "install-tracking"
SQLITE_HOST_ACCESS = "host-access"
HTTP_GITEA = "gitea"
HTTP_PORTAINER = "portainer"
HTTP_NPM = "nginx-proxy-manager"
MARKER_GITEA_CREDENTIAL = "gitea-credential"
MARKER_PORTAINER_CREDENTIAL = "portainer-credential"
MARKER_NPM_CREDENTIAL = "npm-credential"
MARKER_NPM_CERTIFICATE = "npm-certificate"
MARKER_APPSTORE_MANIFEST = "appstore-manifest"
MARKER_APPSTORE_SYNC = "appstore-sync"
MARKER_APPSTORE_SYNC_FAILED = "appstore-sync-failed"
MARKER_MARKETPLACE_APP = "marketplace-app"


def _data_root() -> str:
    return os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")


def _sqlite_database_path(kind: str) -> Path:
    data_root = _data_root()
    if kind == SQLITE_PRODUCT_AUTH:
        directory = os.getenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", f"{data_root}/config/product-auth")
        return Path(directory) / "product-auth.sqlite"
    if kind == SQLITE_INSTALL_TRACKING:
        directory = os.getenv("WEBSOFT9_INSTALL_TRACKING_DIR", f"{data_root}/config/apphub")
        return Path(directory) / "install-tracking.sqlite"
    directory = os.getenv("WEBSOFT9_HOST_ACCESS_DATA_DIR", f"{data_root}/config/host-access")
    return Path(directory) / "host-access.sqlite"


def _appstore_manifest_paths() -> list[Path]:
    data_root = _data_root()
    config_path = Path(os.getenv("WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH", f"{data_root}/config/apphub/system.ini"))
    config = configparser.ConfigParser()
    config.read(config_path)
    media_path = config.get("app_media", "path", fallback=f"{data_root}/media/json").strip()
    return [Path(media_path) / f"app-store-manifest_{locale}.json" for locale in ("zh", "en")]


def _has_valid_appstore_manifests() -> bool:
    try:
        for locale, manifest_path in zip(("zh", "en"), _appstore_manifest_paths()):
            with manifest_path.open(encoding="utf-8") as handle:
                manifest = json.load(handle)
            if (
                not isinstance(manifest, dict)
                or manifest.get("schemaVersion") != "1"
                or manifest.get("locale") != locale
                or not isinstance(manifest.get("apps"), list)
            ):
                return False
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _appstore_contains_app(app_slug: str) -> bool:
    normalized_slug = str(app_slug or "").strip().lower()
    if not normalized_slug:
        return False

    try:
        for manifest_path in _appstore_manifest_paths():
            with manifest_path.open(encoding="utf-8") as handle:
                manifest = json.load(handle)
            if any(
                str(app.get("key") or "").strip().lower() == normalized_slug
                for app in manifest.get("apps", [])
                if isinstance(app, dict)
            ):
                return True
    except (OSError, json.JSONDecodeError):
        return False
    return False


def _read_appstore_startup_state() -> str:
    state_path = Path(
        os.getenv(
            "WEBSOFT9_APPSTORE_STARTUP_STATE_FILE",
            f"{_data_root()}/config/appstore_startup_state.json",
        )
    )
    try:
        with state_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        state = str(payload.get("state") or "").strip().lower()
        return state if state in {"completed", "failed", "running"} else "running"
    except (OSError, json.JSONDecodeError):
        return "running"


class PlatformReadinessService:
    """Aggregates the platform's full-readiness state.

    Every sub-check is side-effect free: SQLite databases are opened for a
    read-only probe and HTTP services are hit with short timeouts.  Any
    failure is reported as a `pending` component rather than raised, so the
    readiness endpoint itself never returns a bare 500.
    """

    def __init__(self, http_probe: Optional[Callable[[str], bool]] = None):
        self._http_probe = http_probe or self._probe_http

    def check(self) -> tuple[bool, list[str]]:
        pending: list[str] = []

        if not self._check_sqlite(_sqlite_database_path(SQLITE_PRODUCT_AUTH), "operators"):
            pending.append(SQLITE_PRODUCT_AUTH)
        if not self._check_sqlite(_sqlite_database_path(SQLITE_INSTALL_TRACKING), "install_tasks"):
            pending.append(SQLITE_INSTALL_TRACKING)
        if not self._check_sqlite(_sqlite_database_path(SQLITE_HOST_ACCESS), "host_profiles"):
            pending.append(SQLITE_HOST_ACCESS)

        if not self._http_probe(os.getenv("WEBSOFT9_GITEA_HEALTH_URL", "http://127.0.0.1:3001/")):
            pending.append(HTTP_GITEA)
        if not self._http_probe(os.getenv("WEBSOFT9_PORTAINER_HEALTH_URL", "http://127.0.0.1:9004/api/system/status")):
            pending.append(HTTP_PORTAINER)
        if not self._http_probe(os.getenv("WEBSOFT9_NPM_HEALTH_URL", "http://127.0.0.1:81/")):
            pending.append(HTTP_NPM)

        data_root = _data_root()
        if not Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", f"{data_root}/gitea/credential")).is_file():
            pending.append(MARKER_GITEA_CREDENTIAL)
        if not Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", f"{data_root}/portainer/credential")).is_file():
            pending.append(MARKER_PORTAINER_CREDENTIAL)
        if not Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", f"{data_root}/credential.json")).is_file():
            pending.append(MARKER_NPM_CREDENTIAL)
        if not Path(os.getenv("WEBSOFT9_NPM_CERT_MARKER", f"{data_root}/custom_ssl/websoft9-self-signed.cert")).is_file():
            pending.append(MARKER_NPM_CERTIFICATE)
        if not _has_valid_appstore_manifests():
            pending.append(MARKER_APPSTORE_MANIFEST)

        return (not pending, pending)

    def check_setup(self) -> tuple[bool, list[str]]:
        ready, pending = self.check()
        if not ready:
            return ready, pending

        marketplace = MarketplaceBootstrapService().read()
        if not marketplace:
            return True, []

        appstore_startup_state = _read_appstore_startup_state()
        if appstore_startup_state == "running":
            return False, [MARKER_APPSTORE_SYNC]
        if not _appstore_contains_app(str(marketplace.get("app_slug") or "")):
            if appstore_startup_state == "failed":
                return False, [MARKER_APPSTORE_SYNC_FAILED]
            return False, [MARKER_MARKETPLACE_APP]
        return True, []

    @staticmethod
    def _probe_http(url: str) -> bool:
        try:
            response = requests.get(url, timeout=READINESS_PROBE_TIMEOUT_SECONDS)
            return 200 <= response.status_code < 500
        except Exception:
            return False

    @staticmethod
    def _check_sqlite(database_file: Path, required_table: str) -> bool:
        try:
            if not database_file.is_file():
                return False
            connection = sqlite3.connect(str(database_file), timeout=1)
            try:
                row = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (required_table,),
                ).fetchone()
                return row is not None
            finally:
                connection.close()
        except Exception:
            return False
