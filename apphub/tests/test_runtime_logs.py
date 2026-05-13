import json
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import auth as auth_router
from src.api.v1.routers import logs as logs_router
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.schemas.runtimeLogs import RuntimeLogsQuery
from src.services.runtime_logs import RuntimeLogsService


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
    app.include_router(logs_router.router)
    return app


class FakeAuthService:
    def _require_authenticated_operator(self, session_token: Optional[str]):
        if session_token != "valid-session":
            raise CustomException(401, "Unauthorized", "Login required")


def write_runtime_log_file(tmp_path: Path, payloads: Iterable[Union[dict, str]], file_name: str = "platform-runtime.log") -> Path:
    path = tmp_path / file_name
    lines: list[str] = []
    for payload in payloads:
        if isinstance(payload, dict):
            lines.append(json.dumps(payload, ensure_ascii=True))
        else:
            lines.append(str(payload))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_runtime_logs_service_filters_by_level_and_keyword(tmp_path: Path):
    log_path = write_runtime_log_file(
        tmp_path,
        [
            {"ts": "2026-05-06T08:49:28.100000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "core-bootstrap.start-supervisor", "message": "phase=core-bootstrap action=start-supervisor"},
            {"ts": "2026-05-06T08:49:29.100000Z", "level": "error", "component": "platform-entrypoint", "domain": "runtime", "event": "bootstrap-failed", "message": "failed to bootstrap platform gateway"},
            {"ts": "2026-05-06T08:49:30.100000Z", "level": "warning", "component": "apphub-api", "domain": "runtime", "event": "restart-detected", "message": "warning restart detected"},
        ],
    )
    service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    entries = service.get_runtime_logs("valid-session", RuntimeLogsQuery(level="error", keyword="gateway", limit=20))

    assert len(entries) == 1
    assert entries[0].level == "error"
    assert "gateway" in entries[0].message.lower()


def test_runtime_logs_service_filters_by_time_range_and_drops_unparseable_lines(tmp_path: Path):
    log_path = write_runtime_log_file(
        tmp_path,
        [
            "not-json startup line",
            {"ts": "2026-05-01T08:49:28.100000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "old-line", "message": "info old line"},
            {"ts": "2099-05-06T08:49:29.100000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "future-line", "message": "info future line"},
        ],
    )
    service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    entries = service.get_runtime_logs("valid-session", RuntimeLogsQuery(time_range="24h", limit=20))

    assert len(entries) == 1
    assert entries[0].message == "[platform-entrypoint] info future line"


def test_runtime_logs_service_accepts_7d_time_range(tmp_path: Path):
    now = datetime.now(timezone.utc)
    log_path = write_runtime_log_file(
        tmp_path,
        [
            {"ts": (now - timedelta(days=3)).isoformat().replace("+00:00", "Z"), "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "within-7d", "message": "info line within seven days"},
            {"ts": (now - timedelta(days=10)).isoformat().replace("+00:00", "Z"), "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "outside-7d", "message": "info line outside seven days"},
        ],
    )
    service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    entries = service.get_runtime_logs("valid-session", RuntimeLogsQuery(time_range="7d", limit=20))

    assert len(entries) == 1
    assert entries[0].message == "[platform-entrypoint] info line within seven days"


def test_runtime_logs_service_ignores_third_party_and_non_runtime_lines(tmp_path: Path):
    log_path = write_runtime_log_file(
        tmp_path,
        [
            {"ts": "2026-05-06T01:12:53.000000Z", "level": "info", "component": "nginx-proxy-manager", "domain": "service", "event": "reload", "message": "Reloading Nginx"},
            {"ts": "2026-05-06T01:12:51.000000Z", "level": "info", "component": "portainer", "domain": "service", "event": "cert-renewed", "message": "Completed SSL cert renew process"},
            {"ts": "2026-05-06T01:12:55.000000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "workspace-bootstrap.bootstrap-platform-gateway", "message": "phase=workspace-bootstrap action=bootstrap-platform-gateway"},
        ],
    )
    service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    entries = service.get_runtime_logs("valid-session", RuntimeLogsQuery(limit=20))

    assert len(entries) == 1
    assert "platform-entrypoint" in entries[0].message


def test_runtime_logs_service_excludes_apphub_runtime_entries(tmp_path: Path):
    log_path = write_runtime_log_file(
        tmp_path,
        [
            {"ts": "2026-05-06T01:12:50.000000Z", "level": "info", "component": "apphub-api", "domain": "runtime", "event": "bootstrap", "message": "apphub started"},
            {"ts": "2026-05-06T01:12:55.000000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "workspace-bootstrap.bootstrap-platform-gateway", "message": "phase=workspace-bootstrap action=bootstrap-platform-gateway"},
        ],
    )
    service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    entries = service.get_runtime_logs("valid-session", RuntimeLogsQuery(limit=20))

    assert len(entries) == 1
    assert "apphub" not in entries[0].message.lower()


def test_runtime_logs_service_raises_stable_error_when_log_source_missing(tmp_path: Path):
    service = RuntimeLogsService(log_path=str(tmp_path / "missing.log"), auth_service=FakeAuthService())

    try:
        service.get_runtime_logs("valid-session", RuntimeLogsQuery(limit=20))
    except CustomException as exc:
        assert exc.status_code == 503
        assert exc.message == "Runtime Logs Unavailable"
    else:
        raise AssertionError("Expected CustomException")


def test_runtime_logs_router_requires_authenticated_session():
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/logs/runtime")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication Required"


def test_runtime_logs_router_returns_normalized_payload(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    log_path = write_runtime_log_file(
        PROJECT_ROOT / "tests",
        [
            {"ts": "2026-05-06T08:49:28.100000Z", "level": "info", "component": "platform-entrypoint", "domain": "runtime", "event": "core-bootstrap.start-supervisor", "message": "phase=core-bootstrap action=start-supervisor"},
            {"ts": "2026-05-06T08:49:29.100000Z", "level": "error", "component": "platform-entrypoint", "domain": "runtime", "event": "bootstrap-failed", "message": "failed to bootstrap platform gateway"},
        ],
        file_name="platform-runtime-router.log",
    )
    logs_router._runtime_logs_service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    response = client.get("/logs/runtime", cookies={"websoft9_operator_session": "valid-session"}, params={"limit": 50, "level": "error"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "runtime-console"
    assert payload["level"] == "error"
    assert payload["limit"] == 50
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["level"] == "error"


def test_runtime_logs_router_validates_limit(monkeypatch):
    app = create_test_app()
    client = TestClient(app)
    log_path = write_runtime_log_file(PROJECT_ROOT / "tests", [], file_name="platform-runtime-empty.log")
    logs_router._runtime_logs_service = RuntimeLogsService(log_path=str(log_path), auth_service=FakeAuthService())

    response = client.get("/logs/runtime", cookies={"websoft9_operator_session": "valid-session"}, params={"limit": 50000})

    assert response.status_code == 400
    assert response.json()["message"] == "Request Validation Error"