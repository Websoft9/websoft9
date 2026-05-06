import sys
from gzip import open as gzip_open
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import auth as auth_router
from src.api.v1.routers import services as services_router
from src.core.exception import CustomException
from src.schemas.coreServices import ServiceLogsQuery
from src.schemas.errorResponse import ErrorResponse
from src.services.core_services import CoreServicesService, HealthProbeResult, ServiceDefinition


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
    app.include_router(services_router.router)
    return app


class FakeAuthService:
    def _require_authenticated_operator(self, session_token: Optional[str]):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")


def build_service_definitions(tmp_path: Path) -> list[ServiceDefinition]:
    return [
        ServiceDefinition(
            key="gitea",
            label="Gitea",
            description="Git repository service",
            supervisor_program="gitea",
            health_url="http://127.0.0.1:3000/",
            workspace_route="repository",
            integration_key="gitea",
            log_root=tmp_path / "gitea",
            markers=(tmp_path / "gitea-credential",),
        ),
        ServiceDefinition(
            key="portainer",
            label="Portainer",
            description="Container management service",
            supervisor_program="portainer",
            health_url="https://127.0.0.1:9443/api/system/status",
            health_verify_tls=False,
            workspace_route="containers",
            integration_key="portainer",
            log_root=tmp_path / "portainer",
            markers=(tmp_path / "portainer-credential",),
        ),
        ServiceDefinition(
            key="nginx-proxy-manager",
            label="Nginx Proxy Manager",
            description="Reverse proxy and certificate service",
            supervisor_program=None,
            health_url="http://127.0.0.1:81/",
            workspace_route="gateway",
            integration_key="npm",
            log_root=tmp_path / "nginx-proxy-manager",
            markers=(tmp_path / "npm-credential.json", tmp_path / "npm-cert.pem"),
        ),
    ]


def write_log(root: Path, file_name: str, lines: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / file_name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_core_services_inventory_reuses_runtime_signals(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "gitea-credential").write_text("ok", encoding="utf-8")
    (tmp_path / "portainer-credential").write_text("ok", encoding="utf-8")
    (tmp_path / "npm-credential.json").write_text("{}", encoding="utf-8")
    (tmp_path / "npm-cert.pem").write_text("ok", encoding="utf-8")
    write_log(tmp_path / "gitea", "gitea.log", ["2026-05-06T08:49:28Z repo ready"])
    write_log(tmp_path / "portainer", "portainer.log", ["2026-05-06T08:49:29Z endpoint ready"])
    write_log(tmp_path / "nginx-proxy-manager", "npm.log", ["2026-05-06T08:49:30Z gateway ready"])

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"gitea": "RUNNING", "portainer": "EXITED"},
        health_probe=lambda definition: HealthProbeResult(ok=definition.key in {"gitea", "nginx-proxy-manager"}, detail="ok" if definition.key in {"gitea", "nginx-proxy-manager"} else "connection failed"),
        now_provider=lambda: datetime(2026, 5, 6, 8, 50, tzinfo=timezone.utc),
    )

    payload = service.list_services("valid-session")

    assert [item.key for item in payload] == ["gitea", "portainer", "nginx-proxy-manager"]
    assert payload[0].runtime_state == "running"
    assert payload[0].health_state == "healthy"
    assert payload[0].workspace_route == "repository"
    assert payload[1].runtime_state == "stopped"
    assert payload[1].health_state == "unavailable"
    assert payload[2].runtime_state == "running"
    assert payload[2].health_state == "healthy"
    assert all("/" not in (indicator.value or "") for service in payload for indicator in service.indicators)


def test_core_services_inventory_degrades_per_row_when_one_health_source_fails(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "gitea-credential").write_text("ok", encoding="utf-8")
    (tmp_path / "portainer-credential").write_text("ok", encoding="utf-8")

    def probe(definition: ServiceDefinition) -> HealthProbeResult:
        if definition.key == "portainer":
            raise OSError("portainer probe timed out")
        return HealthProbeResult(ok=True, detail="ok")

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"gitea": "RUNNING", "portainer": "RUNNING"},
        health_probe=probe,
        now_provider=lambda: datetime(2026, 5, 6, 8, 50, tzinfo=timezone.utc),
    )

    payload = service.list_services("valid-session")

    assert payload[0].health_state == "healthy"
    assert payload[1].health_state == "degraded"
    assert payload[1].indicators[0].status == "error"
    assert "timed out" in (payload[1].indicators[0].detail or "")


def test_core_services_inventory_prefers_running_when_starting_service_is_healthy(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "portainer-credential").write_text("ok", encoding="utf-8")
    write_log(tmp_path / "portainer", "portainer.log", ["2026-05-06T08:49:29Z endpoint ready"])

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"portainer": "STARTING"},
        health_probe=lambda definition: HealthProbeResult(ok=definition.key == "portainer", detail="HTTP 200" if definition.key == "portainer" else "connection failed"),
        now_provider=lambda: datetime(2026, 5, 6, 8, 50, tzinfo=timezone.utc),
    )

    payload = service.list_services("valid-session")
    portainer = next(item for item in payload if item.key == "portainer")

    assert portainer.runtime_state == "running"
    assert portainer.runtime_detail == "starting-endpoint-responding"


def test_core_services_log_drilldown_filters_raw_lines(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "gitea-credential").write_text("ok", encoding="utf-8")
    write_log(
        tmp_path / "gitea",
        "gitea.log",
        [
            "2026-05-06T08:49:28Z repo ready",
            "2026-05-06T08:49:29Z fatal migration error",
            "2026-05-06T08:49:30Z repo restarted",
        ],
    )

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"gitea": "RUNNING"},
        health_probe=lambda _definition: HealthProbeResult(ok=True, detail="ok"),
    )

    payload = service.get_service_logs("valid-session", "gitea", ServiceLogsQuery(keyword="fatal", limit=20))

    assert payload.service == "gitea"
    assert len(payload.entries) == 1
    assert payload.entries[0].message == "fatal migration error"
    assert payload.available is True


def test_core_services_log_drilldown_strips_ansi_and_parses_portainer_lines(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "portainer-credential").write_text("ok", encoding="utf-8")
    write_log(
        tmp_path / "portainer",
        "service.log",
        [
            "\u001b[90m2026/05/06 03:43AM\u001b[0m \u001b[32mINF\u001b[0m \u001b[1mgithub.com/portainer/portainer/api/cmd/portainer/main.go:366\u001b[0m\u001b[36m >\u001b[0m proceeding without encryption key |",
            "2026/05/06 03:43:33 Portainer initialization completed successfully.",
        ],
    )

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"portainer": "RUNNING"},
        health_probe=lambda _definition: HealthProbeResult(ok=True, detail="ok"),
    )

    payload = service.get_service_logs("valid-session", "portainer", ServiceLogsQuery(limit=20))

    assert payload.available is True
    assert payload.entries[0].timestamp == "2026-05-06T03:43:00Z"
    assert payload.entries[0].level == "INF"
    assert payload.entries[0].message == "proceeding without encryption key |"
    assert "\u001b" not in payload.entries[0].raw
    assert payload.entries[1].timestamp == "2026-05-06T03:43:33Z"


def test_core_services_log_drilldown_skips_gzip_rotated_logs(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "npm-credential.json").write_text("{}", encoding="utf-8")
    (tmp_path / "npm-cert.pem").write_text("ok", encoding="utf-8")
    log_root = tmp_path / "nginx-proxy-manager"
    write_log(log_root, "fallback_error.log", ["2026/05/06 01:34:52 connect() failed"])
    log_root.mkdir(parents=True, exist_ok=True)
    with gzip_open(log_root / "fallback_error.log.1.gz", "wb") as handle:
        handle.write(b"binary compressed content")

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {},
        health_probe=lambda _definition: HealthProbeResult(ok=True, detail="ok"),
    )

    payload = service.get_service_logs("valid-session", "nginx-proxy-manager", ServiceLogsQuery(limit=20))

    assert payload.available is True
    assert len(payload.entries) == 1
    assert payload.entries[0].message == "connect() failed"
    assert payload.entries[0].level is None


def test_core_services_log_drilldown_filters_by_level_and_time_range(tmp_path: Path):
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "portainer-credential").write_text("ok", encoding="utf-8")
    write_log(
        tmp_path / "portainer",
        "service.log",
        [
            "2026/05/06 08:20AM INF github.com/portainer/portainer/api/cmd/portainer/main.go:366 > proceeding without encryption key |",
            "2026/05/06 08:48AM FTL github.com/portainer/portainer/api/cmd/portainer/main.go:104 > failed opening store | error=timeout",
        ],
    )

    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"portainer": "RUNNING"},
        health_probe=lambda _definition: HealthProbeResult(ok=True, detail="ok"),
        now_provider=lambda: datetime(2026, 5, 6, 8, 50, tzinfo=timezone.utc),
    )

    payload = service.get_service_logs(
        "valid-session",
        "portainer",
        ServiceLogsQuery(level="fatal", time_range="15m", limit=50),
    )

    assert payload.level == "fatal"
    assert payload.time_range == "15m"
    assert len(payload.entries) == 1
    assert payload.entries[0].level == "FTL"
    assert payload.entries[0].message == "failed opening store | error=timeout"


def test_core_services_log_drilldown_rejects_unsupported_service(tmp_path: Path):
    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=build_service_definitions(tmp_path),
        supervisor_status_loader=lambda: {},
        health_probe=lambda _definition: HealthProbeResult(ok=False, detail="not-ready"),
    )

    try:
        service.get_service_logs("valid-session", "unknown-service", ServiceLogsQuery(limit=20))
    except CustomException as exc:
        assert exc.status_code == 404
        assert exc.message == "Service Not Found"
    else:
        raise AssertionError("Expected CustomException")


def test_core_services_log_drilldown_hides_runtime_paths_when_unavailable(tmp_path: Path):
    service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=build_service_definitions(tmp_path),
        supervisor_status_loader=lambda: {},
        health_probe=lambda _definition: HealthProbeResult(ok=False, detail="not-ready"),
    )

    payload = service.get_service_logs("valid-session", "gitea", ServiceLogsQuery(limit=20))

    assert payload.available is False
    assert payload.unavailable_reason == "Service raw logs are not currently available"


def test_core_services_router_requires_authenticated_session():
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/services")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication Required"


def test_core_services_router_returns_inventory_payload(tmp_path: Path):
    app = create_test_app()
    client = TestClient(app)
    definitions = build_service_definitions(tmp_path)
    (tmp_path / "gitea-credential").write_text("ok", encoding="utf-8")
    write_log(tmp_path / "gitea", "gitea.log", ["2026-05-06T08:49:28Z repo ready"])

    services_router._core_services_service = CoreServicesService(
        auth_service=FakeAuthService(),
        service_definitions=definitions,
        supervisor_status_loader=lambda: {"gitea": "RUNNING"},
        health_probe=lambda definition: HealthProbeResult(ok=definition.key == "gitea", detail="ok" if definition.key == "gitea" else "connection failed"),
        now_provider=lambda: datetime(2026, 5, 6, 8, 50, tzinfo=timezone.utc),
    )

    response = client.get("/services", cookies={"websoft9_operator_session": "valid-session"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["services"]) == 3
    assert payload["services"][0]["key"] == "gitea"
    assert payload["services"][0]["runtime_state"] == "running"
