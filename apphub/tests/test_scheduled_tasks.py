import subprocess
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import scheduled_tasks as scheduled_tasks_router
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME
from src.services.scheduled_tasks import SKIPPED_EXIT_CODE, SYSTEM_TASKS, ScheduledTaskService
from fastapi.responses import JSONResponse


class FakeAuthService:
    def _require_authenticated_operator(self, session_token):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")
        return {"id": "operator-1"}


class FakeHostClient:
    def __init__(self, output="Asia/Shanghai"):
        self.output = output

    def exec_command(self, _command, timeout):
        output = self.output

        class Channel:
            @staticmethod
            def recv_exit_status():
                return 0

        class Output:
            channel = Channel()

            @staticmethod
            def read():
                return output.encode()

        class Error:
            @staticmethod
            def read():
                return b""

        return None, Output(), Error()


class FakeHostAccessService:
    def __init__(self, timezone_name="Asia/Shanghai"):
        self.timezone_name = timezone_name

    def get_connection_profile(self, session_token, profile_id):
        assert session_token == "valid-session"
        assert profile_id == "profile-1"
        return {"profile_id": profile_id}

    class _ClientContext:
        def __init__(self, timezone_name):
            self.timezone_name = timezone_name

        def __enter__(self):
            return FakeHostClient(self.timezone_name)

        def __exit__(self, *_args):
            return False

    def _open_file_client(self, _profile):
        return self._ClientContext(self.timezone_name)


class FakeHostTaskClient:
    def __init__(self):
        self.commands = []

    def exec_command(self, command, timeout):
        self.commands.append(command)

        class Channel:
            @staticmethod
            def recv_exit_status():
                return 0

        class Output:
            channel = Channel()

            @staticmethod
            def read():
                return b"/home/operator"

        class Error:
            @staticmethod
            def read():
                return b""

        return None, Output(), Error()


class FakeHostTaskAccessService(FakeHostAccessService):
    def __init__(self):
        self.client = FakeHostTaskClient()

    class _ClientContext:
        def __init__(self, client):
            self.client = client

        def __enter__(self):
            return self.client

        def __exit__(self, *_args):
            return False

    def _open_file_client(self, _profile):
        return self._ClientContext(self.client)


class RecoveringHostTaskAccessService(FakeHostTaskAccessService):
    def __init__(self):
        super().__init__()
        self.available = False

    def _open_file_client(self, profile):
        if not self.available:
            raise CustomException(400, "SSH Authentication Failed", "Authentication failed")
        return super()._open_file_client(profile)


def create_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(CustomException)
    async def custom_exception_handler(_request, exc: CustomException):
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(message=exc.message, details=exc.details).model_dump())

    app.include_router(scheduled_tasks_router.router)
    return app


@pytest.fixture(autouse=True)
def clear_host_capability_cache():
    ScheduledTaskService._host_capability_cache.clear()
    yield
    ScheduledTaskService._host_capability_cache.clear()


def test_platform_task_crud_renders_cron_and_preserves_operator_isolation(monkeypatch, tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )
    monkeypatch.setattr(scheduled_tasks_router, "_scheduled_task_service", service)

    with TestClient(create_test_app()) as client:
        created = client.post(
            "/scheduled-tasks",
            headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"},
            json={"name": "Date", "schedule": "* * * * *", "command": "date", "enabled": True},
        )
        assert created.status_code == 201
        task = created.json()
        assert task["sync_status"] == "synced"
        assert "* * * * * root" in (tmp_path / "websoft9-tasks").read_text(encoding="utf-8")
        assert (tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh").is_file()

        listed = client.get("/scheduled-tasks", headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"})
        assert listed.status_code == 200
        payload = listed.json()
        assert [item["name"] for item in payload["tasks"]] == ["Date"]
        # The platform's own tasks are exposed beside them, marked as system-owned.
        assert {item["task_id"] for item in payload["system_tasks"]} == {
            definition["task_id"] for definition in SYSTEM_TASKS
        }
        assert all(item["origin"] == "system" for item in payload["system_tasks"])

        toggled = client.post(
            f"/scheduled-tasks/{task['task_id']}/toggle",
            headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"},
            json={"enabled": False},
        )
        assert toggled.status_code == 200
        assert task["task_id"] not in (tmp_path / "websoft9-tasks").read_text(encoding="utf-8")

        deleted = client.delete(f"/scheduled-tasks/{task['task_id']}", headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"})
        assert deleted.status_code == 204
        assert not (tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh").exists()


def test_reconcile_local_schedule_rebuilds_only_enabled_container_tasks(tmp_path):
    cron_file = tmp_path / "websoft9-tasks"
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(cron_file),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=host_access,
    )
    enabled = service.create_task("valid-session", {"name": "Enabled", "schedule": "* * * * *", "command": "date"})
    disabled = service.create_task("valid-session", {"name": "Disabled", "schedule": "* * * * *", "command": "echo disabled", "enabled": False})
    host_task = service.create_task(
        "valid-session", {"name": "Remote", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"}
    )

    cron_file.unlink()
    (tmp_path / "tasks" / "scripts" / f"{enabled['task_id']}.sh").unlink()
    remote_commands_before_reconcile = len(host_access.client.commands)
    service.reconcile_local_schedule()

    cron = cron_file.read_text(encoding="utf-8")
    assert enabled["task_id"] in cron
    assert disabled["task_id"] not in cron
    assert host_task["task_id"] not in cron
    assert (tmp_path / "tasks" / "scripts" / f"{enabled['task_id']}.sh").is_file()
    assert not (tmp_path / "tasks" / "scripts" / f"{disabled['task_id']}.sh").exists()
    assert len(host_access.client.commands) == remote_commands_before_reconcile


def test_internal_one_time_schedule_is_not_rendered_to_cron(tmp_path):
    cron_file = tmp_path / "websoft9-tasks"
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(cron_file),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )
    task = service.create_task("valid-session", {"name": "Internal", "schedule": "* * * * *", "command": "date"})

    with service._db_connect() as connection:
        connection.execute("UPDATE scheduled_tasks SET schedule = '@once' WHERE task_id = ?", (task["task_id"],))
        connection.commit()

    service.reconcile_local_schedule()

    assert task["task_id"] not in cron_file.read_text(encoding="utf-8")
    assert service._next_run("@once") is None
    assert service._normalize_payload({"name": "Internal", "schedule": "@once", "command": "date"}, allow_once=True)["schedule"] == "@once"
    with pytest.raises(CustomException):
        service.create_task("valid-session", {"name": "External", "schedule": "@once", "command": "date"})


def test_enqueue_prewarm_creates_and_reuses_one_time_task(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )

    created = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    reused = service.enqueue_prewarm("valid-session", "wordpress", "6.3")

    assert created["task_id"] == reused["task_id"]
    assert created["schedule"] == "@once"
    assert created["category"] == "prewarm"
    assert created["subject_app"] == "wordpress"
    assert created["subject_version"] == "6.3"
    assert created["queue_state"] == "queued"
    assert "images prewarm --app wordpress --version 6.3" in created["command"]
    assert (tmp_path / "tasks" / "scripts" / f"{created['task_id']}.sh").is_file()


def test_enqueue_prewarm_api_authenticates_and_returns_accepted(monkeypatch, tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )
    monkeypatch.setattr(scheduled_tasks_router, "_scheduled_task_service", service)

    with TestClient(create_test_app()) as client:
        response = client.post(
            "/scheduled-tasks/prewarm",
            headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"},
            json={"app_name": "wordpress", "version": "6.3"},
        )

    assert response.status_code == 202
    assert response.json()["queue_state"] == "running"


def test_dispatch_prewarm_claims_and_starts_oldest_task(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    monkeypatch.setenv("WEBSOFT9_PREWARM_INSTANCE_ID_FILE", str(tmp_path / "instance-id"))
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")

    class Process:
        pid = 12345

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: Process())
    result = service.dispatch_prewarm()

    assert result == {"status": "started", "task_id": task["task_id"]}
    refreshed = service._get_task("operator-1", task["task_id"])
    assert refreshed["queue_state"] == "running"
    assert refreshed["runner_pgid"] == 12345
    with pytest.raises(CustomException):
        service.run_task("valid-session", task["task_id"])


def test_dispatch_prewarm_requeues_task_claimed_by_old_instance(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    monkeypatch.setenv("WEBSOFT9_PREWARM_INSTANCE_ID_FILE", str(tmp_path / "instance-id"))
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    service._write_task(task["task_id"], queue_state="running", claimed_by="old-instance", runner_pgid=12345)

    class Process:
        pid = 5678

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: Process())
    result = service.dispatch_prewarm()

    assert result == {"status": "started", "task_id": task["task_id"]}
    refreshed = service._get_task("operator-1", task["task_id"])
    assert refreshed["claimed_by"] != "old-instance"
    assert refreshed["runner_pgid"] == 5678


def test_dispatch_prewarm_recovers_missing_runner_before_starting_next(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    monkeypatch.setenv("WEBSOFT9_PREWARM_INSTANCE_ID_FILE", str(tmp_path / "instance-id"))
    first = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    second = service.enqueue_prewarm("valid-session", "nginx", "1.27")
    service._write_task(first["task_id"], queue_state="running", runner_pgid=12345)
    monkeypatch.setattr(ScheduledTaskService, "_prewarm_runner_alive", staticmethod(lambda _pgid: False))

    class Process:
        pid = 5678

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: Process())
    result = service.dispatch_prewarm()

    assert result == {"status": "started", "task_id": first["task_id"]}
    assert service._get_task("operator-1", second["task_id"])["queue_state"] == "queued"


def test_cancel_running_prewarm_preserves_cancelled_state(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    service._write_task(task["task_id"], queue_state="running", runner_pgid=12345)
    calls = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))
    monkeypatch.setattr(ScheduledTaskService, "_prewarm_runner_alive", staticmethod(lambda _pgid: False))

    service.cancel_prewarm("valid-session", task["task_id"])
    refreshed = service._get_task("operator-1", task["task_id"])

    assert refreshed["queue_state"] == "cancelled"
    assert refreshed["last_status"] == "cancelled"
    assert refreshed["runner_pgid"] is None
    assert calls == [(12345, signal.SIGTERM)]


def test_cancel_running_prewarm_escalates_when_the_run_survives(monkeypatch, tmp_path):
    """`timeout` moves the pull into its own process group, so the whole session is signalled."""
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    service._write_task(task["task_id"], queue_state="running", runner_pgid=4321)
    group_calls = []
    pid_calls = []
    # 4322 stands for the CLI that `timeout` left behind in its own group of the same session.
    survivors = {"pids": [4322]}
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: group_calls.append((pgid, sig)))
    monkeypatch.setattr(os, "kill", lambda pid, sig: pid_calls.append((pid, sig)))
    monkeypatch.setattr(ScheduledTaskService, "_prewarm_session_pids", staticmethod(lambda _sid: list(survivors["pids"])))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    service.cancel_prewarm("valid-session", task["task_id"])

    assert group_calls == [(4321, signal.SIGTERM), (4321, signal.SIGKILL)]
    assert pid_calls == [(4322, signal.SIGTERM), (4322, signal.SIGKILL)]


def test_cancelled_run_is_not_reopened_by_the_runner_record(monkeypatch, tmp_path):
    """The runner writes "running" while a run lives; that must not revive a run already closed."""
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    task_id = task["task_id"]
    started_at = service._now_iso()
    record = {"run_id": "run-1", "task_id": task_id, "started_at": started_at, "finished_at": "", "status": "running", "exit_code": None, "trigger": "manual", "log_path": ""}
    with service._db_connect() as connection:
        connection.execute(
            "INSERT INTO scheduled_task_runs (run_id, task_id, started_at, finished_at, status, exit_code, trigger, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-1", task_id, started_at, service._now_iso(), "cancelled", None, "manual", ""),
        )
        connection.commit()

    service._sync_task_run_records(service._get_task("operator-1", task_id), [record])

    with service._db_connect() as connection:
        row = connection.execute("SELECT status, finished_at FROM scheduled_task_runs WHERE run_id = 'run-1'").fetchone()
    assert row["status"] == "cancelled"


def test_cancel_prewarm_closes_the_running_run_and_annotates_its_log(monkeypatch, tmp_path):
    """A cancelled pull never writes its own result, so the history must not stay on `running`."""
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "cron"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.enqueue_prewarm("valid-session", "wordpress", "6.3")
    service._write_task(task["task_id"], queue_state="running", runner_pgid=999)
    log_path = tmp_path / "tasks" / "run.log"
    log_path.write_text("START trigger=manual\n", encoding="utf-8")
    with service._db_connect() as connection:
        connection.execute(
            "INSERT INTO scheduled_task_runs (run_id, task_id, started_at, finished_at, status, exit_code, trigger, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-cancelled", task["task_id"], "2026-01-01T00:00:00+00:00", "", "running", None, "manual", str(log_path)),
        )
        connection.commit()
    monkeypatch.setattr(os, "killpg", lambda _pgid, _sig: None)
    monkeypatch.setattr(ScheduledTaskService, "_prewarm_runner_alive", staticmethod(lambda _pgid: False))

    service.cancel_prewarm("valid-session", task["task_id"])

    with service._db_connect() as connection:
        run = connection.execute("SELECT status, finished_at FROM scheduled_task_runs WHERE run_id = 'run-cancelled'").fetchone()
    assert run["status"] == "cancelled"
    assert run["finished_at"]
    assert "CANCELLED by operator" in log_path.read_text(encoding="utf-8")


def test_reconcile_local_schedule_initializes_empty_storage(tmp_path):
    data_dir = tmp_path / "tasks"
    cron_file = tmp_path / "websoft9-tasks"
    service = ScheduledTaskService(
        data_dir=str(data_dir),
        cron_file=str(cron_file),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )

    service.reconcile_local_schedule()

    assert (data_dir / "scheduled-tasks.sqlite").is_file()
    assert cron_file.is_file()
    # A store with no operator task still schedules the platform's own maintenance jobs.
    cron = cron_file.read_text(encoding="utf-8")
    for definition in SYSTEM_TASKS:
        assert definition["task_id"] in cron


def test_scheduled_task_defaults_and_history_retention(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )

    task = service.create_task("valid-session", {"name": "Defaults", "schedule": "* * * * *", "command": "date"})

    assert task["timeout_seconds"] == 30
    assert task["retry_count"] == 3
    assert service._run_retention_count == 20
    assert service._run_retention_days == 3


def test_platform_timezone_uses_container_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")

    assert ScheduledTaskService._platform_timezone() == "Asia/Shanghai"


def test_reconcile_local_schedule_updates_existing_container_task_timezone(monkeypatch, tmp_path):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )
    task = service.create_task("valid-session", {"name": "Timezone", "schedule": "* * * * *", "command": "date"})
    service._write_task(task["task_id"], timezone="UTC")

    service.reconcile_local_schedule()

    assert service._get_task("operator-1", task["task_id"])["timezone"] == "Asia/Shanghai"


def test_host_uploaded_task_marks_unreachable_when_upload_fails(monkeypatch, tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=FakeHostTaskAccessService(),
    )
    monkeypatch.setattr(service, "_store_uploaded_script", lambda *_args: (_ for _ in ()).throw(CustomException(503, "Scheduled Task Upload Failed", "Host unavailable")))

    with pytest.raises(CustomException):
        service.create_task(
            "valid-session",
            {"name": "Remote upload", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "execution_mode": "upload", "script_content": "echo task"},
        )

    task = service._list_tasks("operator-1")[0]
    assert task["sync_status"] == "unreachable"


def test_delete_host_task_succeeds_when_host_is_unreachable(monkeypatch, tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=FakeHostTaskAccessService(),
    )
    task = service.create_task(
        "valid-session",
        {"name": "Remote", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"},
    )
    monkeypatch.setattr(
        service,
        "_sync_host_tasks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(CustomException(503, "Scheduled Task Host Unavailable", "Host is unavailable")),
    )

    service.delete_task("valid-session", task["task_id"])

    assert service._list_tasks("operator-1") == []


def test_platform_task_rejects_profile_on_container_target(monkeypatch, tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    monkeypatch.setattr(scheduled_tasks_router, "_scheduled_task_service", service)

    with TestClient(create_test_app()) as client:
        response = client.post(
            "/scheduled-tasks",
            headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"},
            json={"name": "Remote", "target": "container", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"},
        )

    assert response.status_code == 400


def test_platform_task_accepts_multiline_shell_command(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )

    task = service.create_task("valid-session", {"name": "Multiline", "schedule": "* * * * *", "command": "echo first\necho second"})

    runner = (tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh").read_text(encoding="utf-8")
    assert "echo first\necho second" in runner


def test_delete_restores_cron_file_when_reload_fails(tmp_path):
    reload_attempts = []

    def reload_cron():
        reload_attempts.append(True)
        if len(reload_attempts) == 2:
            raise RuntimeError("cron reload failed")

    cron_file = tmp_path / "websoft9-tasks"
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(cron_file), auth_service=FakeAuthService(), cron_reloader=reload_cron
    )
    task = service.create_task("valid-session", {"name": "Date", "schedule": "* * * * *", "command": "date"})

    try:
        service.delete_task("valid-session", task["task_id"])
    except RuntimeError as exc:
        assert str(exc) == "cron reload failed"
    else:
        raise AssertionError("Expected cron reload failure")

    assert task["task_id"] in cron_file.read_text(encoding="utf-8")
    assert service.list_tasks("valid-session")["tasks"][0]["task_id"] == task["task_id"]


def test_public_task_always_returns_a_future_next_run(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    task = service.create_task("valid-session", {"name": "Date", "schedule": "* * * * *", "command": "date"})

    assert task["next_run_at"] > service._now_iso()


def test_public_task_exposes_execution_path(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    task = service.create_task("valid-session", {"name": "Date", "schedule": "* * * * *", "command": "date"})
    published = service.list_tasks("valid-session")["tasks"][0]
    assert published["execution_path"] == str(tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh")

    service.create_task("valid-session", {"name": "PathMode", "schedule": "* * * * *", "execution_mode": "path", "script_path": "/usr/local/bin/backup.sh"})
    tasks = service.list_tasks("valid-session")["tasks"]
    path_task = next(item for item in tasks if item["name"] == "PathMode")
    assert path_task["execution_path"] == "/usr/local/bin/backup.sh"


def test_execution_path_for_host_tasks_uses_remote_scheduled_tasks_root(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    assert service._execution_path({"task_id": "t-1", "target": "host", "execution_mode": "command", "script_path": None}) == "~/.local/state/websoft9/scheduled-tasks/scripts/t-1.sh"
    assert service._execution_path({"task_id": "t-1", "target": "host", "execution_mode": "upload", "script_path": None}) == "~/.local/state/websoft9/scheduled-tasks/uploads/t-1.sh"


def test_task_list_orders_by_creation_time_descending(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    first = service.create_task("valid-session", {"name": "First", "schedule": "* * * * *", "command": "date"})
    second = service.create_task("valid-session", {"name": "Second", "schedule": "* * * * *", "command": "date"})
    service._write_task(first["task_id"], updated_at="2099-01-01T00:00:00+00:00")

    tasks = service.list_tasks("valid-session")["tasks"]

    assert [task["task_id"] for task in tasks] == [second["task_id"], first["task_id"]]


def test_system_tasks_are_seeded_once_visible_and_read_only(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )

    # Seeding is idempotent: a restart, an upgrade and a second instance must not duplicate them.
    ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
    )._ensure_storage()
    service._ensure_storage()

    tasks = service.list_tasks("valid-session")
    system_tasks = tasks["system_tasks"]
    assert [task["task_id"] for task in system_tasks] == [definition["task_id"] for definition in SYSTEM_TASKS]
    assert all(task["enabled"] for task in system_tasks)
    assert all(task["target"] == "container" for task in system_tasks)
    # They are not part of an operator's own task list.
    assert tasks["tasks"] == []

    task_id = system_tasks[0]["task_id"]
    assert service.refresh_status("valid-session", task_id)["origin"] == "system"
    assert service.list_runs("valid-session", task_id)["runs"] == []

    # Read-only means every write is refused, not just hidden in the console.
    writes = (
        lambda: service.update_task("valid-session", task_id, {"name": "Mine", "schedule": "* * * * *", "command": "date"}),
        lambda: service.toggle_task("valid-session", task_id, False),
        lambda: service.run_task("valid-session", task_id),
        lambda: service.delete_task("valid-session", task_id),
    )
    for write in writes:
        with pytest.raises(CustomException) as error:
            write()
        assert error.value.status_code == 403

    # The refused writes must not have changed anything.
    assert [task["task_id"] for task in service.list_tasks("valid-session")["system_tasks"]] == [
        definition["task_id"] for definition in SYSTEM_TASKS
    ]


def test_system_task_runner_reports_a_skip_instead_of_a_failure():
    service = ScheduledTaskService(data_dir="/tmp/unused", cron_file="/tmp/unused-cron", auth_service=FakeAuthService())

    runner = service._runner_content("/tmp/state", "/tmp/lock", "/tmp/logs", "/tmp/runs", "system:appstore-sync", "true")

    # `websoft9 appstore sync --skip-if-running` exits with this code when another sync holds the
    # lock; the run has to be recorded as skipped and must not be retried.
    assert f'-eq {SKIPPED_EXIT_CODE} ]; then status=skipped' in runner
    assert f'-eq {SKIPPED_EXIT_CODE} ] || [ "$attempt" -gt 0 ]' in runner
    for definition in SYSTEM_TASKS:
        assert definition["command"].startswith("/usr/local/bin/websoft9")


def test_platform_maintenance_is_not_also_scheduled_by_the_image_crontab():
    crontab = (PROJECT_ROOT.parent / "docker" / "crontab").read_text(encoding="utf-8")

    # Both jobs now run from the platform task store; a leftover entry here would run them twice.
    assert "appstore sync" not in crontab
    assert "check-update" not in crontab
    assert not [line for line in crontab.splitlines() if line.strip() and not line.strip().startswith("#") and _looks_like_cron_entry(line)]


def _looks_like_cron_entry(line: str) -> bool:
    fields = line.split()
    return len(fields) >= 6 and len(fields[0].split("*/")) > 0 and fields[0][0] in "0123456789*" and "=" not in fields[0]


def test_appstore_sync_can_skip_when_another_sync_is_running(monkeypatch):
    from click.testing import CliRunner

    from src.cli import apphub_cli
    from src.services.appstore_sync_manager import AppStoreSyncManager

    monkeypatch.setattr(AppStoreSyncManager, "is_sync_running", lambda self: True)
    runner = CliRunner()

    skipped = runner.invoke(apphub_cli.cli, ["appstore", "sync", "--skip-if-running"])
    assert skipped.exit_code == SKIPPED_EXIT_CODE

    # Without the flag the CLI keeps its previous contract: fail loudly.
    failed = runner.invoke(apphub_cli.cli, ["appstore", "sync"])
    assert failed.exit_code != SKIPPED_EXIT_CODE
    assert failed.exit_code != 0


def test_host_capability_reuses_saved_host_access_profile(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=FakeHostAccessService(),
    )

    result = service.check_host_capability("valid-session", "profile-1")

    assert result["capability_status"] == "ready"
    assert result["timezone"] == "Asia/Shanghai"
    assert all(check["ok"] for check in result["checks"])


def test_host_task_saves_while_unreachable_and_refresh_resynchronizes(tmp_path):
    host_access_service = RecoveringHostTaskAccessService()
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=host_access_service,
    )

    task = service.create_task("valid-session", {"name": "Remote", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"})

    assert task["sync_status"] == "unreachable"
    host_access_service.available = True

    refreshed = service.refresh_status("valid-session", task["task_id"])

    assert refreshed["sync_status"] == "synced"


def test_background_sync_runs_different_host_profiles_concurrently(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    tasks = [
        {"task_id": "task-1", "target": "host", "profile_id": "profile-1", "sync_status": "synced"},
        {"task_id": "task-2", "target": "host", "profile_id": "profile-2", "sync_status": "synced"},
    ]
    both_started = threading.Event()
    release_syncs = threading.Event()
    started_profiles = set()
    started_lock = threading.Lock()

    monkeypatch.setattr(service, "_list_tasks", lambda _operator_id: tasks)

    def sync_host_group(_session_token, profile_id, _grouped_tasks):
        with started_lock:
            started_profiles.add(profile_id)
            if len(started_profiles) == 2:
                both_started.set()
        release_syncs.wait(timeout=1)

    monkeypatch.setattr(service, "_sync_host_task_runs_batch", sync_host_group)
    worker = threading.Thread(target=service._sync_operator_tasks_in_background, args=("valid-session", "operator-1"))
    worker.start()

    assert both_started.wait(timeout=0.5)
    release_syncs.set()
    worker.join(timeout=1)
    assert not worker.is_alive()
def test_host_capability_uses_utc_for_non_iana_timezone(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=FakeHostAccessService("EDT"),
    )

    result = service.check_host_capability("valid-session", "profile-1")

    assert result["timezone"] == "UTC"


def test_host_capability_closes_a_timed_out_remote_command(monkeypatch, tmp_path):
    class HangingChannel:
        def __init__(self):
            self.closed = False

        def exit_status_ready(self):
            return False

        def close(self):
            self.closed = True

    class HangingClient:
        def __init__(self):
            self.channel = HangingChannel()

        def exec_command(self, _command, timeout):
            class Output:
                def __init__(self, channel):
                    self.channel = channel

                @staticmethod
                def read():
                    return b""

            class Error:
                @staticmethod
                def read():
                    return b""

            return None, Output(self.channel), Error()

    class ClientContext:
        def __init__(self, client):
            self.client = client

        def __enter__(self):
            return self.client

        def __exit__(self, *_args):
            return False

    host_access = FakeHostAccessService()
    client = HangingClient()
    monkeypatch.setattr(host_access, "_open_file_client", lambda _profile: ClientContext(client))
    monotonic_values = iter([0.0, 0.0, 16.0])
    monkeypatch.setattr("src.services.scheduled_tasks.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("src.services.scheduled_tasks.time.sleep", lambda _seconds: None)
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None, host_access_service=host_access)

    try:
        service.check_host_capability("valid-session", "profile-1")
    except CustomException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Expected the hanging capability command to time out")

    assert client.channel.closed


def test_host_crontab_rejects_unmatched_or_nested_profile_markers():
    block = "# >>> websoft9-tasks:profile-1\n# <<< websoft9-tasks:profile-1"
    malformed_inputs = [
        "# <<< websoft9-tasks:profile-1",
        "# >>> websoft9-tasks:profile-1\n# >>> websoft9-tasks:profile-1\n# <<< websoft9-tasks:profile-1",
    ]

    for existing in malformed_inputs:
        try:
            ScheduledTaskService._replace_host_cron_block(existing, "profile-1", block)
        except CustomException as exc:
            assert exc.status_code == 503
        else:
            raise AssertionError("Expected malformed crontab markers to be rejected")


def test_host_runner_overlap_does_not_overwrite_active_state(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)

    runner = service._runner_content("/tmp/task.state", "/tmp/task.lock", "/tmp/task.logs", "/tmp/task.runs", "task-1", "sleep 1")

    assert service._runner_version_marker in runner
    assert "write_state skipped" not in runner
    assert "SKIPPED trigger=$trigger reason=previous_execution_running" in runner


def test_container_runner_overlap_does_not_overwrite_active_state(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "Overlap", "schedule": "* * * * *", "command": "sleep 1"})

    runner = (tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh").read_text(encoding="utf-8")

    assert "write_state skipped" not in runner
    assert "SKIPPED trigger=$trigger reason=previous_execution_running" in runner


def test_container_task_supports_script_path_timeout_and_retry(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)

    task = service.create_task(
        "valid-session",
        {"name": "Path", "schedule": "* * * * *", "execution_mode": "path", "script_path": "/opt/jobs/backup.sh", "timeout_seconds": 60, "retry_count": 2},
    )

    runner = (tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh").read_text(encoding="utf-8")
    assert task["execution_mode"] == "path"
    assert task["timeout_seconds"] == 60
    assert task["retry_count"] == 2
    assert "timeout 60 bash -c" in runner
    assert "RETRY trigger=$trigger attempt=$((attempt + 1))/3 exit_code=$exit_code" in runner
    assert "bash -- /opt/jobs/backup.sh" in runner


def test_container_runner_writes_execution_boundaries(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "Boundaries", "schedule": "* * * * *", "command": "printf 'task output\\n'"})

    result = subprocess.run([str(tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh"), "manual"], capture_output=True, text=True)
    log = next((tmp_path / "tasks" / "logs" / task["task_id"]).glob("*.log")).read_text(encoding="utf-8")

    assert result.returncode == 0
    assert "START trigger=manual" in log
    assert "task output" in log
    assert "END trigger=manual status=success exit_code=0 duration=" in log


def test_container_runner_logs_retry_and_failure(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "Retry", "schedule": "* * * * *", "command": "exit 7", "retry_count": 1})

    result = subprocess.run([str(tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh"), "manual"], capture_output=True, text=True)
    log = next((tmp_path / "tasks" / "logs" / task["task_id"]).glob("*.log")).read_text(encoding="utf-8")

    assert result.returncode == 7
    assert "RETRY trigger=manual attempt=2/2 exit_code=7" in log
    assert "END trigger=manual status=failed exit_code=7 duration=" in log


def test_container_run_history_indexes_individual_log(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "History", "schedule": "* * * * *", "command": "printf 'history output\\n'"})

    subprocess.run([str(tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh"), "manual"], check=True)
    service.refresh_status("valid-session", task["task_id"])
    runs = service.list_runs("valid-session", task["task_id"])["runs"]
    log = service.get_run_log("valid-session", task["task_id"], runs[0]["run_id"])

    assert len(runs) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["trigger"] == "manual"
    assert "history output" in log["content"]


def test_download_run_log_returns_an_attachment(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "Download", "schedule": "* * * * *", "command": "printf 'download output\\n'"})
    subprocess.run([str(tmp_path / "tasks" / "scripts" / f"{task['task_id']}.sh"), "manual"], check=True)
    service.refresh_status("valid-session", task["task_id"])
    run = service.list_runs("valid-session", task["task_id"])["runs"][0]

    content = service.download_run_log("valid-session", task["task_id"], run["run_id"])

    assert b"download output" in content


def test_list_runs_reads_sqlite_without_synchronizing_source_files(monkeypatch, tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)
    task = service.create_task("valid-session", {"name": "Cached history", "schedule": "* * * * *", "command": "date"})

    monkeypatch.setattr(service, "_sync_task_runs", lambda *_args: (_ for _ in ()).throw(AssertionError("list_runs must not synchronize source files")))

    result = service.list_runs("valid-session", task["task_id"])

    assert result == {"runs": [], "total": 0, "offset": 0, "limit": 20}


def test_container_task_stores_uploaded_script(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)

    task = service.create_task(
        "valid-session",
        {"name": "Upload", "schedule": "* * * * *", "execution_mode": "upload", "script_name": "backup.sh", "script_content": "#!/bin/bash\necho backup"},
    )

    uploaded_script = tmp_path / "tasks" / "uploads" / f"{task['task_id']}.sh"
    assert task["execution_mode"] == "upload"
    assert task["script_name"] == "backup.sh"
    assert uploaded_script.read_text(encoding="utf-8") == "#!/bin/bash\necho backup"


def test_new_uploaded_task_requires_script_content(tmp_path):
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None)

    try:
        service.create_task("valid-session", {"name": "Missing upload", "schedule": "* * * * *", "execution_mode": "upload"})
    except CustomException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected an uploaded task without content to be rejected")


def test_host_task_writes_profile_scoped_runner_and_crontab(tmp_path):
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=host_access,
    )

    task = service.create_task(
        "valid-session",
        {"name": "Remote", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"},
    )

    commands = "\n".join(host_access.client.commands)
    assert task["target"] == "host"
    assert task["profile_id"] == "profile-1"
    assert f"# >>> websoft9-tasks:profile-1" in commands
    assert f"{task['task_id']}.sh" in commands


def test_list_tasks_refreshes_ssh_task_execution_status(monkeypatch, tmp_path):
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=host_access,
    )
    task = service.create_task(
        "valid-session",
        {"name": "Remote status", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"},
    )
    monkeypatch.setattr(
        service,
        "_read_host_runs",
        lambda *_args: [{"run_id": "remote-run-1", "task_id": task["task_id"], "status": "success", "started_at": "2026-08-20T08:00:00+00:00", "finished_at": "2026-08-20T08:00:01+00:00", "exit_code": 0, "trigger": "cron", "log_path": "/remote/run.log"}],
    )

    listed_task = service.list_tasks("valid-session")["tasks"][0]

    assert listed_task["task_id"] == task["task_id"]
    assert listed_task["last_status"] == "success"
    assert listed_task["last_run_at"] == "2026-08-20T08:00:01+00:00"


def test_host_run_sync_accepts_an_empty_remote_runs_directory(tmp_path):
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"),
        cron_file=str(tmp_path / "websoft9-tasks"),
        auth_service=FakeAuthService(),
        cron_reloader=lambda: None,
        host_access_service=host_access,
    )
    task = service.create_task(
        "valid-session",
        {"name": "Empty remote history", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"},
    )

    service.list_tasks("valid-session")

    assert service._get_task("operator-1", task["task_id"])["sync_status"] == "synced"


def test_switching_away_from_host_removes_remote_task_files(tmp_path):
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None, host_access_service=host_access)
    task = service.create_task("valid-session", {"name": "Move", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"})

    service.update_task("valid-session", task["task_id"], {"name": "Move", "target": "container", "schedule": "* * * * *", "command": "date"})

    assert f"rm -rf /home/operator/.local/state/websoft9/scheduled-tasks/scripts/{task['task_id']}.sh" in "\n".join(host_access.client.commands)


def test_container_cron_excludes_ssh_tasks(tmp_path):
    host_access = FakeHostTaskAccessService()
    cron_file = tmp_path / "websoft9-tasks"
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(cron_file), auth_service=FakeAuthService(), cron_reloader=lambda: None, host_access_service=host_access)
    host_task = service.create_task("valid-session", {"name": "Host", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"})
    service.create_task("valid-session", {"name": "Container", "schedule": "* * * * *", "command": "date"})

    assert host_task["task_id"] not in cron_file.read_text(encoding="utf-8")


def test_switching_away_from_unreachable_host_is_rejected(monkeypatch, tmp_path):
    host_access = FakeHostTaskAccessService()
    service = ScheduledTaskService(data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None, host_access_service=host_access)
    task = service.create_task("valid-session", {"name": "Unavailable", "target": "host", "profile_id": "profile-1", "schedule": "* * * * *", "command": "date"})
    monkeypatch.setattr(service, "_sync_host_tasks", lambda *_args, **_kwargs: (_ for _ in ()).throw(CustomException(503, "Scheduled Task Host Unavailable", "Host is unavailable")))

    try:
        service.update_task("valid-session", task["task_id"], {"name": "Unavailable", "target": "container", "schedule": "* * * * *", "command": "date"})
    except CustomException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Expected an unreachable old host to block task migration")