"""Regression tests for variables that were used before being guaranteed bound.

Each case below used to raise ``UnboundLocalError`` (or silently use a stale
value) and surface as an opaque 500 to the caller.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.schemas.appInstall import appInstall
from src.services import app_manager as app_manager_module
from src.services.app_manager import AppManger
from src.services.scheduled_tasks import ScheduledTaskService


class FakeAuthService:
    def _require_authenticated_operator(self, session_token):
        if session_token != "valid-session":
            raise RuntimeError("invalid session")
        return {"id": "operator-1", "username": "operator"}


# ── create_installation_tracking ──────────────────────────────────────────


def _install_payload(**overrides):
    data = {
        "app_name": "wordpress",
        "edition": {"dist": "community", "version": "6.0"},
        "app_id": "wordpress",
        "proxy_enabled": False,
        "domain_names": ["192.0.2.10"],
        "settings": None,
        "profile": None,
    }
    data.update(overrides)
    return appInstall(**data)


def test_installation_tracking_still_works_when_the_app_library_is_unreadable(monkeypatch):
    """A broken system.ini used to leave ``app_directory`` unbound."""
    captured = {}

    def exploding_config(*_args, **_kwargs):
        raise OSError("system.ini is not readable")

    def fake_start(app_id, app_name, app_uuid=None, reserved_ports=None):
        captured.update(app_id=app_id, app_name=app_name, reserved_ports=reserved_ports)
        return "tracking-id"

    monkeypatch.setattr(app_manager_module, "ConfigManager", exploding_config)
    monkeypatch.setattr(app_manager_module, "start_app_installation", fake_start)

    tracked_app_id, tracking_id = AppManger().create_installation_tracking(_install_payload())

    assert tracking_id == "tracking-id"
    assert tracked_app_id.startswith("wordpress_")
    assert captured["app_id"] == tracked_app_id
    assert captured["app_name"] == "wordpress"
    assert captured["reserved_ports"] == set()


# ── list_prewarm_records ──────────────────────────────────────────────────


def _service(tmp_path, monkeypatch):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "cron"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )
    monkeypatch.setattr(service, "reconcile_prewarm_state", lambda: None)
    monkeypatch.setattr(service, "dispatch_prewarm", lambda: None)
    return service


def test_prewarm_records_name_each_run_after_its_own_task(tmp_path, monkeypatch):
    """Records used to be labelled with the last task left over from a loop."""
    service = _service(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "_now_iso", lambda: "2026-10-10T09:00:00+08:00")
    mysql = service.enqueue_prewarm("valid-session", "mysql", "9.1")
    gitea = service.enqueue_prewarm("valid-session", "gitea", "1.27")

    records = service.list_prewarm_records("valid-session")["runs"]

    names = {record["task_id"]: record["name"] for record in records}
    assert names == {mysql["task_id"]: "mysql 9.1", gitea["task_id"]: "gitea 1.27"}
    assert all(record["retry_blocked"] is True for record in records)
