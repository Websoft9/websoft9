import subprocess
import sys
import threading
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
from src.services.scheduled_tasks import ScheduledTaskService
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
        assert [item["name"] for item in listed.json()["tasks"]] == ["Date"]

        toggled = client.post(
            f"/scheduled-tasks/{task['task_id']}/toggle",
            headers={"Cookie": f"{PRODUCT_AUTH_COOKIE_NAME}=valid-session"},
            json={"enabled": False},
        )
        assert toggled.status_code == 200
        assert " root " not in (tmp_path / "websoft9-tasks").read_text(encoding="utf-8")

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
    assert " root " not in cron_file.read_text(encoding="utf-8")


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


def test_task_list_orders_by_creation_time_descending(tmp_path):
    service = ScheduledTaskService(
        data_dir=str(tmp_path / "tasks"), cron_file=str(tmp_path / "websoft9-tasks"), auth_service=FakeAuthService(), cron_reloader=lambda: None
    )
    first = service.create_task("valid-session", {"name": "First", "schedule": "* * * * *", "command": "date"})
    second = service.create_task("valid-session", {"name": "Second", "schedule": "* * * * *", "command": "date"})
    service._write_task(first["task_id"], updated_at="2099-01-01T00:00:00+00:00")

    tasks = service.list_tasks("valid-session")["tasks"]

    assert [task["task_id"] for task in tasks] == [second["task_id"], first["task_id"]]


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

    assert "# websoft9-task-runner-version: 4" in runner
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