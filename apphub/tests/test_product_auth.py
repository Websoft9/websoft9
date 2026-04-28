import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import auth as auth_router
from src.core.request_auth import has_valid_internal_gateway_auth
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.services.product_auth import ProductAuthService
from fastapi.responses import JSONResponse


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

    app.include_router(auth_router.router)
    return app


def test_product_auth_status_requires_initialization(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        response = client.get("/auth/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["initialization_required"] is True
    assert payload["authenticated"] is False
    assert payload["protected_modules"] == ["users", "files", "terminal", "services", "logs"]


def test_product_auth_initialize_login_session_and_logout(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200
        initialize_payload = initialize_response.json()
        assert initialize_payload["authenticated"] is True
        assert initialize_payload["initialization_required"] is False
        assert initialize_payload["current_user"]["username"] == "admin"

        session_response = client.get("/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is True

        second_initialize_response = client.post(
            "/auth/initialize",
            json={"username": "second", "password": "StrongPass123!", "display_name": "Second Admin"},
        )
        assert second_initialize_response.status_code == 409

        logout_response = client.post("/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json()["authenticated"] is False

        invalid_login_response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "WrongPass123!"},
        )
        assert invalid_login_response.status_code == 401

        login_response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "StrongPass123!"},
        )
        assert login_response.status_code == 200
        login_payload = login_response.json()
        assert login_payload["authenticated"] is True
        assert login_payload["current_user"]["display_name"] == "Platform Admin"

        final_session_response = client.get("/auth/session")
        assert final_session_response.status_code == 200
        assert final_session_response.json()["authenticated"] is True


def test_product_auth_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "false")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        status_response = client.get("/auth/status")
        assert status_response.status_code == 200
        assert status_response.json()["enabled"] is False

        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

    assert initialize_response.status_code == 403
    assert initialize_response.json()["message"] == "Product Authentication Disabled"


def test_product_auth_status_hides_internal_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        response = client.get("/auth/status")

    assert response.status_code == 200
    assert response.json()["storage_boundary"] == {
        "asset_group": "product-auth",
        "backup_scope": "product-owned",
        "separated_from_integrations": True,
    }


def test_product_auth_initialize_sets_secure_cookie_on_https(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/auth/initialize",
            headers={"x-forwarded-proto": "https"},
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_internal_gateway_auth_requires_matching_secret():
    assert has_valid_internal_gateway_auth({"x-websoft9-internal-request": "1"}, "shared-secret") is False
    assert has_valid_internal_gateway_auth(
        {"x-websoft9-internal-request": "1", "x-websoft9-internal-secret": "wrong-secret"},
        "shared-secret",
    ) is False
    assert has_valid_internal_gateway_auth(
        {"x-websoft9-internal-request": "1", "x-websoft9-internal-secret": "shared-secret"},
        "shared-secret",
    ) is True


def test_product_auth_respects_configured_protected_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_PROTECTED_MODULES", "users,logs")

    app = create_test_app()

    with TestClient(app) as client:
        response = client.get("/auth/status")

    assert response.status_code == 200
    assert response.json()["protected_modules"] == ["users", "logs"]


def test_product_auth_rejects_blank_or_trimmed_short_identity_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        blank_display_name = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "   "},
        )
        short_username = client.post(
            "/auth/initialize",
            json={"username": "  a ", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

    assert blank_display_name.status_code == 400
    assert "Display name" in blank_display_name.json()["details"]
    assert short_username.status_code == 400
    assert "Username" in short_username.json()["details"]


def test_product_auth_invalidates_existing_session_when_operator_is_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()
    service = ProductAuthService(str(tmp_path))

    with TestClient(app) as client:
        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

        assert initialize_response.status_code == 200
        operator_id = initialize_response.json()["current_user"]["id"]

        operators = service._read_json(service.operators_file, default=[])
        operators[0]["disabled"] = True
        service._write_json(service.operators_file, operators)
        service.invalidate_sessions_for_operator(operator_id, "disabled-by-test")

        session_response = client.get("/auth/session")

    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False