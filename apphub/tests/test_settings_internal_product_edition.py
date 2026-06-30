import sys
import types
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
        version="3.0.0",
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