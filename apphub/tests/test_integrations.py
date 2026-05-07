import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import integrations as integrations_router
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.services.integration_session_bridge import IntegrationSessionBridge


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
        errors = ", ".join(f"{err['loc'][1]}: {err['msg']}" for err in exc.errors())
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(message="Request Validation Error", details=errors).model_dump(),
        )

    app.include_router(integrations_router.router)
    return app


def test_bulk_integration_bootstrap_sets_cookies(monkeypatch):
    def fake_bootstrap_all(self, locale=None):
        assert locale == "zh-CN"
        return {
            "status": "ok",
            "integrations": {
                "gitea": {"status": "ok", "cookies": 1},
                "portainer": {"status": "ok", "cookies": 1},
                "npm": {"status": "ok", "cookies": 1},
            },
            "cookies": [
                {"name": "i_like_gitea", "value": "gitea-cookie", "path": "/w9git", "httponly": False},
                {"name": "portainer_jwt", "value": "portainer-token", "path": "/", "httponly": True},
                {"name": "nginx_tokens", "value": "npm-token", "path": "/", "httponly": False},
            ],
        }

    monkeypatch.setattr(IntegrationSessionBridge, "bootstrap_all", fake_bootstrap_all)
    app = create_test_app()

    with TestClient(app) as client:
        response = client.post("/integrations/session", headers={"X-Websoft9-Locale": "zh-CN"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["integrations"]["portainer"]["status"] == "ok"
    set_cookie = response.headers.get("set-cookie", "")
    assert "i_like_gitea=gitea-cookie" in set_cookie
    assert "portainer_jwt=portainer-token" in set_cookie


def test_bulk_integration_bootstrap_isolates_partial_failure(monkeypatch):
    def fake_bootstrap_all(self, locale=None):
        return {
            "status": "partial",
            "integrations": {
                "gitea": {"status": "ok", "cookies": 1},
                "portainer": {"status": "error", "message": "Unable to establish Portainer session"},
                "npm": {"status": "ok", "cookies": 1},
            },
            "cookies": [
                {"name": "i_like_gitea", "value": "gitea-cookie", "path": "/w9git", "httponly": False},
                {"name": "nginx_tokens", "value": "npm-token", "path": "/", "httponly": False},
            ],
        }

    monkeypatch.setattr(IntegrationSessionBridge, "bootstrap_all", fake_bootstrap_all)
    app = create_test_app()

    with TestClient(app) as client:
        response = client.post("/integrations/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["integrations"]["gitea"]["status"] == "ok"
    assert payload["integrations"]["portainer"]["status"] == "error"
    assert payload["integrations"]["portainer"]["message"] == "Unable to establish Portainer session"