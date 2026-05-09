import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import auth as auth_router
from src.api.v1.routers import overview as overview_router
from src.core.exception import CustomException
from src.schemas.appResponse import AppResponse
from src.schemas.coreServices import CoreServiceSummary
from src.schemas.errorResponse import ErrorResponse
from src.schemas.overview import OverviewTaskItem
from src.services.overview_service import OverviewService


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
    app.include_router(overview_router.router)
    return app


class FakeAuthService:
    def _require_authenticated_operator(self, session_token: Optional[str]):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")


def test_overview_service_aggregates_product_apps_services_and_tasks():
    service = OverviewService(
        auth_service=FakeAuthService(),
        product_metadata_loader=lambda: {"version": "2.2.17", "edition_key": "free", "edition_name": "Free", "max_apps": 2},
        available_catalog_count_loader=lambda: 432,
        host_summary_loader=lambda: {
            "hostname": "host-a",
            "os_name": "Ubuntu 24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "uptime_seconds": 7200,
        },
        host_runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 31.2,
            "cpu_cores": 8,
            "cpu_quota_cores": None,
            "memory_percent": 44.1,
            "memory_used_bytes": 441,
            "memory_total_bytes": 1000,
            "network_rx_rate_bytes": 4096,
            "network_tx_rate_bytes": 2048,
            "network_rx_bytes": 200_000,
            "network_tx_bytes": 100_000,
            "disk_percent": 52.5,
            "disk_used_bytes": 525,
            "disk_total_bytes": 1000,
        },
        apps_loader=lambda: [
            {"app_id": "a1", "status": 1},
            {"app_id": "a2", "status": 3},
            {"app_id": "a3", "status": 4},
        ],
        runtime_summary_loader=lambda: {
            "runtime_scope": "container",
            "health_state": "warning",
            "cpu_percent": 72.5,
            "cpu_cores": 4,
            "cpu_quota_cores": 2.0,
            "memory_percent": 81.2,
            "memory_used_bytes": 8,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": 2048,
            "network_tx_rate_bytes": 1024,
            "network_rx_bytes": 100_000,
            "network_tx_bytes": 50_000,
        },
        services_loader=lambda session_token: [
            CoreServiceSummary(
                key="gitea",
                label="Gitea",
                description="Git repository service",
                runtime_state="running",
                runtime_detail="running",
                health_state="healthy",
                updated_at="2026-05-07T09:00:00Z",
                workspace_route="repository",
                integration_key="gitea",
                logs_available=True,
                runtime_logs_href="/logs?keyword=gitea",
                indicators=[],
            ),
            CoreServiceSummary(
                key="portainer",
                label="Portainer",
                description="Container management service",
                runtime_state="running",
                runtime_detail="running",
                health_state="degraded",
                updated_at="2026-05-07T09:00:00Z",
                workspace_route="containers",
                integration_key="portainer",
                logs_available=True,
                runtime_logs_href="/logs?keyword=portainer",
                indicators=[],
            ),
        ],
        tasks_loader=lambda: [
            OverviewTaskItem(
                key="install-a2",
                kind="app-install",
                title="Install a2",
                status="running",
                detail="App installation is still running",
                updated_at="2026-05-07T09:00:00Z",
                target_route="/myapps",
            )
        ],
        now_provider=lambda: datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    payload = service.get_overview("valid-session")

    assert payload.product.version == "2.2.17"
    assert payload.product.edition_key == "free"
    assert payload.product.catalog_app_count == 432
    assert payload.product.installed_count == 3
    assert payload.product.available_app_count == 2
    assert payload.host.hostname == "host-a"
    assert payload.host.os_name == "Ubuntu 24.04"
    assert payload.apps.installed_count == 3
    assert payload.apps.active_count == 1
    assert payload.apps.installing_count == 1
    assert payload.apps.error_count == 1
    assert payload.runtime.health_state == "warning"
    assert payload.runtime.runtime_scope == "container"
    assert payload.runtime.memory_percent == 81.2
    assert payload.host_runtime.runtime_scope == "system"
    assert payload.host_runtime.disk_percent == 52.5
    assert payload.services.total_count == 2
    assert payload.services.healthy_count == 1
    assert payload.services.degraded_count == 1
    assert payload.tasks.items[0].status == "running"
    assert payload.alerts[0].target_route in {"/myapps", "/services"}


def test_overview_service_degrades_per_section_instead_of_failing_whole_page():
    service = OverviewService(
        auth_service=FakeAuthService(),
        product_metadata_loader=lambda: {"version": "2.2.17", "edition_key": "free", "edition_name": "Free", "max_apps": 2},
        available_catalog_count_loader=lambda: 432,
        host_summary_loader=lambda: {"hostname": "host-a"},
        host_runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 10.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 20.0,
            "memory_used_bytes": 2,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
            "disk_percent": 30.0,
            "disk_used_bytes": 3,
            "disk_total_bytes": 10,
        },
        apps_loader=lambda: (_ for _ in ()).throw(OSError("apps source unavailable")),
        runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 12.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 24.0,
            "memory_used_bytes": 2,
            "memory_total_bytes": 8,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
        },
        services_loader=lambda session_token: [],
        tasks_loader=lambda: [],
        now_provider=lambda: datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    payload = service.get_overview("valid-session")

    assert payload.apps.available is False
    assert "apps source unavailable" in (payload.apps.unavailable_reason or "")
    assert payload.product.available is True
    assert payload.product.catalog_app_count == 432
    assert payload.product.installed_count is None
    assert payload.product.available_app_count == 2
    assert payload.host.available is True
    assert payload.host_runtime.available is True
    assert payload.runtime.available is True
    assert payload.services.available is True
    assert payload.tasks.available is True


def test_overview_service_supports_runtime_app_response_models():
    service = OverviewService(
        auth_service=FakeAuthService(),
        product_metadata_loader=lambda: {"version": "2.2.17", "edition_key": "free", "edition_name": "Free", "max_apps": 2},
        available_catalog_count_loader=lambda: 432,
        host_summary_loader=lambda: {"hostname": "host-a"},
        host_runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 18.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 30.0,
            "memory_used_bytes": 3,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
            "disk_percent": 40.0,
            "disk_used_bytes": 4,
            "disk_total_bytes": 10,
        },
        apps_loader=lambda: [
            AppResponse(app_id="demo", app_name="Demo", status=1, tracking_id="task-1", creationDate=1_778_147_200),
            AppResponse(app_id="demo-2", app_name="Demo 2", status=4, tracking_id="task-2", error="install failed", creationDate=1_778_147_260),
        ],
        runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 18.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 30.0,
            "memory_used_bytes": 3,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
        },
        services_loader=lambda session_token: [],
        tasks_loader=None,
        now_provider=lambda: datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    payload = service.get_overview("valid-session")

    assert payload.apps.active_count == 1
    assert payload.apps.error_count == 1
    assert any(item.status == "failed" for item in payload.tasks.items)
    assert any(item.updated_at == "2026-05-07T09:47:40Z" for item in payload.tasks.items)


def test_overview_router_requires_authenticated_session():
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/overview")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication Required"


def test_overview_router_returns_normalized_payload():
    app = create_test_app()
    client = TestClient(app)

    overview_router._overview_service = OverviewService(
        auth_service=FakeAuthService(),
        product_metadata_loader=lambda: {"version": "2.2.17", "edition_key": "free", "edition_name": "Free", "max_apps": 2},
        host_summary_loader=lambda: {
            "hostname": "host-a",
            "os_name": "Ubuntu 24.04",
            "kernel_version": "6.8.0",
            "architecture": "x86_64",
            "uptime_seconds": 7200,
        },
        host_runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 11.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 22.0,
            "memory_used_bytes": 2,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
            "disk_percent": 33.0,
            "disk_used_bytes": 3,
            "disk_total_bytes": 10,
        },
        apps_loader=lambda: [{"app_id": "a1", "status": 1}],
        runtime_summary_loader=lambda: {
            "runtime_scope": "system",
            "health_state": "healthy",
            "cpu_percent": 21.0,
            "cpu_cores": 4,
            "cpu_quota_cores": None,
            "memory_percent": 40.0,
            "memory_used_bytes": 4,
            "memory_total_bytes": 10,
            "network_rx_rate_bytes": None,
            "network_tx_rate_bytes": None,
            "network_rx_bytes": None,
            "network_tx_bytes": None,
        },
        services_loader=lambda session_token: [],
        tasks_loader=lambda: [],
        now_provider=lambda: datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    response = client.get("/overview", cookies={"websoft9_operator_session": "valid-session"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["version"] == "2.2.17"
    assert payload["product"]["installed_count"] == 1
    assert payload["product"]["available_app_count"] == 2
    assert payload["host"]["hostname"] == "host-a"
    assert payload["host_runtime"]["disk_percent"] == 33.0
    assert payload["runtime"]["runtime_scope"] == "system"
    assert payload["runtime"]["cpu_percent"] == 21.0
    assert payload["tasks"]["items"] == []


def test_overview_host_runtime_summary_reports_system_disk_usage():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(service, "_load_docker_host_info", return_value={}),
        patch.object(service, "_read_host_cpu_percent", return_value=42.5),
        patch.object(service, "_read_memory_snapshot", return_value=(16_000, 10_000)),
        patch.object(service, "_read_network_summary", return_value=(120_000, 80_000, 4_096, 2_048)),
        patch("src.services.overview_service.os.cpu_count", return_value=8),
        patch("src.services.overview_service.shutil.disk_usage", return_value=shutil._ntuple_diskusage(total=200_000, used=90_000, free=110_000)),
    ):
        payload = service._load_host_runtime_summary()

    assert payload["runtime_scope"] == "system"
    assert payload["cpu_percent"] == 42.5
    assert payload["memory_percent"] == 37.5
    assert payload["disk_percent"] == 45.0
    assert payload["disk_used_bytes"] == 90_000
    assert payload["disk_total_bytes"] == 200_000


def test_overview_host_summary_prefers_docker_host_info_when_available():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(
            service,
            "_load_docker_host_info",
            return_value={
                "hostname": "iZ8vb9gse4rc3k7hxgadluZ",
                "os_name": "Rocky Linux 9.7 (Blue Onyx)",
                "kernel_version": "5.14.0-611.16.1.el9_7.x86_64",
                "architecture": "x86_64",
                "cpu_cores": 2,
                "memory_total_bytes": 8_054_468_608,
                "docker_root_dir": "/data/docker",
            },
        ),
        patch.object(service, "_read_uptime_seconds", return_value=3600),
        patch("src.services.overview_service.socket.gethostname", return_value="container-name"),
        patch("src.services.overview_service.os.uname") as mocked_uname,
    ):
        mocked_uname.return_value = type("Uname", (), {"release": "container-kernel", "machine": "container-arch"})()
        payload = service._load_host_summary()

    assert payload["hostname"] == "iZ8vb9gse4rc3k7hxgadluZ"
    assert payload["os_name"] == "Rocky Linux 9.7 (Blue Onyx)"
    assert payload["kernel_version"] == "5.14.0-611.16.1.el9_7.x86_64"
    assert payload["architecture"] == "x86_64"
    assert payload["uptime_seconds"] == 3600


def test_overview_host_runtime_summary_prefers_docker_host_capacity_when_available():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(
            service,
            "_load_docker_host_info",
            return_value={
                "cpu_cores": 2,
                "memory_total_bytes": 8_054_468_608,
                "docker_root_dir": "/data/docker",
            },
        ),
        patch.object(service, "_read_host_cpu_percent", return_value=50.0),
        patch.object(service, "_read_memory_snapshot", return_value=(7_865_692 * 1024, 2_700_000_000)),
        patch.object(service, "_read_network_summary", return_value=(120_000, 80_000, 4_096, 2_048)),
        patch("src.services.overview_service.shutil.disk_usage", return_value=shutil._ntuple_diskusage(total=200_000, used=90_000, free=110_000)) as mocked_disk_usage,
    ):
        payload = service._load_host_runtime_summary()

    mocked_disk_usage.assert_called_once_with("/data/docker")
    assert payload["runtime_scope"] == "system"
    assert payload["cpu_cores"] == 2
    assert payload["cpu_percent"] == 50.0
    assert payload["memory_total_bytes"] == 8_054_468_608
    assert payload["memory_used_bytes"] == 5_354_468_608
    assert payload["memory_percent"] == 66.5


def test_overview_host_cpu_percent_uses_proc_stat_deltas():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(service, "_read_host_cpu_times", side_effect=[(400, 1_000), (420, 1_100)]),
        patch("src.services.overview_service.time.sleep"),
        patch("src.services.overview_service.time.monotonic_ns", return_value=1_000_000_000),
    ):
        cpu_percent = service._read_host_cpu_percent()

    assert cpu_percent == 80.0


def test_overview_runtime_summary_prefers_cgroup_limits_when_available():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(service, "_read_cgroup_cpu_limit_cores", return_value=1.5),
        patch.object(service, "_read_cgroup_cpu_percent", return_value=61.2),
        patch.object(service, "_read_cgroup_memory_snapshot", return_value=(8_000, 3_000)),
        patch.object(service, "_read_memory_snapshot", return_value=(16_000, 10_000)),
        patch.object(service, "_read_network_summary", return_value=(120_000, 90_000, 4_096, 2_048)),
        patch("src.services.overview_service.os.cpu_count", return_value=8),
    ):
        payload = service._load_runtime_summary()

    assert payload["runtime_scope"] == "container"
    assert payload["cpu_percent"] == 61.2
    assert payload["cpu_quota_cores"] == 1.5
    assert payload["memory_total_bytes"] == 8_000
    assert payload["memory_used_bytes"] == 3_000
    assert payload["memory_percent"] == 37.5
    assert payload["network_rx_rate_bytes"] == 4_096
    assert payload["network_tx_rate_bytes"] == 2_048
    assert payload["disk_percent"] is None


def test_overview_runtime_memory_snapshot_excludes_inactive_file_cache():
    service = OverviewService(auth_service=FakeAuthService())

    with patch.object(
        service,
        "_read_text_file",
        side_effect=lambda path: {
            "/sys/fs/cgroup/memory.current": "8000",
            "/sys/fs/cgroup/memory.max": "10000",
            "/sys/fs/cgroup/memory.stat": "anon 3000\ninactive_file 2500\nfile 4000",
        }.get(str(path)),
    ):
        memory_snapshot = service._read_cgroup_memory_snapshot()

    assert memory_snapshot == (10_000, 5_500)


def test_overview_runtime_summary_uses_container_memory_when_limit_is_unbounded():
    service = OverviewService(auth_service=FakeAuthService())

    with (
        patch.object(service, "_read_cgroup_cpu_limit_cores", return_value=None),
        patch.object(service, "_read_cgroup_cpu_percent", return_value=8.5),
        patch.object(service, "_read_cgroup_memory_snapshot", return_value=None),
        patch.object(service, "_read_cgroup_memory_usage_bytes", return_value=600_000_000),
        patch.object(service, "_read_memory_snapshot", return_value=(7_500_000_000, 2_900_000_000)),
        patch.object(service, "_read_network_summary", return_value=(None, None, None, None)),
        patch("src.services.overview_service.os.cpu_count", return_value=2),
    ):
        payload = service._load_runtime_summary()

    assert payload["runtime_scope"] == "container"
    assert payload["memory_used_bytes"] == 600_000_000
    assert payload["memory_total_bytes"] == 7_500_000_000
    assert payload["memory_percent"] == 8.0