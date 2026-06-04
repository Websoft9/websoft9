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


def test_product_auth_blank_display_name_falls_back_to_username(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "   "},
        )

    assert response.status_code == 200
    assert response.json()["current_user"]["display_name"] == "admin"


def test_product_auth_rejects_short_username(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/auth/initialize",
            json={"username": "  a ", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

    assert response.status_code == 400
    assert "Username" in response.json()["details"]


def test_product_auth_rejects_weak_passwords(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        weak_initialize = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "weakpass", "display_name": "Platform Admin"},
        )

        assert weak_initialize.status_code == 400
        assert "uppercase, lowercase, number, and special character" in weak_initialize.json()["details"]

        initialize = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize.status_code == 200

        weak_create = client.post(
            "/auth/users",
            json={"username": "operator", "password": "Strongpass", "display_name": "Operator"},
        )
        assert weak_create.status_code == 400
        assert "uppercase, lowercase, number, and special character" in weak_create.json()["details"]

        create_user = client.post(
            "/auth/users",
            json={"username": "operator", "password": "StrongPass123!", "display_name": "Operator"},
        )
        assert create_user.status_code == 200

        weak_reset = client.post(
            f"/auth/users/{create_user.json()['id']}/reset-password",
            json={"password": "passwordonly"},
        )
        assert weak_reset.status_code == 400
        assert "uppercase, lowercase, number, and special character" in weak_reset.json()["details"]


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

        operators = service._load_operators()
        operators[0]["disabled"] = True
        service._store_operators(operators)
        service.invalidate_sessions_for_operator(operator_id, "disabled-by-test")

        session_response = client.get("/auth/session")

    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False


    def test_product_auth_creates_sqlite_storage(monkeypatch, tmp_path):
        monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
        monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

        service = ProductAuthService(str(tmp_path))
        service.get_status()

        assert service.database_file.exists() is True


def test_product_auth_user_management_crud_and_session_invalidation(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as admin_client:
        initialize_response = admin_client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )

        assert initialize_response.status_code == 200

        create_response = admin_client.post(
            "/auth/users",
            json={"username": "alice", "password": "StrongPass123!", "display_name": "Alice Operator", "disabled": True},
        )
        assert create_response.status_code == 200
        alice_id = create_response.json()["id"]
        assert create_response.json()["disabled"] is True

        enable_response = admin_client.put(
            f"/auth/users/{alice_id}",
            json={"display_name": "Alice Operator", "locale": "en", "disabled": False},
        )
        assert enable_response.status_code == 200
        assert enable_response.json()["disabled"] is False

        update_response = admin_client.put(
            f"/auth/users/{alice_id}",
            json={"display_name": "Alice Updated", "locale": "en", "disabled": False},
        )
        assert update_response.status_code == 200
        assert update_response.json()["username"] == "alice"
        assert update_response.json()["display_name"] == "Alice Updated"

        list_response = admin_client.get("/auth/users")
        assert list_response.status_code == 200
        assert [item["username"] for item in list_response.json()["users"]] == ["admin", "alice"]

        with TestClient(app) as alice_client:
            login_response = alice_client.post(
                "/auth/login",
                json={"username": "alice", "password": "StrongPass123!"},
            )
            assert login_response.status_code == 200

            reset_response = admin_client.post(
                f"/auth/users/{alice_id}/reset-password",
                json={"password": "NewPass456!"},
            )
            assert reset_response.status_code == 200

            alice_session_after_reset = alice_client.get("/auth/session")
            assert alice_session_after_reset.status_code == 200
            assert alice_session_after_reset.json()["authenticated"] is False

            old_password_login = alice_client.post(
                "/auth/login",
                json={"username": "alice", "password": "StrongPass123!"},
            )
            assert old_password_login.status_code == 401

            new_password_login = alice_client.post(
                "/auth/login",
                json={"username": "alice", "password": "NewPass456!"},
            )
            assert new_password_login.status_code == 200

            disable_response = admin_client.post(f"/auth/users/{alice_id}/disable")
            assert disable_response.status_code == 200
            assert disable_response.json()["disabled"] is True

            alice_session_after_disable = alice_client.get("/auth/session")
            assert alice_session_after_disable.status_code == 200
            assert alice_session_after_disable.json()["authenticated"] is False

            disabled_login = alice_client.post(
                "/auth/login",
                json={"username": "alice", "password": "NewPass456!"},
            )
            assert disabled_login.status_code == 403
            assert disabled_login.json()["details"] == "User account is disabled"

        delete_response = admin_client.delete(f"/auth/users/{alice_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] is True

        final_list_response = admin_client.get("/auth/users")
        assert final_list_response.status_code == 200
        assert [item["username"] for item in final_list_response.json()["users"]] == ["admin"]


def test_product_auth_persists_locale_and_favorites_and_can_reenable_user(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as admin_client:
        initialize_response = admin_client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin", "locale": "zh-CN"},
        )
        assert initialize_response.status_code == 200
        assert initialize_response.json()["current_user"]["locale"] == "zh-CN"

        create_response = admin_client.post(
            "/auth/users",
            json={"username": "alice", "password": "StrongPass123!", "display_name": "Alice User", "locale": "en"},
        )
        assert create_response.status_code == 200
        alice_id = create_response.json()["id"]
        assert create_response.json()["locale"] == "en"

        update_response = admin_client.put(
            f"/auth/users/{alice_id}",
            json={"display_name": "Alice Updated", "locale": "zh-CN"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["locale"] == "zh-CN"

        disable_response = admin_client.post(f"/auth/users/{alice_id}/disable")
        assert disable_response.status_code == 200
        assert disable_response.json()["disabled"] is True

        enable_response = admin_client.post(f"/auth/users/{alice_id}/enable")
        assert enable_response.status_code == 200
        assert enable_response.json()["disabled"] is False

        add_favorite_response = admin_client.post("/auth/favorites", json={"app_key": "wordpress"})
        assert add_favorite_response.status_code == 200
        assert add_favorite_response.json()["favorites"] == ["wordpress"]

        list_favorites_response = admin_client.get("/auth/favorites")
        assert list_favorites_response.status_code == 200
        assert list_favorites_response.json()["favorites"] == ["wordpress"]

        remove_favorite_response = admin_client.delete("/auth/favorites/wordpress")
        assert remove_favorite_response.status_code == 200
        assert remove_favorite_response.json()["favorites"] == []


def test_product_auth_user_management_requires_session_and_rejects_duplicate_username(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        unauthenticated_list = client.get("/auth/users")
        assert unauthenticated_list.status_code == 401

        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200

        duplicate_response = client.post(
            "/auth/users",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Second Admin"},
        )
        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["message"] == "Operator Already Exists"

        create_response = client.post(
            "/auth/users",
            json={"username": "alice", "password": "StrongPass123!", "display_name": "Alice Admin"},
        )
        assert create_response.status_code == 200

        update_response = client.put(
            f"/auth/users/{create_response.json()['id']}",
            json={"display_name": "Alice Admin Updated"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["username"] == "alice"
        assert update_response.json()["display_name"] == "Alice Admin Updated"


def test_product_auth_prevents_disabling_or_deleting_last_active_operator(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as client:
        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200
        admin_id = initialize_response.json()["current_user"]["id"]

        disable_response = client.post(f"/auth/users/{admin_id}/disable")
        assert disable_response.status_code == 409
        assert disable_response.json()["message"] == "Last Active Operator Protected"

        delete_response = client.delete(f"/auth/users/{admin_id}")
        assert delete_response.status_code == 409
        assert delete_response.json()["message"] == "Protected User"


def test_product_auth_prevents_deleting_initialized_user(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path / "product-auth"))

    service = ProductAuthService(str(tmp_path / "product-auth"))
    bootstrap_user, _ = service.bootstrap_operator_if_missing(
        username="websoft9",
        password="StrongPass123!",
        display_name="Websoft9 User",
    )
    session_token = service._create_session(bootstrap_user["id"])

    app = create_test_app()

    with TestClient(app) as client:
        client.cookies.set("websoft9_operator_session", session_token)

        delete_response = client.delete(f"/auth/users/{bootstrap_user['id']}")

    assert delete_response.status_code == 409
    assert delete_response.json()["message"] == "Protected User"


def test_non_system_user_can_only_edit_self_and_reset_own_password(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as system_client:
        initialize_response = system_client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200
        admin_id = initialize_response.json()["current_user"]["id"]

        alice_response = system_client.post(
            "/auth/users",
            json={"username": "alice", "password": "StrongPass123!", "display_name": "Alice User"},
        )
        assert alice_response.status_code == 200
        alice_id = alice_response.json()["id"]

        bob_response = system_client.post(
            "/auth/users",
            json={"username": "bob", "password": "StrongPass123!", "display_name": "Bob User"},
        )
        assert bob_response.status_code == 200
        bob_id = bob_response.json()["id"]

    with TestClient(app) as alice_client:
        login_response = alice_client.post(
            "/auth/login",
            json={"username": "alice", "password": "StrongPass123!"},
        )
        assert login_response.status_code == 200

        create_response = alice_client.post(
            "/auth/users",
            json={"username": "carol", "password": "StrongPass123!", "display_name": "Carol User"},
        )
        assert create_response.status_code == 403
        assert create_response.json()["message"] == "Permission Denied"

        update_bob_response = alice_client.put(
            f"/auth/users/{bob_id}",
            json={"display_name": "Bob Updated"},
        )
        assert update_bob_response.status_code == 403
        assert update_bob_response.json()["message"] == "Permission Denied"

        delete_bob_response = alice_client.delete(f"/auth/users/{bob_id}")
        assert delete_bob_response.status_code == 403
        assert delete_bob_response.json()["message"] == "Permission Denied"

        reset_admin_response = alice_client.post(
            f"/auth/users/{admin_id}/reset-password",
            json={"password": "OtherPass456!"},
        )
        assert reset_admin_response.status_code == 403
        assert reset_admin_response.json()["message"] == "Permission Denied"

        update_self_response = alice_client.put(
            f"/auth/users/{alice_id}",
            json={"display_name": "Alice Self Updated"},
        )
        assert update_self_response.status_code == 200
        assert update_self_response.json()["display_name"] == "Alice Self Updated"

        reset_self_response = alice_client.post(
            f"/auth/users/{alice_id}/reset-password",
            json={"password": "AliceNewPass456!"},
        )
        assert reset_self_response.status_code == 200

    with TestClient(app) as alice_relogin_client:
        old_login_response = alice_relogin_client.post(
            "/auth/login",
            json={"username": "alice", "password": "StrongPass123!"},
        )
        assert old_login_response.status_code == 401

        new_login_response = alice_relogin_client.post(
            "/auth/login",
            json={"username": "alice", "password": "AliceNewPass456!"},
        )
        assert new_login_response.status_code == 200


def test_non_system_user_only_sees_self_in_users_list(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    app = create_test_app()

    with TestClient(app) as system_client:
        initialize_response = system_client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200

        alice_response = system_client.post(
            "/auth/users",
            json={"username": "alice", "password": "StrongPass123!", "display_name": "Alice User"},
        )
        assert alice_response.status_code == 200
        alice_id = alice_response.json()["id"]

        bob_response = system_client.post(
            "/auth/users",
            json={"username": "bob", "password": "StrongPass123!", "display_name": "Bob User"},
        )
        assert bob_response.status_code == 200

        list_response = system_client.get("/auth/users")
        assert list_response.status_code == 200
        assert [user["username"] for user in list_response.json()["users"]] == ["admin", "alice", "bob"]

    with TestClient(app) as alice_client:
        login_response = alice_client.post(
            "/auth/login",
            json={"username": "alice", "password": "StrongPass123!"},
        )
        assert login_response.status_code == 200

        list_response = alice_client.get("/auth/users")
        assert list_response.status_code == 200
        assert len(list_response.json()["users"]) == 1
        assert list_response.json()["users"][0]["id"] == alice_id
        assert list_response.json()["users"][0]["username"] == "alice"


def test_product_auth_trusted_internal_request_does_not_auto_login_bootstrap_operator(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path / "product-auth"))

    trust_key_file = tmp_path / "internal-gateway-auth" / "trust_key"
    trust_key_file.parent.mkdir(parents=True, exist_ok=True)
    trust_key_file.write_text("shared-secret", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(trust_key_file))

    service = ProductAuthService(str(tmp_path / "product-auth"))
    operator, created = service.bootstrap_operator_if_missing(
        username="websoft9",
        password="StrongPass123!",
        display_name="Websoft9 Operator",
    )

    assert created is True
    assert operator["username"] == "websoft9"

    app = create_test_app()

    with TestClient(app) as client:
        session_response = client.get(
            "/auth/session",
            headers={"x-websoft9-internal-request": "1", "x-websoft9-internal-secret": "shared-secret"},
        )

        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is False
        assert session_response.json()["initialization_required"] is False
        assert session_response.json()["current_user"] is None
        assert "set-cookie" not in session_response.headers


def test_product_auth_internal_request_does_not_auto_login_ui_initialized_operator(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path / "product-auth"))

    trust_key_file = tmp_path / "internal-gateway-auth" / "trust_key"
    trust_key_file.parent.mkdir(parents=True, exist_ok=True)
    trust_key_file.write_text("shared-secret", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(trust_key_file))

    app = create_test_app()

    with TestClient(app) as client:
        initialize_response = client.post(
            "/auth/initialize",
            json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
        )
        assert initialize_response.status_code == 200

    with TestClient(app) as internal_client:
        session_response = internal_client.get(
            "/auth/session",
            headers={"x-websoft9-internal-request": "1", "x-websoft9-internal-secret": "shared-secret"},
        )

    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False
    assert "set-cookie" not in session_response.headers