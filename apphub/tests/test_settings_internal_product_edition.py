import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Importing the app modules initialises the install-tracking store; keep it away from the
# host's real data root so a test run can never touch a live deployment.
os.environ.setdefault("WEBSOFT9_INSTALL_TRACKING_DIR", tempfile.mkdtemp(prefix="w9-tracking-"))


settings_summary_module = types.ModuleType("src.schemas.settingsSummary")


class _SettingsSummaryResponse(BaseModel):
    pass


settings_summary_module.SettingsSummaryResponse = _SettingsSummaryResponse
sys.modules.setdefault("src.schemas.settingsSummary", settings_summary_module)

settings_manager_module = types.ModuleType("src.services.settings_manager")


class _SettingsManager:
    def read_all(self):
        return {}

    def read_summary(self):
        return {}

    def read_section(self, _section):
        return {}

    def write_section(self, _section, _key, _value):
        return {}

    def write_platform_gateway_settings(self, **_kwargs):
        return {}

    def generate_self_signed_cert(self, **_kwargs):
        return {}

    def apply_letsencrypt_cert(self, **_kwargs):
        return {}

    def upload_cert(self, **_kwargs):
        return {}


settings_manager_module.SettingsManager = _SettingsManager
sys.modules.setdefault("src.services.settings_manager", settings_manager_module)

from src.api.v1.routers import settings as settings_router
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.services.product_runtime_state import ProductRuntimeState


@pytest.fixture(autouse=True)
def _isolated_runtime_data_root(tmp_path, monkeypatch):
    """These tests drive the HTTP API, so keep the runtime on a throwaway data root instead of
    writing into the host's real /opt/websoft9/data."""
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))


def create_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(CustomException)
    async def custom_exception_handler(_request, exc: CustomException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(message=exc.message, details=exc.details).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(message="Validation Error", details=str(exc)).model_dump(),
        )

    app.include_router(settings_router.router)
    return app


def _runtime_state(*, edition_key: str, updated_by: str, note: Optional[str] = None) -> ProductRuntimeState:
    edition_name = {
        "free": "Free",
        "starter": "Starter",
        "standard": "Standard",
        "enterprise": "Enterprise",
    }[edition_key]
    max_apps = {
        "free": 2,
        "starter": 3,
        "standard": 10,
        "enterprise": None,
    }[edition_key]
    return ProductRuntimeState(
        version="2.3.0",
        edition_key=edition_key,
        edition_name=edition_name,
        edition_names={"en": edition_name},
        max_apps=max_apps,
        state_source="manual-support",
        updated_by=updated_by,
        updated_at="2026-06-16T00:00:00Z",
        note=note,
    )


def test_internal_product_edition_requires_authenticated_operator(monkeypatch):
    app = create_test_app()
    client = TestClient(app)

    class RejectingAuthService:
        def _require_authenticated_operator(self, _session_token):
            raise CustomException(status_code=401, message="Authentication Required", details="Operator session is required")

    monkeypatch.setattr(settings_router, "ProductAuthService", RejectingAuthService)

    response = client.get("/settings/internal/product-edition")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication Required"


def test_internal_product_edition_allows_authenticated_operator_read(monkeypatch):
    app = create_test_app()
    client = TestClient(app)

    class AuthenticatedAuthService:
        def _require_authenticated_operator(self, _session_token):
            return {"id": "user-1", "username": "alice", "delete_eligible": True}

    monkeypatch.setattr(settings_router, "ProductAuthService", AuthenticatedAuthService)
    monkeypatch.setattr(settings_router, "read_product_runtime_state", lambda: _runtime_state(edition_key="free", updated_by="system"))

    response = client.get("/settings/internal/product-edition", cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"})

    assert response.status_code == 200
    assert response.json()["edition_key"] == "free"
    assert response.json()["updated_by"] == "system"


def _stub_release_checker(monkeypatch, version):
    class StubChecker:
        def ensure_latest_version(self, **_kwargs):
            return version

    monkeypatch.setattr(settings_router, "ReleaseVersionChecker", StubChecker)


def test_upgrade_status_does_not_recommend_release_candidate(monkeypatch):
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.3.3")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "release")
    _stub_release_checker(monkeypatch, "2.3.4-rc.1")

    status = settings_router.get_upgrade_status()

    assert status["latest_version"] == "2.3.4-rc.1"
    assert status["upgrade_available"] is False


def test_upgrade_status_keeps_stable_release_recommendation(monkeypatch):
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.3.3")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "release")
    _stub_release_checker(monkeypatch, "2.3.4")

    status = settings_router.get_upgrade_status()

    assert status["upgrade_available"] is True


def test_upgrade_status_does_not_recommend_an_older_release(monkeypatch):
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.2")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")
    _stub_release_checker(monkeypatch, "2.4.1")

    status = settings_router.get_upgrade_status()

    assert status["latest_version"] == "2.4.1"
    assert status["upgrade_available"] is False


def _authenticated_auth_service():
    class AuthenticatedAuthService:
        def _require_authenticated_operator(self, _session_token):
            return {"id": "op-1", "username": "admin"}

    return AuthenticatedAuthService


def _rejecting_auth_service():
    class RejectingAuthService:
        def _require_authenticated_operator(self, _session_token):
            raise CustomException(401, "Unauthorized", "Authentication required")

    return RejectingAuthService


def test_upgrade_status_is_readable_without_a_session(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.1")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")
    _stub_release_checker(monkeypatch, "2.4.2")

    response = client.get("/settings/upgrade/status")

    assert response.status_code == 200
    assert response.json()["upgrade_available"] is True


def test_upgrade_status_never_waits_for_the_full_network_timeout(monkeypatch):
    captured = []

    class StubChecker:
        def ensure_latest_version(self, **kwargs):
            captured.append(kwargs)
            return "2.4.2"

    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ReleaseVersionChecker", StubChecker)
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.1")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")

    client.get("/settings/upgrade/status")

    # A plain status read is on the console's hot path, so it must stay on the short timeout.
    assert captured == [{"channel": "dev", "force": False, "background": False}]


def test_upgrade_prepare_requires_an_authenticated_operator(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _rejecting_auth_service())

    response = client.post("/settings/upgrade/prepare")

    assert response.status_code == 401


def test_upgrade_prepare_reports_a_conflict_while_another_job_holds_the_lock(tmp_path, monkeypatch):
    from src.services.upgrade_manager import UpgradeManager

    app = create_test_app()
    client = TestClient(app)
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "UpgradeManager", lambda: manager)

    held = manager._acquire_lock()
    try:
        response = client.post(
            "/settings/upgrade/prepare",
            cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
        )
    finally:
        manager._release_lock(held)

    assert response.status_code == 409
    assert "already active" in response.json()["details"]


def test_upgrade_apply_requires_a_prepared_task(tmp_path, monkeypatch):
    from src.services.upgrade_manager import UpgradeManager

    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "UpgradeManager", lambda: UpgradeManager(data_root=str(tmp_path / "data")))

    response = client.post(
        "/settings/upgrade/apply",
        cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
    )

    assert response.status_code == 409
    assert "Prepare a newer version" in response.json()["details"]


def test_upgrade_check_requires_an_authenticated_operator(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _rejecting_auth_service())

    response = client.post("/settings/upgrade/check")

    assert response.status_code == 401


def test_internal_upgrade_dispatch_requires_the_platform_secret(tmp_path, monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    secret_file = tmp_path / "trust_key"
    secret_file.write_text("dispatch-secret\n", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret_file))

    response = client.post("/settings/internal/upgrade/auto-prepare")

    assert response.status_code == 403


def test_internal_upgrade_dispatch_starts_the_apphub_download(tmp_path, monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    secret_file = tmp_path / "trust_key"
    secret_file.write_text("dispatch-secret\n", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret_file))
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")
    _stub_release_checker(monkeypatch, "2.4.4")
    started = []
    monkeypatch.setattr(
        settings_router.upgrade_manager,
        "maybe_start_auto_download",
        lambda *, latest_version: started.append(latest_version) or True,
    )

    response = client.post(
        "/settings/internal/upgrade/auto-prepare",
        headers={settings_router.UPGRADE_DISPATCH_SECRET_HEADER: "dispatch-secret"},
    )

    assert response.status_code == 202
    assert response.json() == {"started": True}
    assert started == ["2.4.4"]


def test_upgrade_log_requires_an_authenticated_operator(monkeypatch):
    """A log names internal paths and image digests, so it is not a public read."""
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _rejecting_auth_service())

    response = client.get("/settings/upgrade/logs", params={"run_id": "run-1"})

    assert response.status_code == 401


def test_upgrade_log_returns_the_requested_tail(tmp_path, monkeypatch):
    from src.services.upgrade_manager import UpgradeManager

    app = create_test_app()
    client = TestClient(app)
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    log_dir = manager.upgrade_root / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "run-1.log").write_text("first\nsecond\nthird\n", encoding="utf-8")
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "UpgradeManager", lambda: manager)

    response = client.get(
        "/settings/upgrade/logs",
        params={"run_id": "run-1", "tail": 2},
        cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "file"
    assert payload["lines"] == ["second", "third"]


def test_upgrade_log_rejects_a_run_id_that_is_a_path(tmp_path, monkeypatch):
    from src.services.upgrade_manager import UpgradeManager

    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "UpgradeManager", lambda: UpgradeManager(data_root=str(tmp_path / "data")))

    response = client.get(
        "/settings/upgrade/logs",
        params={"run_id": "../../etc/passwd"},
        cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
    )

    assert response.status_code == 400


def test_upgrade_check_forces_a_fresh_release_lookup(monkeypatch):
    captured = []

    class StubChecker:
        def ensure_latest_version(self, **kwargs):
            captured.append(kwargs)
            return "2.4.2"

    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "ReleaseVersionChecker", StubChecker)
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.1")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")

    response = client.post(
        "/settings/upgrade/check",
        cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
    )

    assert response.status_code == 200
    # The operator asked for a fresh answer, so this call may skip the cache and wait longer.
    assert captured == [{"channel": "dev", "force": True, "background": True}]


def test_upgrade_check_only_reports_a_newer_release(monkeypatch):
    """Checking for updates must stay read-only so the operator still sees the download action."""

    class StubChecker:
        def ensure_latest_version(self, **_kwargs):
            return "2.4.2"

    class StubManager:
        def status(self, **_kwargs):
            return {"state": "idle"}

    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(settings_router, "ProductAuthService", _authenticated_auth_service())
    monkeypatch.setattr(settings_router, "ReleaseVersionChecker", StubChecker)
    monkeypatch.setattr(settings_router, "UpgradeManager", StubManager)
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.1")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")

    response = client.post(
        "/settings/upgrade/check",
        cookies={settings_router.PRODUCT_AUTH_COOKIE_NAME: "valid-session"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upgrade_available"] is True
    assert payload["state"] == "idle"
    # The endpoint must never stage anything by itself: the auto-download hook is not even
    # reachable from this router anymore.
    assert not hasattr(settings_router, "maybe_start_auto_download")


def test_upgrade_status_survives_a_corrupt_state_file(tmp_path, monkeypatch):
    from src.services.upgrade_manager import UpgradeManager

    app = create_test_app()
    client = TestClient(app)
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager.upgrade_root.mkdir(parents=True, exist_ok=True)
    manager.state_file.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(settings_router, "UpgradeManager", lambda: manager)
    monkeypatch.setattr(settings_router, "read_release_version", lambda: "2.4.1")
    monkeypatch.setattr(settings_router, "read_release_channel", lambda: "dev")
    _stub_release_checker(monkeypatch, "2.4.2")

    response = client.get("/settings/upgrade/status")

    assert response.status_code == 200
    assert response.json()["state"] == "idle"


def test_disabling_https_clears_secure_product_session_before_gateway_restart(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    manager = _GatewaySettingsManager(https_enabled=True)
    monkeypatch.setattr(settings_router, "SettingsManager", lambda: manager)

    response = client.put(
        "/settings/platform_gateway/apply",
        headers={"X-Forwarded-Proto": "https"},
        json={"bound_domain": "", "https_enabled": "false", "force_https": "false", "ssl_cert": "", "ssl_key": ""},
    )

    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert manager.restart_calls == 1
    assert manager.write_calls == [{"restart_gateway": False}]


def test_other_gateway_settings_changes_do_not_clear_product_session(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    manager = _GatewaySettingsManager(https_enabled=True)
    monkeypatch.setattr(settings_router, "SettingsManager", lambda: manager)

    response = client.put(
        "/settings/platform_gateway/apply",
        headers={"X-Forwarded-Proto": "https"},
        json={"bound_domain": "", "https_enabled": "true", "force_https": "false", "ssl_cert": "", "ssl_key": ""},
    )

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert manager.restart_calls == 1


class _GatewaySettingsManager:
    def __init__(self, *, https_enabled: bool):
        self.https_enabled = https_enabled
        self.restart_calls = 0
        self.write_calls = []

    def _is_platform_https_enabled(self):
        return self.https_enabled

    def _parse_bool(self, value: str):
        return value == "true"

    def write_platform_gateway_settings(self, **kwargs):
        self.write_calls.append({"restart_gateway": kwargs["restart_gateway"]})
        return {"platform_gateway": "updated"}

    def _restart_platform_gateway(self):
        self.restart_calls += 1