from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
import types
from pathlib import Path
import pytest

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_docker_frame(stream_id: int, text: str) -> bytes:
    payload = text.encode("utf-8")
    header = bytes([stream_id, 0, 0, 0]) + len(payload).to_bytes(4, "big")
    return header + payload


def test_install_state_store_lazy_init_and_readonly_snapshot(tmp_path):
    from src.services.app_status import InstallStateStore

    store_dir = tmp_path / "lazy-tracking"
    store = InstallStateStore(str(store_dir), initialize=False)
    assert not store.database_file.exists()
    with pytest.raises(FileNotFoundError):
        store.list_tasks_readonly((3, 4, 6))
    assert not store.database_file.exists()

    tracking_id = store.create_task("wordpress_a1b2c", "wordpress", status=3)
    assert store.database_file.exists()

    readonly_tasks = dict(store.list_tasks_readonly((3,)))
    assert tracking_id in readonly_tasks
    assert readonly_tasks[tracking_id]["app_id"] == "wordpress_a1b2c"


def test_app_list_and_inspect_are_readonly_and_strict(monkeypatch, tmp_path):
    from src.cli.app_commands import app_group
    from src.schemas.appResponse import AppResponse
    from src.services import app_manager as app_manager_module
    from src.services.app_manager import AppManger
    from src.services.app_status import appInstalling, configure_install_state_store, start_app_installation

    configure_install_state_store(str(tmp_path))
    for tid, _ in list(appInstalling.items()):
        appInstalling.pop(tid, None)

    tracking_id = start_app_installation("wordpress_stale", "wordpress")
    stale_task = appInstalling[tracking_id]
    stale_task["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    appInstalling[tracking_id] = stale_task

    class FakePortainerManager:
        def get_local_endpoint_id(self):
            return 1

        def get_stacks(self, endpoint_id: int):
            return [
                {
                    "Id": 10,
                    "Name": "redis_12345",
                    "Status": 1,
                    "GitConfig": {"URL": "http://gitea/redis"},
                    "CreationDate": 1700000000,
                }
            ]

        def get_containers(self, endpoint_id: int):
            return [
                {
                    "Id": "cid-redis",
                    "Names": ["/redis_12345"],
                    "Image": "redis:7",
                    "State": "running",
                    "Status": "Up 2 hours (healthy)",
                    "Labels": {"com.docker.compose.project": "redis_12345"},
                }
            ]

        def get_volumes_by_stack_name(self, stack_name: str, endpoint_id: int, dangling: bool):
            return [{"Name": f"{stack_name}_data", "Driver": "local"}]

        def get_container_by_id(self, endpoint_id: int, container_id: str):
            return {
                "Config": {
                    "Env": [
                        "W9_APP_NAME=redis",
                        "W9_VERSION=7.2",
                        "W9_DIST=community",
                        "REDIS_PASSWORD=supersecret",
                    ]
                }
            }

        def get_stack_by_name(self, stack_name: str, endpoint_id: int):
            if stack_name == "redis_12345":
                return {
                    "Id": 10,
                    "Name": "redis_12345",
                    "Status": 1,
                    "GitConfig": {"URL": "http://gitea/redis"},
                    "CreationDate": 1700000000,
                }
            return None

        def get_containers_by_stack_name(self, stack_name: str, endpoint_id: int):
            return self.get_containers(endpoint_id) if stack_name == "redis_12345" else []

    class FakeProxyManager:
        def get_proxy_hosts(self):
            return []

        def get_proxy_host_by_app(self, app_id: str):
            return []

    class FakeGiteaManager:
        def check_repo_exists(self, repo_name: str):
            return False

    monkeypatch.setattr(app_manager_module, "PortainerManager", FakePortainerManager)
    monkeypatch.setattr(app_manager_module, "ProxyManager", FakeProxyManager)
    monkeypatch.setattr(app_manager_module, "GiteaManager", FakeGiteaManager)
    monkeypatch.setattr(app_manager_module, "check_endpointId", lambda endpoint_id, manager: None)
    monkeypatch.setattr(AppManger, "_get_available_app_logo_map", lambda self, locale: {})

    runner = CliRunner()
    list_res = runner.invoke(app_group, ["list", "--json"])
    assert list_res.exit_code == 0, list_res.output
    payload = json.loads(list_res.output)
    assert payload["ok"] is True
    assert payload["code"] == "OK"
    app_ids = {item["app_id"]: item for item in payload["data"]["items"]}
    assert "redis_12345" in app_ids
    assert app_ids["redis_12345"]["type"] == "store"
    assert app_ids["redis_12345"]["status"] == {"code": 1, "name": "active"}
    assert "wordpress_stale" in app_ids
    assert app_ids["wordpress_stale"]["status"] == {"code": 3, "name": "installing"}
    # Stale install must remain untouched in appInstalling after CLI list!
    assert tracking_id in appInstalling

    inspect_res = runner.invoke(app_group, ["inspect", "redis_12345", "--json"])
    assert inspect_res.exit_code == 0, inspect_res.output
    inspect_payload = json.loads(inspect_res.output)
    assert inspect_payload["ok"] is True
    assert inspect_payload["data"]["app"]["app_id"] == "redis_12345"
    assert "REDIS_PASSWORD" in inspect_payload["data"]["env_keys"]
    assert "supersecret" not in inspect_res.output

    missing_res = runner.invoke(app_group, ["inspect", "nonexistent_app", "--json"])
    assert missing_res.exit_code == 1
    missing_payload = json.loads(missing_res.output)
    assert missing_payload["ok"] is False
    assert missing_payload["code"] == "APP_NOT_FOUND"
    assert missing_payload["data"] is None
    assert tracking_id in appInstalling


def test_app_start_stop_restart_cli_commands(monkeypatch):
    from src.cli.app_commands import app_group
    from src.schemas.appResponse import AppResponse

    calls: list[tuple[str, str, int | None]] = []
    manager_module = types.ModuleType("src.services.app_manager")

    class FakeAppManger:
        def start_app(self, app_id, endpoint_id=None):
            calls.append(("start", app_id, endpoint_id))

        def stop_app(self, app_id, endpoint_id=None):
            calls.append(("stop", app_id, endpoint_id))

        def restart_app(self, app_id, endpoint_id=None):
            calls.append(("restart", app_id, endpoint_id))

        def get_app_by_id(self, app_id, endpoint_id=None, **kwargs):
            return AppResponse(
                app_id=app_id,
                endpointId=endpoint_id or 1,
                app_name="wordpress",
                app_official=True,
                status=1,
                containers=[{"Id": "c1", "Names": [f"/{app_id}"], "Image": "wordpress:6", "State": "running"}],
            )

    manager_module.AppManger = FakeAppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", manager_module)

    runner = CliRunner()
    for action in ("start", "stop", "restart"):
        res = runner.invoke(app_group, [action, "wp_123", "--endpoint-id", "2", "--json"])
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["ok"] is True
        assert body["data"]["action"] == action
        assert body["data"]["app_id"] == "wp_123"

    assert calls == [
        ("start", "wp_123", 2),
        ("stop", "wp_123", 2),
        ("restart", "wp_123", 2),
    ]


def test_overview_and_appstore_and_host_ports_cli(monkeypatch):
    from src.cli.appstore_commands import register_appstore_commands
    from src.cli.host_commands import host_group
    from src.cli.overview_commands import overview_group
    import click

    @click.group(name="appstore")
    def temp_appstore_group():
        pass

    register_appstore_commands(temp_appstore_group)

    metadata_module = types.ModuleType("src.services.product_metadata")
    metadata_module.read_product_metadata = lambda *, readonly: {
        "version": "2.5.0",
        "edition_key": "pro",
        "edition_name": "Professional",
        "max_apps": 20,
        "state_source": "runtime",
        "updated_by": "system",
        "updated_at": "2026-01-01T00:00:00Z",
        "note": None,
    }
    monkeypatch.setitem(sys.modules, "src.services.product_metadata", metadata_module)

    readiness_module = types.ModuleType("src.services.platform_readiness")

    class FakeReadinessService:
        def check(self):
            return True, []

        def check_setup(self):
            return False, ["appstore-sync"]

    readiness_module.PlatformReadinessService = FakeReadinessService
    monkeypatch.setitem(sys.modules, "src.services.platform_readiness", readiness_module)

    runner = CliRunner()
    ed_res = runner.invoke(overview_group, ["edition", "--json"])
    assert ed_res.exit_code == 0
    ed_payload = json.loads(ed_res.output)
    assert ed_payload["ok"] is True
    assert ed_payload["data"]["edition_key"] == "pro"

    ready_res = runner.invoke(overview_group, ["readiness", "--setup", "--json"])
    assert ready_res.exit_code == 0
    ready_payload = json.loads(ready_res.output)
    assert ready_payload["data"] == {"ready": False, "pending": ["appstore-sync"], "scope": "setup"}

    manager_module = types.ModuleType("src.services.app_manager")

    class FakeStoreAppManger:
        def get_available_apps(self, locale):
            return [
                {
                    "key": "wordpress",
                    "trademark": "WordPress",
                    "summary": "Blog and CMS",
                    "is_web_app": True,
                    "default_scheme": "http",
                    "vmmemory": 1,
                    "distribution": [{"key": "community", "value": ["6.4", "latest"]}],
                    "settings": {"W9_HTTP_PORT_SET": "9001"},
                    "profiles": {"external-db": {"is_external_database": True}},
                }
            ]

    manager_module.AppManger = FakeStoreAppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", manager_module)

    local_store_module = types.ModuleType("src.services.local_app_store")
    local_store_module.get_local_app_store_apps = lambda: []
    monkeypatch.setitem(sys.modules, "src.services.local_app_store", local_store_module)

    search_res = runner.invoke(temp_appstore_group, ["search", "word", "--json"])
    assert search_res.exit_code == 0
    search_payload = json.loads(search_res.output)
    assert search_payload["data"]["total"] == 1
    assert search_payload["data"]["items"][0]["key"] == "wordpress"

    info_res = runner.invoke(temp_appstore_group, ["info", "wordpress", "--json"])
    assert info_res.exit_code == 0
    info_payload = json.loads(info_res.output)
    assert info_payload["data"]["template"]["key"] == "wordpress"
    assert "external-db" in info_payload["data"]["template"]["profiles"]

    port_module = types.ModuleType("src.services.port_allocator")
    port_module.read_port_range = lambda: (9001, 9099)
    port_module.check_ports = lambda ports: [{"port": p, "available": p != 9001, "reason": "container" if p == 9001 else None} for p in ports]
    port_module.suggest_ports = lambda keys: [{"key": k, "port": 9002 + idx} for idx, k in enumerate(keys)]
    monkeypatch.setitem(sys.modules, "src.services.port_allocator", port_module)

    ports_check = runner.invoke(host_group, ["ports", "check", "9001,9002", "--json"])
    assert ports_check.exit_code == 0
    ports_payload = json.loads(ports_check.output)
    assert ports_payload["data"]["all_available"] is False
    assert len(ports_payload["data"]["items"]) == 2

    ports_suggest = runner.invoke(host_group, ["ports", "suggest", "--count", "2", "--json"])
    assert ports_suggest.exit_code == 0
    suggest_payload = json.loads(ports_suggest.output)
    assert [item["port"] for item in suggest_payload["data"]["items"]] == [9002, 9003]


def test_docker_container_inspect_and_logs_masking_and_decoding(monkeypatch):
    from src.cli.docker_commands import docker_group

    raw_logs = (
        _make_docker_frame(1, "Starting service with MYSQL_PASSWORD=mysecretpass\n")
        + _make_docker_frame(2, "Connecting to redis://user:topsecret@127.0.0.1:6379/0\n")
    )

    class FakePortainerAPI:
        def read_container_logs_bounded(self, endpoint_id, container_id, params, max_bytes=1048576, timeout_seconds=20):
            return raw_logs, False

    class FakePortainerManager:
        def __init__(self):
            self.portainer = FakePortainerAPI()

        def get_local_endpoint_id(self):
            return 1

        def get_containers(self, endpoint_id):
            return [
                {
                    "Id": "abc123def456",
                    "Names": ["/wp_db"],
                    "Image": "mysql:8.0",
                    "State": "running",
                    "Status": "Up 5 minutes",
                    "Labels": {"com.docker.compose.project": "wp"},
                }
            ]

        def get_container_by_id(self, endpoint_id, container_id):
            return {
                "Id": container_id,
                "Name": "/wp_db",
                "Config": {"Image": "mysql:8.0"},
                "State": {"Status": "running", "Running": True, "ExitCode": 0, "OOMKilled": False},
                "RestartCount": 1,
                "NetworkSettings": {"Networks": {"websoft9": {"IPAddress": "172.18.0.5", "Gateway": "172.18.0.1"}}},
                "Mounts": [{"Type": "volume", "Name": "wp_db_data", "Destination": "/var/lib/mysql", "RW": True, "Source": "/var/lib/docker/volumes/secret"}],
            }

    pm_module = types.ModuleType("src.services.portainer_manager")
    pm_module.PortainerManager = FakePortainerManager
    monkeypatch.setitem(sys.modules, "src.services.portainer_manager", pm_module)

    runner = CliRunner()
    inspect_res = runner.invoke(docker_group, ["container", "inspect", "wp_db", "--json"])
    assert inspect_res.exit_code == 0, inspect_res.output
    inspect_payload = json.loads(inspect_res.output)
    assert inspect_payload["data"]["name"] == "wp_db"
    # Host source path must not be exposed in mount projection
    assert "Source" not in json.dumps(inspect_payload["data"]["mounts"])

    logs_res = runner.invoke(docker_group, ["container", "logs", "wp_db", "--tail", "50", "--since", "15m", "--json"])
    assert logs_res.exit_code == 0, logs_res.output
    logs_payload = json.loads(logs_res.output)
    assert logs_payload["ok"] is True
    entries = logs_payload["data"]["entries"]
    assert len(entries) == 2
    assert entries[0]["stream"] == "stdout"
    assert "mysecretpass" not in entries[0]["text"]
    assert "******" in entries[0]["text"]
    assert entries[1]["stream"] == "stderr"
    assert "topsecret" not in entries[1]["text"]
    assert "******" in entries[1]["text"]
