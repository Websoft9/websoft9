from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest
from click.testing import CliRunner
from starlette.requests import Request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.parametrize("content", [
    "password: fixture-value",
    '{"password": "fixture-value", "safe": "visible"}',
    'prefix {"credentials": {"first": "fixture-value", "second": "another-value"}}',
    "DB_PASSWORD='fixture-value'",
    'PASSWORD="fixture-value with spaces"',
    "password: |\n  fixture-value\n  another-value\nsafe: visible\n",
    "credentials:\n  first: fixture-value\n  second: another-value\nsafe: visible\n",
    "+  password: >-\n+    fixture-value\n+    another-value\n+  safe: visible\n",
    'prefix {"message": "password: fixture-value"}',
])
def test_text_secrets_are_masked_before_display(content):
    from src.cli.cli_output import mask_sensitive_text, sanitize_value

    masked = mask_sensitive_text(content)
    assert "fixture-value" not in masked
    assert "another-value" not in masked
    assert "******" in masked
    assert "fixture-value" not in json.dumps(sanitize_value({"content": content}))
    if "visible" in content:
        assert "visible" in masked


def test_sensitive_presence_flags_only_bypass_masking_when_boolean():
    from src.cli.cli_output import sanitize_value

    assert sanitize_value({"has_password": True, "is_token": False}) == {"has_password": True, "is_token": False}
    assert sanitize_value({"has_password": "fixture-value"})["has_password"] == "******"


def test_dependency_status_is_not_reclassified_by_message():
    from src.cli.cli_output import map_exception
    from src.core.exception import CustomException

    assert map_exception(CustomException(503, "Unavailable", "Upstream not found")).code == "DEPENDENCY_UNAVAILABLE"


def test_upgrade_prepare_is_dispatched_to_authenticated_apphub(tmp_path, monkeypatch):
    from src.cli.settings_commands import settings_group
    from src.cli import upgrade_dispatch
    from src.services.upgrade_manager import UpgradeManager

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-dispatch-key\n", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    start = MagicMock(side_effect=AssertionError("No worker may start inside CLI"))
    monkeypatch.setattr(UpgradeManager, "start_prepare", start)
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"state": "downloading", "run_id": "server-run"}).encode()

    def open_request(request, timeout):
        captured.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout)
        return Response()

    opener = MagicMock(side_effect=open_request)
    monkeypatch.setattr(upgrade_dispatch, "urlopen", opener)
    denied = CliRunner().invoke(settings_group, ["upgrade", "prepare", "--json"])
    assert denied.exit_code == 1
    opener.assert_not_called()
    result = CliRunner().invoke(settings_group, ["upgrade", "prepare", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"]["run_id"] == "server-run"
    assert captured["url"] == upgrade_dispatch.UPGRADE_PREPARE_URL
    assert captured["timeout"] == 5
    assert captured["headers"]["X-websoft9-upgrade-dispatch-secret"] == "fixture-dispatch-key"
    start.assert_not_called()


def test_upgrade_dispatch_rejects_http_and_invalid_responses(tmp_path, monkeypatch):
    from src.cli import upgrade_dispatch
    from src.cli.settings_commands import settings_group

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    monkeypatch.setattr(upgrade_dispatch, "urlopen", MagicMock(side_effect=HTTPError(
        upgrade_dispatch.UPGRADE_PREPARE_URL, 409, "Conflict", {}, io.BytesIO(b"")
    )))
    result = CliRunner().invoke(settings_group, ["upgrade", "prepare", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize("payload", [[], {"started": True}, {"state": "downloading"}])
def test_upgrade_dispatch_requires_a_server_run_acknowledgment(payload, tmp_path, monkeypatch):
    from src.cli import upgrade_dispatch
    from src.cli.settings_commands import settings_group

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    monkeypatch.setattr(upgrade_dispatch, "urlopen", MagicMock(return_value=response))
    result = CliRunner().invoke(settings_group, ["upgrade", "prepare", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["ok"] is False


def test_upgrade_dispatch_transport_failure_is_a_dependency_error(tmp_path, monkeypatch):
    from src.cli import upgrade_dispatch
    from src.cli.settings_commands import settings_group

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    monkeypatch.setattr(upgrade_dispatch, "urlopen", MagicMock(side_effect=URLError("Connection refused")))
    result = CliRunner().invoke(settings_group, ["upgrade", "prepare", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["code"] == "DEPENDENCY_UNAVAILABLE"


def test_upgrade_internal_route_requires_dispatch_credential(tmp_path, monkeypatch):
    from src.api.v1.routers import settings
    from src.core.exception import CustomException

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    start = MagicMock(return_value={"state": "downloading", "run_id": "server-run"})
    monkeypatch.setattr(settings, "UpgradeManager", lambda: MagicMock(start_prepare=start))
    with pytest.raises(CustomException) as error:
        settings.dispatch_prepare(Request({"type": "http", "headers": []}))
    assert error.value.status_code == 403
    start.assert_not_called()
    request = Request({"type": "http", "headers": [(b"x-websoft9-upgrade-dispatch-secret", b"fixture-key")]})
    assert settings.dispatch_prepare(request)["run_id"] == "server-run"
    start.assert_called_once()


def test_upgrade_internal_route_is_reachable_through_production_app(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.v1.routers import settings
    from src.main import app

    secret = tmp_path / "trust_key"
    secret.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret))
    start = MagicMock(return_value={"state": "downloading", "run_id": "server-run"})
    monkeypatch.setattr(settings, "UpgradeManager", lambda: MagicMock(start_prepare=start))
    client = TestClient(app)
    assert client.post("/api/settings/internal/upgrade/prepare").status_code == 403
    start.assert_not_called()
    response = client.post(
        "/api/settings/internal/upgrade/prepare",
        headers={"x-websoft9-upgrade-dispatch-secret": "fixture-key"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["run_id"] == "server-run"
    start.assert_called_once()


def test_install_state_readonly_fails_explicitly_without_creating_storage(tmp_path):
    from src.services.app_status import InstallStateStore
    from src.core.exception import CustomException

    store = InstallStateStore(str(tmp_path / "tracking"), initialize=False)
    with pytest.raises(FileNotFoundError):
        store.list_tasks_readonly((3, 4, 6))
    assert not store.data_dir.exists()
    store.data_dir.mkdir()
    store.database_file.write_bytes(b"invalid sqlite contents")
    with pytest.raises(CustomException) as error:
        store.list_tasks_readonly((3,))
    assert error.value.status_code == 503
    assert store.database_file.read_bytes() == b"invalid sqlite contents"


def test_custom_fields_and_tracking_readonly_do_not_initialize(tmp_path, monkeypatch):
    from src.services.app_status import InstallStateStore

    store = InstallStateStore(str(tmp_path))
    fields = [{"field_name": "owner", "field_value": "operator", "field_type": "text"}]
    store.save_custom_fields("demo", fields)
    tracking_id = store.create_task("demo", "Demo")
    monkeypatch.setattr(store, "_ensure_storage", MagicMock(side_effect=AssertionError("Unexpected initialization")))
    monkeypatch.setattr(store, "_raw_connect", MagicMock(side_effect=AssertionError("Unexpected writable connection")))
    assert store.get_custom_fields("demo", readonly=True)[0]["field_value"] == "operator"
    assert dict(store.list_tasks_readonly((3,)))[tracking_id]["app_id"] == "demo"


def test_db_list_is_readonly_and_propagates_upstream_failure(monkeypatch):
    from src.cli.apphub_cli import cli
    from src.core.exception import CustomException
    from src.services.app_manager import AppManger

    source = MagicMock(side_effect=CustomException(503, "Unavailable", "Inventory backend offline"))
    monkeypatch.setattr(AppManger, "get_apps", source)
    result = CliRunner().invoke(cli, ["app", "database", "list", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["code"] == "DEPENDENCY_UNAVAILABLE"
    source.assert_called_once_with(None, "en", reconcile_stale=False, readonly_install_state=True)


def test_container_stats_uses_selected_portainer_endpoint(monkeypatch):
    from src.cli import docker_commands
    from src.services.portainer_manager import PortainerManager
    from src.external.portainer_api import PortainerAPI

    api = MagicMock()
    api.get_container_stats.return_value = MagicMock(status_code=200, json=lambda: {
        "memory_stats": {"usage": 256, "limit": 1024}, "pids_stats": {"current": 2},
    })
    manager = object.__new__(PortainerManager)
    manager.portainer = api
    manager.get_containers = MagicMock(return_value=[{"Id": "remote-id", "Names": ["/remote"]}])
    monkeypatch.setattr("src.services.portainer_manager.PortainerManager", lambda: manager)
    monkeypatch.setattr(docker_commands, "_resolve_endpoint_id", lambda *_args: 77)
    result = CliRunner().invoke(docker_commands.docker_group, ["container", "stats", "remote", "--endpoint-id", "77", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"]["memory_percent"] == 25.0
    api.get_container_stats.assert_called_once_with(77, "remote-id")

    portainer = object.__new__(PortainerAPI)
    portainer.api = MagicMock()
    PortainerAPI.get_container_stats.__wrapped__(portainer, 77, "remote-id")
    portainer.api.get.assert_called_once_with(
        path="endpoints/77/docker/containers/remote-id/stats", params={"stream": "false"}
    )


def test_task_collectors_are_readonly_and_do_not_reconcile(tmp_path, monkeypatch):
    from src.services.scheduled_tasks import ScheduledTaskService
    from src.core.exception import CustomException

    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=MagicMock(), host_access_service=MagicMock())
    with pytest.raises(CustomException) as error:
        service.collect_tasks_local()
    assert error.value.status_code == 503
    assert not service.data_dir.exists()
    service._ensure_storage()
    log = tmp_path / "run.log"
    log.write_text("one\ntwo\nthree\n", encoding="utf-8")
    task_id = "system:log-cleanup"
    with service._db_connect() as connection:
        connection.execute(
            "INSERT INTO scheduled_task_runs VALUES (?, ?, ?, NULL, ?, ?, ?, ?)",
            ("fixture-run", task_id, "2026-10-20T00:00:00Z", "running", None, "cron", str(log)),
        )
        connection.commit()
        before = "\n".join(connection.iterdump())
    for method in ("_ensure_storage", "reconcile_prewarm_state", "_sync_task_runs", "_db_connect"):
        monkeypatch.setattr(service, method, MagicMock(side_effect=AssertionError(f"Unexpected {method}")))
    assert service.collect_tasks_local()["system_tasks"]
    assert service.collect_runs_local(task_id)["runs"][0]["status"] == "running"
    assert service.collect_run_log_local(task_id, "fixture-run")["content"] == "one\ntwo\nthree"
    with sqlite3.connect(f"{service.database_file.as_uri()}?mode=ro", uri=True) as connection:
        assert "\n".join(connection.iterdump()) == before


def test_cli_log_scan_is_bounded_and_small_log_pagination_is_preserved(tmp_path, monkeypatch):
    from src.services.scheduled_tasks import ScheduledTaskService
    from src.core.exception import CustomException

    service = ScheduledTaskService(data_dir=str(tmp_path), auth_service=MagicMock(), host_access_service=MagicMock())
    log = tmp_path / "large.log"
    log.write_bytes(b"large-line\n" * 200000 + b"tail-marker\n")
    original_open = Path.open
    sizes = []

    class Reader:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.handle.close()

        def seek(self, *args):
            return self.handle.seek(*args)

        def read(self, size=-1):
            sizes.append(size)
            assert 0 <= size <= service._log_read_byte_limit
            return self.handle.read(size)

    def open_log(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        return Reader(handle) if path == log else handle

    monkeypatch.setattr(Path, "open", open_log)
    result = service._read_log_window(log, None, max_scan_bytes=service._log_read_byte_limit)
    assert result["truncated"] is True
    assert "tail-marker" in result["content"]
    assert result["next_before"] is None
    assert sum(sizes) <= service._log_read_byte_limit
    with pytest.raises(CustomException):
        service._read_log_window(log, 100, max_scan_bytes=service._log_read_byte_limit)
    small = tmp_path / "small.log"
    small.write_text("\n".join(str(number) for number in range(300)), encoding="utf-8")
    page = service._read_log_window(small, None, max_scan_bytes=service._log_read_byte_limit)
    assert page["next_before"] == 100
    previous = service._read_log_window(small, page["next_before"], max_scan_bytes=service._log_read_byte_limit)
    assert previous["content"].splitlines() == [str(number) for number in range(100)]
