from __future__ import annotations

import os
import base64
import fcntl
import json
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from src.core.exception import CustomException
from src.core.logger import logger
from src.services.host_access import HostAccessService
from src.services.product_auth import ProductAuthService

# A task command exits with this code to say "this run was skipped on purpose" (for example
# because another run of the same maintenance job was already in progress). The runner records
# it as skipped instead of failed and does not retry it.
SKIPPED_EXIT_CODE = 75

# Tasks the product owns. They are seeded as ordinary container tasks with a system origin, so
# they execute and record runs through the same runner as an operator's tasks, while the console
# shows them read-only.
SYSTEM_ORIGIN = "system"
SYSTEM_OPERATOR_ID = "system"
PLATFORM_CLI_PATH = "/usr/local/bin/websoft9"
SYSTEM_TASKS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "system:appstore-sync",
        "name": "App Store sync",
        # The sync takes a global lock; asking it to skip keeps a manual sync from turning this
        # scheduled run into a failure.
        "schedule": "0 3 * * *",
        "command": f"{PLATFORM_CLI_PATH} appstore sync --skip-if-running",
        "timeout_seconds": 3600,
    },
    {
        "task_id": "system:update-check",
        "name": "Platform update check",
        "schedule": "30 3 * * *",
        "command": f"{PLATFORM_CLI_PATH} check-update",
        "timeout_seconds": 900,
    },
)


def _container_local_zone() -> str:
    """The IANA zone this container resolves, the one cron schedules in.

    cron reads a cron.d entry in the container's local time, so this is what a schedule is
    really interpreted in. `/etc/timezone` and `/etc/localtime` are both supplied by the host
    that runs the container, which makes them the deployment's own answer to the question.
    """
    candidates: list[str] = []
    try:
        candidates.append(Path("/etc/timezone").read_text(encoding="utf-8").strip())
    except OSError:
        pass
    localtime = Path("/etc/localtime")
    try:
        target = os.readlink(localtime) if localtime.is_symlink() else ""
        if "zoneinfo/" in target:
            candidates.append(target.split("zoneinfo/", 1)[1])
    except OSError:
        pass
    for candidate in candidates:
        if not candidate:
            continue
        try:
            ZoneInfo(candidate)
            return candidate
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return "UTC"


class ScheduledTaskService:
    """Persist and run simple platform-container cron tasks."""

    _lock = threading.RLock()
    _host_capability_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
    _background_syncing: set[str] = set()
    _background_syncing_task_ids: dict[str, set[str]] = {}
    _runner_version_marker = "# websoft9-task-runner-version: 7"
    _run_retention_count = 20
    _run_retention_days = 3
    _log_read_line_limit = 200
    _log_read_byte_limit = 1024 * 1024

    def __init__(
        self,
        data_dir: Optional[str] = None,
        cron_file: Optional[str] = None,
        auth_service: Optional[ProductAuthService] = None,
        cron_reloader: Optional[Callable[[], None]] = None,
        host_access_service: Optional[HostAccessService] = None,
    ):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_SCHEDULED_TASKS_DATA_DIR") or f"{data_root}/config/scheduled-tasks")
        self.database_file = self.data_dir / "scheduled-tasks.sqlite"
        self.cron_file = Path(cron_file or os.getenv("WEBSOFT9_SCHEDULED_TASKS_CRON_FILE", "/etc/cron.d/websoft9-tasks"))
        self.auth_service = auth_service or ProductAuthService()
        self._cron_reloader = cron_reloader or self._reload_cron
        self.host_access_service = host_access_service or HostAccessService(auth_service=self.auth_service)

    def check_host_capability(self, session_token: Optional[str], profile_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized_profile_id = str(profile_id or "").strip()
        if not normalized_profile_id:
            raise CustomException(400, "Host Access Profile Required", "A saved SSH host profile is required")
        cache_key = (str(operator["id"]), normalized_profile_id)
        cached = self._host_capability_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1]

        profile = self.host_access_service.get_connection_profile(session_token, profile_id=normalized_profile_id)
        with self.host_access_service._open_file_client(profile) as client:
            try:
                _, stdout, stderr = client.exec_command(
                    "command -v bash >/dev/null && command -v crontab >/dev/null && command -v flock >/dev/null && command -v timeout >/dev/null "
                    "&& mkdir -p \"$HOME/.local/state/websoft9/scheduled-tasks\" "
                    "&& timezone_name=$(test -f /etc/timezone -a -r /etc/timezone && cat /etc/timezone || readlink -f /etc/localtime 2>/dev/null | sed 's#^.*/zoneinfo/##') "
                    "&& printf '%s' \"${timezone_name:-UTC}\"",
                    timeout=15,
                )
                deadline = time.monotonic() + 15
                while not getattr(stdout.channel, "exit_status_ready", lambda: True)():
                    if time.monotonic() >= deadline:
                        close_channel = getattr(stdout.channel, "close", None)
                        if callable(close_channel):
                            close_channel()
                        raise CustomException(503, "Scheduled Task Host Unavailable", "Timed out while inspecting the SSH host")
                    time.sleep(0.1)
                exit_code = stdout.channel.recv_exit_status()
                timezone_name = stdout.read().decode("utf-8", errors="replace").strip() or "UTC"
                error_text = stderr.read().decode("utf-8", errors="replace").strip()
            except Exception as exc:
                raise CustomException(503, "Scheduled Task Host Unavailable", f"Unable to inspect the SSH host: {exc}") from exc

        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            timezone_name = "UTC"

        checks = [
            {"name": "bash", "ok": exit_code == 0},
            {"name": "crontab", "ok": exit_code == 0},
            {"name": "flock", "ok": exit_code == 0},
            {"name": "timeout", "ok": exit_code == 0},
            {"name": "task_directory", "ok": exit_code == 0},
        ]
        result = {
            "capability_status": "ready" if exit_code == 0 else "unavailable",
            "timezone": timezone_name,
            "checks": checks,
            "message": error_text or ("Host is ready for scheduled tasks" if exit_code == 0 else "The SSH host is missing a required command or directory permission"),
        }
        self._host_capability_cache[cache_key] = (time.monotonic(), result)
        return result

    def list_tasks(self, session_token: Optional[str]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self._start_background_sync(session_token, str(operator["id"]))
        return self.list_cached_tasks(session_token)

    def list_cached_tasks(self, session_token: Optional[str]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self.reconcile_prewarm_state()
        operator_id = str(operator["id"])
        with self._lock:
            syncing_task_ids = self._background_syncing_task_ids.get(operator_id, set()).copy()
        tasks = []
        prewarm_tasks = []
        for task in self._list_tasks(operator_id):
            public_task = self._public_task(task)
            if task["category"] == "prewarm":
                prewarm_tasks.append(public_task)
                continue
            public_task["syncing"] = task["task_id"] in syncing_task_ids
            tasks.append(public_task)
        # Platform tasks travel separately: they belong to the product rather than to the operator,
        # and the console renders them read-only next to the operator's own tasks.
        return {
            "tasks": tasks,
            "system_tasks": [self._public_task(task) for task in self._list_system_tasks()] + [self._prewarm_summary(prewarm_tasks)],
        }

    def _prewarm_summary(self, records: list[dict]) -> dict[str, Any]:
        latest = max(records, key=lambda record: record["updated_at"], default={})
        running = sum(record["queue_state"] == "running" for record in records)
        queued = sum(record["queue_state"] == "queued" for record in records)
        return {
            "task_id": "system:image-prewarm", "name": "Image Prewarm", "target": "container",
            "profile_id": None, "schedule": "@once", "timezone": self._platform_timezone(),
            "command": "", "execution_mode": "command", "script_path": None, "script_name": None,
            "timeout_seconds": 7200, "retry_count": 0, "enabled": True,
            "last_run_at": latest.get("last_run_at"), "last_status": "running" if running else latest.get("queue_state", "never") if not queued else "never",
            "sync_status": "synced", "next_run_at": None, "created_at": latest.get("created_at", ""),
            "updated_at": latest.get("updated_at", ""), "execution_path": "", "origin": "system",
            "category": "prewarm", "subject_app": None, "subject_version": None, "queue_state": None,
            "running_count": running, "queued_count": queued,
        }

    def start_sync(self, session_token: Optional[str]) -> dict[str, str]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self._start_background_sync(session_token, str(operator["id"]))
        return {"status": "started"}

    def reconcile_local_schedule(self) -> None:
        with self._lock:
            self._refresh_container_task_timezones()
            self._sync()

    def _start_background_sync(self, session_token: Optional[str], operator_id: str) -> None:
        with self._lock:
            if operator_id in self._background_syncing:
                return
            self._background_syncing.add(operator_id)
        threading.Thread(target=self._sync_operator_tasks_in_background, args=(session_token, operator_id), daemon=True).start()

    def _sync_operator_tasks_in_background(self, session_token: Optional[str], operator_id: str) -> None:
        try:
            # This runs on a thread of its own, so it cannot assume the request that spawned it
            # already prepared the store.
            self._ensure_storage()
            # Platform tasks are owned by the product rather than the operator, so listing only
            # the operator's own rows would leave their run history unseen forever: the console
            # would keep showing "never" for a job that ran on schedule.
            tasks = [*self._list_system_tasks(), *self._list_tasks(operator_id)]
            for task in tasks:
                if task["target"] == "container":
                    self._upgrade_local_runner_if_needed(task)
                    self._sync_task_runs(session_token, task)
            host_tasks: dict[str, list[sqlite3.Row]] = {}
            for task in tasks:
                if task["target"] == "host" and task["profile_id"]:
                    host_tasks.setdefault(str(task["profile_id"]), []).append(task)
            host_threads = []
            for profile_id, grouped_tasks in host_tasks.items():
                host_thread = threading.Thread(
                    target=self._sync_host_task_group_in_background,
                    args=(session_token, operator_id, profile_id, grouped_tasks),
                    daemon=True,
                )
                host_thread.start()
                host_threads.append(host_thread)
            for host_thread in host_threads:
                host_thread.join()
        finally:
            with self._lock:
                self._background_syncing.discard(operator_id)
                self._background_syncing_task_ids.pop(operator_id, None)

    def _sync_host_task_group_in_background(
        self,
        session_token: Optional[str],
        operator_id: str,
        profile_id: str,
        grouped_tasks: list[sqlite3.Row],
    ) -> None:
        task_ids = {str(task["task_id"]) for task in grouped_tasks}
        with self._lock:
            self._background_syncing_task_ids.setdefault(operator_id, set()).update(task_ids)
        try:
            self._sync_host_task_runs_batch(session_token, profile_id, grouped_tasks)
        except CustomException:
            for task in grouped_tasks:
                self._write_task(task["task_id"], sync_status="unreachable", updated_at=self._now_iso())
        else:
            for task in grouped_tasks:
                if task["sync_status"] == "unreachable":
                    self._write_task(task["task_id"], sync_status="synced", updated_at=self._now_iso())
        finally:
            with self._lock:
                syncing_task_ids = self._background_syncing_task_ids.get(operator_id)
                if syncing_task_ids is not None:
                    syncing_task_ids.difference_update(task_ids)

    def create_task(self, session_token: Optional[str], payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized = self._normalize_payload(payload, require_upload_content=True)
        capability = self._host_capability_or_none(session_token, normalized)
        now = self._now_iso()
        task = {
            "task_id": str(uuid.uuid4()),
            "operator_id": operator["id"],
            "name": normalized["name"],
            "target": normalized["target"],
            "profile_id": normalized["profile_id"],
            "schedule": normalized["schedule"],
            "timezone": capability.get("timezone") if capability else self._platform_timezone(),
            "command": normalized["command"],
            "execution_mode": normalized["execution_mode"],
            "script_path": normalized["script_path"],
            "script_name": normalized["script_name"],
            "timeout_seconds": normalized["timeout_seconds"],
            "retry_count": normalized["retry_count"],
            "enabled": int(normalized["enabled"]),
            "last_run_at": None,
            "last_status": "never",
            "sync_status": "synced",
            "next_run_at": self._next_run(normalized["schedule"]),
            "created_at": now,
            "updated_at": now,
            "category": None,
            "subject_app": None,
            "subject_version": None,
            "queue_state": None,
            "claimed_at": None,
            "claimed_by": None,
            "runner_pgid": None,
        }
        with self._lock:
            self._ensure_storage()
            if self._task_name_exists(operator["id"], task["name"]):
                raise CustomException(409, "Scheduled Task Already Exists", "A task with this name already exists")
            self._insert_task(task)
            if normalized["execution_mode"] == "upload":
                try:
                    self._store_uploaded_script(session_token, self._get_task(operator["id"], task["task_id"]), normalized["script_content"])
                except CustomException:
                    self._write_task(task["task_id"], sync_status="unreachable", updated_at=self._now_iso())
                    raise
                except Exception:
                    self._write_task(task["task_id"], sync_status="failed", updated_at=self._now_iso())
                    raise
            self._sync_or_mark_failed(session_token, task["task_id"])
        return self._public_task(self._get_task(operator["id"], task["task_id"]))

    def enqueue_prewarm(self, session_token: Optional[str], app_name: str, version: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        app_name = str(app_name or "").strip()
        version = str(version or "").strip()
        if not app_name or not version:
            raise CustomException(400, "Invalid Prewarm Request", "An application name and version are required")

        now = self._now_iso()
        task_id: str | None = None
        created_or_requeued = False
        with self._lock:
            self._ensure_storage()
            with self._db_connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT * FROM scheduled_tasks WHERE operator_id = ? AND category = 'prewarm' AND subject_app = ? AND subject_version = ? AND queue_state IN ('queued', 'running') ORDER BY created_at DESC LIMIT 1",
                    (str(operator["id"]), app_name, version),
                ).fetchone()
                if existing:
                    task_id = str(existing["task_id"])
                else:
                    active_count = connection.execute(
                        "SELECT COUNT(*) FROM scheduled_tasks WHERE category = 'prewarm' AND queue_state IN ('queued', 'running')"
                    ).fetchone()[0]
                    if active_count >= 5:
                        raise CustomException(409, "Prewarm Queue Full", "The image prewarm queue is full")
                    task_id = str(uuid.uuid4())
                    task_name = f"Prewarm images {app_name} {version}"[:54] + f" {task_id[:8]}"
                    command = f"{PLATFORM_CLI_PATH} images prewarm --app {shlex.quote(app_name)} --version {shlex.quote(version)}"
                    connection.execute(
                        """
                        INSERT INTO scheduled_tasks (
                            task_id, operator_id, name, target, profile_id, schedule, timezone, command, execution_mode, script_path, script_name,
                            timeout_seconds, retry_count, enabled, last_run_at, last_status, sync_status, next_run_at, created_at, updated_at, origin,
                            category, subject_app, subject_version, queue_state, claimed_at, claimed_by, runner_pgid
                        ) VALUES (?, ?, ?, 'container', NULL, '@once', ?, ?, 'command', NULL, NULL, 7200, 0, 1, NULL, 'never', 'synced', NULL, ?, ?, 'user',
                                  'prewarm', ?, ?, 'queued', NULL, NULL, NULL)
                        """,
                        (task_id, str(operator["id"]), task_name, self._platform_timezone(), command, now, now, app_name, version),
                    )
                    created_or_requeued = True
                connection.commit()

            task = self._get_task(str(operator["id"]), task_id)
            if created_or_requeued:
                self._write_runner(task)
        return self._public_task(self._get_task(str(operator["id"]), task_id))

    def get_prewarm_task(self, session_token: Optional[str], app_name: str, version: str) -> Optional[dict[str, Any]]:
        """Return this operator's prewarm record for one app version, if it exists."""
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self.reconcile_prewarm_state()
        with self._db_connect() as connection:
            task = connection.execute(
                "SELECT * FROM scheduled_tasks WHERE operator_id = ? AND category = 'prewarm' AND subject_app = ? AND subject_version = ? ORDER BY CASE WHEN queue_state IN ('queued', 'running') THEN 0 ELSE 1 END, created_at DESC, rowid DESC LIMIT 1",
                (str(operator["id"]), str(app_name or "").strip(), str(version or "").strip()),
            ).fetchone()
        return self._public_task(task) if task else None

    def _reconcile_running_prewarm(self, connection) -> Optional[sqlite3.Row]:
        """Finalize the running prewarm task once its runner is done, returning it while it lives."""
        instance_id = self._prewarm_instance_id()
        running = connection.execute(
            "SELECT * FROM scheduled_tasks WHERE category = 'prewarm' AND queue_state = 'running' ORDER BY claimed_at ASC LIMIT 1"
        ).fetchone()
        if running and running["claimed_by"] and running["claimed_by"] != instance_id and not self._prewarm_runner_alive(running["runner_pgid"]):
            connection.execute(
                "UPDATE scheduled_tasks SET queue_state = 'queued', claimed_at = NULL, claimed_by = NULL, runner_pgid = NULL, updated_at = ? WHERE task_id = ? AND queue_state = 'running'",
                (self._now_iso(), running["task_id"]),
            )
            connection.commit()
            running = None
        if not running:
            return None
        state = self._read_state(str(running["task_id"]))
        state_status = state.get("status")
        if state_status in {"success", "failed", "skipped"}:
            queue_state = state_status if state_status != "skipped" else "queued"
            connection.execute(
                "UPDATE scheduled_tasks SET queue_state = ?, runner_pgid = NULL, updated_at = ? WHERE task_id = ? AND queue_state = 'running'",
                (queue_state, self._now_iso(), running["task_id"]),
            )
            connection.commit()
            return None
        if not self._prewarm_runner_alive(running["runner_pgid"]):
            queue_state = "failed" if state_status == "running" else "queued"
            connection.execute(
                "UPDATE scheduled_tasks SET queue_state = ?, claimed_at = NULL, claimed_by = NULL, runner_pgid = NULL, updated_at = ? WHERE task_id = ? AND queue_state = 'running'",
                (queue_state, self._now_iso(), running["task_id"]),
            )
            connection.commit()
            return None
        return running

    def reconcile_prewarm_state(self) -> None:
        """Bring prewarm states up to date without starting anything.

        The dispatcher only runs once a minute, so a task whose runner had already finished kept
        reporting \"running\" for up to a minute after its pull ended -- the console showed a pull in
        progress while the run history already said it succeeded. Read paths call this so the two
        never disagree for longer than a request.
        """
        self._ensure_storage()
        with self._db_connect() as connection:
            self._reconcile_running_prewarm(connection)

    def dispatch_prewarm(self) -> dict[str, Any]:
        """Reconcile one completed prewarm task, then start at most one queued task."""
        self._ensure_storage()
        self._states_dir().mkdir(parents=True, exist_ok=True)
        instance_id = self._prewarm_instance_id()
        lock_path = self._states_dir() / "prewarm-dispatch.lock"
        with lock_path.open("w", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"status": "skipped"}

            with self._db_connect() as connection:
                prewarm_tasks = connection.execute("SELECT * FROM scheduled_tasks WHERE category = 'prewarm'").fetchall()
            for task in prewarm_tasks:
                self._sync_task_runs(None, task)
            with self._db_connect() as connection:
                cancelled = connection.execute("SELECT task_id, runner_pgid FROM scheduled_tasks WHERE category = 'prewarm' AND queue_state = 'cancelled' AND runner_pgid IS NOT NULL").fetchall()
                for task in cancelled:
                    if self._prewarm_runner_alive(task["runner_pgid"]):
                        return {"status": "running", "task_id": task["task_id"]}
                    connection.execute("UPDATE scheduled_tasks SET runner_pgid = NULL WHERE task_id = ? AND queue_state = 'cancelled'", (task["task_id"],))
                connection.commit()
                running = self._reconcile_running_prewarm(connection)
                if running:
                    return {"status": "running", "task_id": running["task_id"]}

                queued = connection.execute(
                    "SELECT * FROM scheduled_tasks WHERE category = 'prewarm' AND queue_state = 'queued' ORDER BY created_at ASC, rowid ASC LIMIT 1"
                ).fetchone()
                if not queued:
                    return {"status": "idle"}
                claimed_at = self._now_iso()
                claimed = connection.execute(
                    "UPDATE scheduled_tasks SET queue_state = 'running', claimed_at = ?, claimed_by = ?, updated_at = ? WHERE task_id = ? AND queue_state = 'queued'",
                    (claimed_at, instance_id, claimed_at, queued["task_id"]),
                )
                if claimed.rowcount != 1:
                    connection.commit()
                    return {"status": "skipped"}
                connection.commit()

            runner = self._runner_path(str(queued["task_id"]))
            try:
                self._upgrade_local_runner_if_needed(queued)
                process = subprocess.Popen([str(runner), "manual"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as exc:
                self._write_task(str(queued["task_id"]), queue_state="failed", runner_pgid=None, updated_at=self._now_iso())
                raise CustomException(500, "Image Prewarm Dispatch Failed", f"Unable to start the prewarm runner: {exc}") from exc
            self._write_task(str(queued["task_id"]), runner_pgid=process.pid)
            return {"status": "started", "task_id": queued["task_id"]}

    def cancel_prewarm(self, session_token: Optional[str], task_id: str) -> None:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self._states_dir().mkdir(parents=True, exist_ok=True)
        with (self._states_dir() / "prewarm-dispatch.lock").open("w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            with self._lock:
                self._cancel_prewarm(str(operator["id"]), task_id)
        self._dispatch_prewarm_safely()

    def _dispatch_prewarm_safely(self) -> None:
        try:
            self.dispatch_prewarm()
        except Exception as exc:
            logger.warning(f"Unable to continue image prewarm queue: {exc}")

    def _cancel_prewarm(self, operator_id: str, task_id: str) -> None:
        with self._lock:
            task = self._get_task(operator_id, task_id)
            if str(task["category"] or "") != "prewarm":
                raise CustomException(404, "Prewarm Task Not Found", "The requested task is not an image prewarm task")
            if task["queue_state"] in {"success", "failed", "cancelled"}:
                return
            pgid = task["runner_pgid"]
            self._write_task(task_id, queue_state="cancelled", last_status="cancelled", updated_at=self._now_iso())
        if pgid:
            if self._terminate_prewarm_run(pgid):
                self._write_task(task_id, runner_pgid=None)
            else:
                logger.warning(f"Prewarm task {task_id} still has processes after cancel: {pgid}")
        # The killed runner never writes a result of its own, so its run is closed here. Without this
        # the history kept reporting "running" for a pull the operator had already cancelled.
        with self._db_connect() as connection:
            running_runs = connection.execute(
                "SELECT run_id, log_path FROM scheduled_task_runs WHERE task_id = ? AND status = 'running'",
                (task_id,),
            ).fetchall()
            connection.execute(
                "UPDATE scheduled_task_runs SET status = 'cancelled', finished_at = ? WHERE task_id = ? AND status = 'running'",
                (self._now_iso(), task_id),
            )
            connection.commit()
        log_paths = [run["log_path"] for run in running_runs]
        if not log_paths:
            # The run index is built lazily from the run files, so a pull cancelled before anyone
            # opened its history has no row yet. The state file knows which run is live.
            run_id = str(self._read_state(task_id).get("run_id") or "")
            if run_id:
                log_paths.append(str(self._task_logs_dir(task_id) / f"{run_id}.log"))
        for log_path in log_paths:
            self._append_cancel_marker(log_path)
        self._sync_task_runs(None, self._get_task(operator_id, task_id))

    def _append_cancel_marker(self, log_path: object) -> None:
        """Close a cancelled run's log with a line that explains the early ending."""
        if not log_path:
            return
        try:
            path = Path(str(log_path))
            if not path.exists():
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{self._now_iso()}] CANCELLED by operator\n")
        except OSError as exc:
            logger.warning(f"Unable to annotate cancelled prewarm log {log_path}: {exc}")

    @staticmethod
    def _prewarm_session_pids(session_id: object) -> list[int]:
        """Return every process of one prewarm run.

        Signalling the runner's process group is not enough: the runner wraps the pull in
        `timeout`, and `timeout` puts the command in a **new** process group (measured: runner
        pgid 40666 while `timeout` and the CLI sat in pgid 40675 of the same session). Killing the
        group therefore left the real download alive, still appending progress lines to the run
        log, so cancelling looked like it did nothing. The runner is started with
        `start_new_session=True`, so its pid is also the session id of the whole run.
        """
        try:
            wanted = int(session_id)
        except (TypeError, ValueError):
            return []
        pids: list[int] = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text(encoding="utf-8")
            except OSError:
                continue
            # `comm` may contain spaces and brackets, so fields are read after the last ')'.
            fields = raw[raw.rfind(")") + 2 :].split()
            # fields = state, ppid, pgrp, session, ...; a zombie has already exited and only waits
            # to be reaped, so it must not count as a running prewarm.
            if len(fields) >= 4 and fields[3] == str(wanted) and fields[0] != "Z":
                pids.append(int(entry.name))
        return pids

    def _terminate_prewarm_run(self, pgid: object) -> bool:
        """Stop a whole prewarm run, escalating from SIGTERM to SIGKILL. True when nothing is left."""
        try:
            leader = int(pgid)
        except (TypeError, ValueError):
            return True
        mine = os.getpid()
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(leader, sig)
            except ProcessLookupError:
                pass
            except OSError as exc:
                logger.warning(f"Unable to signal prewarm process group {leader}: {exc}")
            for pid in self._prewarm_session_pids(leader):
                if pid == mine:
                    continue
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    logger.warning(f"Unable to signal prewarm process {pid}: {exc}")
            for _ in range(20):
                if not self._prewarm_session_pids(leader):
                    return True
                time.sleep(0.1)
        return not self._prewarm_session_pids(leader)

    def retry_prewarm(self, session_token: Optional[str], task_id: str) -> dict[str, Any]:
        """Re-queue a failed or cancelled prewarm so its pull can be attempted again.

        Retrying reuses the same task record rather than creating a new one, so the run history keeps
        both attempts together. Layers already downloaded stay in the local store, which makes a retry
        a continuation rather than a fresh download.
        """
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(str(operator["id"]), task_id)
            if str(task["category"] or "") != "prewarm":
                raise CustomException(404, "Prewarm Task Not Found", "The requested task is not an image prewarm task")
            if task["queue_state"] not in {"success", "failed", "cancelled"}:
                raise CustomException(409, "Prewarm Not Retryable", "Only a completed image prewarm can be retried")
            if self._prewarm_runner_alive(task["runner_pgid"]):
                raise CustomException(409, "Prewarm Task Running", "The previous image prewarm process has not stopped")
            self._sync_task_runs(session_token, task)
            with self._db_connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                active = connection.execute(
                    "SELECT task_id FROM scheduled_tasks WHERE operator_id = ? AND category = 'prewarm' AND subject_app = ? AND subject_version = ? AND queue_state IN ('queued', 'running')",
                    (str(operator["id"]), task["subject_app"], task["subject_version"]),
                ).fetchone()
                if active:
                    raise CustomException(409, "Prewarm Already Active", "This application version already has an active image prewarm")
                active_count = connection.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE category = 'prewarm' AND queue_state IN ('queued', 'running')").fetchone()[0]
                if active_count >= 5:
                    raise CustomException(409, "Prewarm Queue Full", "The image prewarm queue is full")
                now = self._now_iso()
                connection.execute(
                    "UPDATE scheduled_tasks SET rowid = (SELECT MAX(rowid) + 1 FROM scheduled_tasks), queue_state = 'queued', claimed_at = NULL, claimed_by = NULL, runner_pgid = NULL, created_at = ?, updated_at = ? WHERE task_id = ?",
                    (now, now, task_id),
                )
                self._state_path(task_id).unlink(missing_ok=True)
                connection.commit()
            self._write_runner(self._get_task(str(operator["id"]), task_id))
        self.dispatch_prewarm()
        return self._public_task(self._get_task(str(operator["id"]), task_id))

    def list_prewarm_records(self, session_token: Optional[str], offset: int = 0, limit: int = 20, search: str = "", status: str = "all") -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self.reconcile_prewarm_state()
        tasks = [task for task in self._list_tasks(str(operator["id"])) if task["category"] == "prewarm"]
        for task in tasks:
            self._sync_task_runs(session_token, task)
        query = """
            FROM scheduled_tasks task LEFT JOIN (
                SELECT task_id, run_id, started_at, finished_at, status, exit_code, trigger, log_path FROM (
                    SELECT runs.*, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY started_at DESC, rowid DESC) AS position
                    FROM scheduled_task_runs runs
                ) latest WHERE position = 1 AND NOT EXISTS (
                    SELECT 1 FROM scheduled_tasks pending WHERE pending.task_id = latest.task_id
                    AND pending.queue_state IN ('queued', 'running') AND latest.status != 'running'
                )
                UNION ALL
                SELECT task_id, '__pending__', created_at, NULL, queue_state, NULL, 'manual', '' FROM scheduled_tasks pending
                WHERE pending.queue_state IN ('queued', 'running')
                AND EXISTS (SELECT 1 FROM scheduled_task_runs WHERE task_id = pending.task_id)
                AND NOT EXISTS (SELECT 1 FROM scheduled_task_runs WHERE task_id = pending.task_id AND status = 'running')
            ) run ON task.task_id = run.task_id
            WHERE task.operator_id = ? AND task.category = 'prewarm'
            AND (? = '' OR instr(lower(COALESCE(task.subject_app, '') || ' ' || COALESCE(task.subject_version, '')), ?) > 0)
            AND (? = 'all' OR task.queue_state = ?)
        """
        parameters = (str(operator["id"]), search.strip().lower(), search.strip().lower(), status, status)
        with self._db_connect() as connection:
            total = connection.execute("SELECT COUNT(*) " + query, parameters).fetchone()[0]
            rows = connection.execute("""
                SELECT task.task_id, COALESCE(run.run_id, '__pending__') AS run_id,
                    COALESCE(run.started_at, task.created_at) AS started_at, run.finished_at,
                    task.queue_state AS status, run.exit_code,
                    COALESCE(run.trigger, 'manual') AS trigger, COALESCE(run.log_path, '') AS log_path
                """ + query + """ ORDER BY
                    CASE task.queue_state WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                    CASE WHEN task.queue_state IN ('running', 'queued') THEN task.created_at END ASC,
                    CASE WHEN task.queue_state IN ('running', 'queued') THEN task.rowid END ASC,
                    started_at DESC, task.rowid DESC, run.run_id DESC LIMIT ? OFFSET ?""",
                (*parameters, limit, offset),
            ).fetchall()
        tasks_by_id = {task["task_id"]: task for task in tasks}
        active_subjects = {(task["subject_app"], task["subject_version"]) for task in tasks if task["queue_state"] in {"queued", "running"}}
        records = []
        for row in rows:
            record = dict(row)
            task = self._public_task(tasks_by_id[row["task_id"]])
            record["task"] = task
            record["name"] = f"{task['subject_app']} {task['subject_version']}"
            record["retry_blocked"] = (task["subject_app"], task["subject_version"]) in active_subjects
            records.append(record)
        return {"runs": records, "total": total, "offset": offset, "limit": limit}

    def delete_prewarm_record(self, session_token: Optional[str], task_id: str, run_id: str) -> None:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(str(operator["id"]), task_id)
            if task["category"] != "prewarm":
                raise CustomException(404, "Prewarm Task Not Found", "The requested task is not an image prewarm task")
            if task["queue_state"] in {"queued", "running"} or self._prewarm_runner_alive(task["runner_pgid"]):
                raise CustomException(409, "Prewarm Task Running", "Cancel the image prewarm before deleting it")
            self._sync_task_runs(session_token, task)
            with self._db_connect() as connection:
                runs = connection.execute("SELECT run_id FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC, rowid DESC", (task_id,)).fetchall()
            if run_id == "__pending__" and not runs:
                self.delete_task(session_token, task_id)
                return
            if not any(run["run_id"] == run_id for run in runs):
                raise CustomException(404, "Scheduled Task Run Not Found", "The requested task execution does not exist")
            if runs[0]["run_id"] == run_id:
                self.delete_task(session_token, task_id)
                return
            if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
                raise CustomException(400, "Invalid Run ID", "Invalid execution record identifier")
            (self._runs_dir(task_id) / f"{run_id}.json").unlink(missing_ok=True)
            (self._task_logs_dir(task_id) / f"{run_id}.log").unlink(missing_ok=True)
            with self._db_connect() as connection:
                connection.execute("DELETE FROM scheduled_task_runs WHERE task_id = ? AND run_id = ?", (task_id, run_id))
                connection.commit()

    def update_task(self, session_token: Optional[str], task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized = self._normalize_payload(payload)
        capability = self._host_capability_or_none(session_token, normalized)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            self._require_mutable(task)
            if task["name"] != normalized["name"] and self._task_name_exists(operator["id"], normalized["name"]):
                raise CustomException(409, "Scheduled Task Already Exists", "A task with this name already exists")
            target_changed = task["target"] != normalized["target"] or task["profile_id"] != normalized["profile_id"]
            if normalized["execution_mode"] == "upload" and not normalized["script_content"] and task["execution_mode"] != "upload":
                raise CustomException(400, "Scheduled Task Script Required", "Upload a script before selecting uploaded script execution")
            if normalized["execution_mode"] == "upload" and target_changed and not normalized["script_content"]:
                raise CustomException(400, "Scheduled Task Script Required", "Upload the script again after changing the execution target")
            script_name = normalized["script_name"] or (task["script_name"] if normalized["execution_mode"] == "upload" else None)
            old_host_available = True
            if task["target"] == "host":
                try:
                    self._sync_host_tasks(session_token, task["profile_id"], exclude_task_id=task_id)
                except CustomException:
                    old_host_available = False
                if target_changed and old_host_available:
                    self._remove_host_task_files(session_token, task)
            elif task["target"] == "container":
                self._sync_without_task(task_id)
            if target_changed and task["target"] == "container":
                for path in (self._runner_path(task_id), self._log_path(task_id), self._state_path(task_id), self._lock_path(task_id), self._uploaded_script_path(task)):
                    path.unlink(missing_ok=True)
            self._write_task(
                task_id,
                name=normalized["name"],
                target=normalized["target"],
                profile_id=normalized["profile_id"],
                schedule=normalized["schedule"],
                timezone=capability.get("timezone") if capability else self._platform_timezone(),
                command=normalized["command"],
                execution_mode=normalized["execution_mode"],
                script_path=normalized["script_path"],
                script_name=script_name,
                timeout_seconds=normalized["timeout_seconds"],
                retry_count=normalized["retry_count"],
                enabled=int(normalized["enabled"]),
                next_run_at=self._next_run(normalized["schedule"]),
                updated_at=self._now_iso(),
            )
            updated_task = self._get_task(operator["id"], task_id)
            if normalized["execution_mode"] == "upload" and normalized["script_content"]:
                self._store_uploaded_script(session_token, updated_task, normalized["script_content"])
            elif task["execution_mode"] == "upload" and normalized["execution_mode"] != "upload":
                self._remove_uploaded_script(session_token, task)
            self._sync_or_mark_failed(session_token, task_id)
        return self._public_task(self._get_task(operator["id"], task_id))

    def toggle_task(self, session_token: Optional[str], task_id: str, enabled: bool) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            self._require_mutable(task)
            self._write_task(task_id, enabled=int(enabled), updated_at=self._now_iso())
            self._sync_or_mark_failed(session_token, task_id)
        return self._public_task(self._get_task(operator["id"], task_id))

    def delete_task(self, session_token: Optional[str], task_id: str) -> None:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            if str(task["category"] or "") == "prewarm":
                if task["queue_state"] in {"queued", "running"} or self._prewarm_runner_alive(task["runner_pgid"]):
                    raise CustomException(409, "Prewarm Task Running", "Cancel the image prewarm before deleting it")
            else:
                self._require_mutable(task)
            if task["target"] == "host":
                try:
                    self._sync_host_tasks(session_token, task["profile_id"], exclude_task_id=task_id)
                    self._remove_host_task_files(session_token, task)
                except CustomException:
                    pass
            else:
                self._sync_without_task(task_id)
            self._delete_task(task_id)
            # The run index is keyed by task_id alone, so it outlives the task row: without this
            # the history of a deleted task stays in the database for good.
            with self._db_connect() as connection:
                connection.execute("DELETE FROM scheduled_task_runs WHERE task_id = ?", (task_id,))
                connection.commit()
            for path in (self._runner_path(task_id), self._log_path(task_id), self._state_path(task_id), self._lock_path(task_id), self._uploaded_script_path(task)):
                path.unlink(missing_ok=True)
            self._task_logs_dir(task_id).unlink(missing_ok=True) if self._task_logs_dir(task_id).is_file() else None
            if self._task_logs_dir(task_id).is_dir():
                subprocess.run(["rm", "-rf", str(self._task_logs_dir(task_id)), str(self._runs_dir(task_id))], check=False)

    def run_task(self, session_token: Optional[str], task_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            self._require_mutable(task)
            if task["sync_status"] != "synced":
                self._sync_or_mark_failed(session_token, task_id)
                task = self._get_task(operator["id"], task_id)
                if task["sync_status"] != "synced":
                    raise CustomException(503, "Scheduled Task Sync Failed", "The task could not be synchronized before running")
            if task["target"] == "host":
                self._run_host_task(session_token, task)
            else:
                runner = self._runner_path(task_id)
                if not runner.is_file():
                    raise CustomException(503, "Scheduled Task Runner Missing", "The task runner is unavailable")
                subprocess.Popen([str(runner), "manual"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self._write_task(task_id, last_status="running", last_run_at=self._now_iso(), updated_at=self._now_iso())
        return {"task_id": task_id, "status": "started"}

    def refresh_status(self, session_token: Optional[str], task_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            if task["target"] == "host":
                self._sync_or_mark_failed(session_token, task_id)
                task = self._get_task(operator["id"], task_id)
            if task["sync_status"] == "synced":
                self._sync_task_runs(session_token, task)
        return self._public_task(self._get_task(operator["id"], task_id))

    def list_runs(self, session_token: Optional[str], task_id: str, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        task = self._get_task(operator["id"], task_id)
        # Read the runner's own records first: without this a run that just finished would still be
        # reported as `running` until the next background sync, which made the run history lag behind
        # the log the operator is reading. Remote tasks are skipped -- they cost an SSH round trip and
        # their sync is handled in the background.
        if task["target"] == "container":
            try:
                self._sync_task_runs(session_token, task)
            except Exception:
                pass
        bounded_offset = max(0, offset)
        bounded_limit = max(1, min(100, limit))
        with self._db_connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM scheduled_task_runs WHERE task_id = ?", (task_id,)).fetchone()[0]
            rows = connection.execute(
                "SELECT run_id, task_id, started_at, finished_at, status, exit_code, trigger, log_path FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (task_id, bounded_limit, bounded_offset),
            ).fetchall()
        return {"runs": [dict(row) for row in rows], "total": total, "offset": bounded_offset, "limit": bounded_limit}

    def get_run_log(self, session_token: Optional[str], task_id: str, run_id: str, before: Optional[int] = None) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        task = self._get_task(operator["id"], task_id)
        with self._db_connect() as connection:
            run = connection.execute("SELECT log_path FROM scheduled_task_runs WHERE task_id = ? AND run_id = ?", (task_id, run_id)).fetchone()
        if run is None:
            raise CustomException(404, "Scheduled Task Run Not Found", "The requested task execution does not exist")
        content = self._read_host_run_log(session_token, task, run["log_path"], before) if task["target"] == "host" else self._read_log_window(Path(run["log_path"]), before)
        return content

    def download_run_log(self, session_token: Optional[str], task_id: str, run_id: str) -> bytes:
        operator = self.auth_service._require_authenticated_operator(session_token)
        task = self._get_task(operator["id"], task_id)
        with self._db_connect() as connection:
            run = connection.execute("SELECT log_path FROM scheduled_task_runs WHERE task_id = ? AND run_id = ?", (task_id, run_id)).fetchone()
        if run is None:
            raise CustomException(404, "Scheduled Task Run Not Found", "The requested task execution does not exist")
        if task["target"] == "host":
            profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
            with self.host_access_service._open_file_client(profile) as client:
                content = self._remote_output(client, f"cat -- {shlex.quote(run['log_path'])} 2>/dev/null || true")
            return content.encode("utf-8")
        try:
            return Path(run["log_path"]).read_bytes()
        except OSError:
            return b""

    def _normalize_payload(self, payload: dict[str, Any], require_upload_content: bool = False, allow_once: bool = False) -> dict[str, Any]:
        target = str(payload.get("target") or "container")
        profile_id = str(payload.get("profile_id") or "").strip() or None
        if target not in {"container", "host"}:
            raise CustomException(400, "Invalid Scheduled Task Target", "Task target must be platform container or SSH host")
        if target == "container" and profile_id:
            raise CustomException(400, "Invalid Scheduled Task Target", "Platform tasks cannot use an SSH host profile")
        if target == "host" and not profile_id:
            raise CustomException(400, "Host Access Profile Required", "SSH host tasks require a saved host profile")
        name = str(payload.get("name") or "").strip()
        execution_mode = str(payload.get("execution_mode") or "command")
        command = str(payload.get("command") or "").strip()
        script_path = str(payload.get("script_path") or "").strip() or None
        script_name = Path(str(payload.get("script_name") or "").strip()).name or None
        script_content = payload.get("script_content")
        timeout_value = payload.get("timeout_seconds")
        retry_value = payload.get("retry_count")
        timeout_seconds = 30 if timeout_value is None else int(timeout_value)
        retry_count = 3 if retry_value is None else int(retry_value)
        schedule = str(payload.get("schedule") or "").strip()
        if not name:
            raise CustomException(400, "Invalid Scheduled Task", "A task name is required")
        if execution_mode not in {"command", "path", "upload"}:
            raise CustomException(400, "Invalid Scheduled Task", "Execution mode is invalid")
        if execution_mode == "command" and (not command or "\x00" in command):
            raise CustomException(400, "Invalid Scheduled Task", "A command is required")
        if execution_mode == "path" and (not script_path or not script_path.startswith("/") or "\n" in script_path or "\x00" in script_path):
            raise CustomException(400, "Invalid Scheduled Task", "Script path must be an absolute path")
        if execution_mode == "upload" and ((require_upload_content and not script_content) or (script_content is not None and (not isinstance(script_content, str) or not script_content.strip()))):
            raise CustomException(400, "Invalid Scheduled Task", "Uploaded script content is invalid")
        if len(name) > 64 or len(command) > 4096 or (script_content is not None and len(script_content) > 524288):
            raise CustomException(400, "Invalid Scheduled Task", "Task input exceeds its maximum length")
        if timeout_seconds < 0 or timeout_seconds > 86400:
            raise CustomException(400, "Invalid Scheduled Task", "Timeout must be between 0 and 86400 seconds")
        if retry_count < 0 or retry_count > 10:
            raise CustomException(400, "Invalid Scheduled Task", "Retry count must be between 0 and 10")
        if schedule == "@once":
            if not allow_once or target != "container":
                raise CustomException(400, "Invalid Schedule", "One-time schedules are reserved for internal container tasks")
        elif len(schedule.split()) != 5 or "\n" in schedule:
            raise CustomException(400, "Invalid Schedule", "Schedule must be a five-field cron expression")
        else:
            try:
                croniter(schedule, datetime.now())
            except (TypeError, ValueError) as exc:
                raise CustomException(400, "Invalid Schedule", "Schedule must be a valid five-field cron expression") from exc
        return {"name": name, "target": target, "profile_id": profile_id, "command": command if execution_mode == "command" else "", "execution_mode": execution_mode, "script_path": script_path if execution_mode == "path" else None, "script_name": script_name if execution_mode == "upload" else None, "script_content": script_content if execution_mode == "upload" else None, "timeout_seconds": timeout_seconds, "retry_count": retry_count, "schedule": schedule, "enabled": bool(payload.get("enabled", True))}

    def _host_capability_or_none(self, session_token: Optional[str], payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        if payload["target"] != "host":
            return None
        try:
            capability = self.check_host_capability(session_token, str(payload["profile_id"]))
        except CustomException:
            return None
        return capability if capability["capability_status"] == "ready" else None

    def _sync_or_mark_failed(self, session_token: Optional[str], task_id: str) -> None:
        task = self._get_task_by_id(task_id)
        if task["target"] == "host":
            try:
                capability = self.check_host_capability(session_token, str(task["profile_id"]))
            except CustomException:
                self._write_task(task_id, sync_status="unreachable", updated_at=self._now_iso())
                return
            if capability["capability_status"] != "ready":
                self._write_task(task_id, sync_status="failed", updated_at=self._now_iso())
                return
            self._write_task(task_id, timezone=capability["timezone"], updated_at=self._now_iso())
        try:
            task = self._get_task_by_id(task_id)
            if task["target"] == "host":
                self._sync_host_tasks(session_token, task["profile_id"])
            else:
                self._sync()
        except CustomException:
            self._write_task(task_id, sync_status="unreachable", updated_at=self._now_iso())
        except Exception:
            self._write_task(task_id, sync_status="failed", updated_at=self._now_iso())
        else:
            self._write_task(task_id, sync_status="synced", updated_at=self._now_iso())

    def _sync(self) -> None:
        self._ensure_storage()
        self._sync_tasks([task for task in self._list_enabled_tasks() if task["target"] == "container" and task["schedule"] != "@once"])

    def _refresh_container_task_timezones(self) -> None:
        self._ensure_storage()
        with self._db_connect() as connection:
            connection.execute(
                "UPDATE scheduled_tasks SET timezone = ? WHERE target = 'container' AND timezone != ?",
                (self._platform_timezone(), self._platform_timezone()),
            )
            connection.commit()

    def _sync_without_task(self, task_id: str) -> None:
        tasks = [task for task in self._list_enabled_tasks() if task["target"] == "container" and task["task_id"] != task_id]
        self._sync_tasks(tasks)

    def _sync_host_tasks(self, session_token: Optional[str], profile_id: Optional[str], exclude_task_id: Optional[str] = None) -> None:
        if not profile_id:
            raise CustomException(503, "Scheduled Task Host Unavailable", "The SSH host profile is unavailable")
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=profile_id)
        tasks = self._list_enabled_host_tasks(profile_id, exclude_task_id)
        with self.host_access_service._open_file_client(profile) as client:
            home = self._remote_home(client)
            for task in tasks:
                self._write_host_runner(client, task, home)
            existing_crontab = self._remote_output(client, "crontab -l 2>/dev/null || true")
            block = self._host_cron_block(profile_id, tasks, home)
            updated_crontab = self._replace_host_cron_block(existing_crontab, profile_id, block)
            self._write_host_crontab(client, home, profile_id, updated_crontab)

    def _list_enabled_host_tasks(self, profile_id: str, exclude_task_id: Optional[str]) -> list[sqlite3.Row]:
        with self._db_connect() as connection:
            rows = connection.execute(
                "SELECT * FROM scheduled_tasks WHERE target = 'host' AND profile_id = ? AND enabled = 1 ORDER BY created_at ASC", (profile_id,)
            ).fetchall()
        return [task for task in rows if task["task_id"] != exclude_task_id and task["schedule"] != "@once"]

    def _remote_home(self, client: Any) -> str:
        home = self._remote_output(client, "printf '%s' \"$HOME\"").strip()
        if not home.startswith("/"):
            raise CustomException(503, "Scheduled Task Host Unavailable", "The SSH host did not provide a usable home directory")
        return home

    def _write_host_runner(self, client: Any, task: sqlite3.Row, home: str) -> None:
        paths = self._host_paths(home, task["task_id"])
        command = (
            f"mkdir -p {shlex.quote(paths['scripts_dir'])} {shlex.quote(paths['logs_task_dir'])} {shlex.quote(paths['runs_dir'])} {shlex.quote(paths['states_dir'])} {shlex.quote(paths['uploads_dir'])}\n"
            f"cat > {shlex.quote(paths['runner'])} <<'WEBSOFT9_TASK_RUNNER'\n"
            f"{self._runner_content(paths['state'], paths['lock'], paths['logs_task_dir'], paths['runs_dir'], task['task_id'], self._task_command(task, paths['upload']), task['timeout_seconds'], task['retry_count'])}"
            "WEBSOFT9_TASK_RUNNER\n"
            f"chmod 700 {shlex.quote(paths['runner'])}"
        )
        self._run_remote(client, command, "Scheduled Task Sync Failed", "Unable to write the remote task runner")

    def _host_cron_block(self, profile_id: str, tasks: list[sqlite3.Row], home: str) -> str:
        start = f"# >>> websoft9-tasks:{profile_id}"
        end = f"# <<< websoft9-tasks:{profile_id}"
        lines = [start]
        for task in tasks:
            lines.append(f"{task['schedule']} {self._host_paths(home, task['task_id'])['runner']}")
        lines.append(end)
        return "\n".join(lines)

    @staticmethod
    def _replace_host_cron_block(existing: str, profile_id: str, block: str) -> str:
        start = f"# >>> websoft9-tasks:{profile_id}"
        end = f"# <<< websoft9-tasks:{profile_id}"
        lines = existing.splitlines()
        kept: list[str] = []
        inside_block = False
        for line in lines:
            if line == start:
                if inside_block:
                    raise CustomException(503, "Scheduled Task Sync Failed", "The remote crontab contains nested Websoft9 task blocks")
                inside_block = True
                continue
            if line == end:
                if not inside_block:
                    raise CustomException(503, "Scheduled Task Sync Failed", "The remote crontab contains an unmatched Websoft9 task block marker")
                inside_block = False
                continue
            if not inside_block:
                kept.append(line)
        if inside_block:
            raise CustomException(503, "Scheduled Task Sync Failed", "The remote crontab contains an incomplete Websoft9 task block")
        while kept and not kept[-1].strip():
            kept.pop()
        return "\n".join([*kept, block, ""])

    def _write_host_crontab(self, client: Any, home: str, profile_id: str, content: str) -> None:
        temporary = f"{home}/.local/state/websoft9/scheduled-tasks/.crontab-{profile_id}"
        command = (
            f"cat > {shlex.quote(temporary)} <<'WEBSOFT9_CRONTAB'\n{content}WEBSOFT9_CRONTAB\n"
            f"crontab {shlex.quote(temporary)} && rm -f {shlex.quote(temporary)}"
        )
        self._run_remote(client, command, "Scheduled Task Sync Failed", "Unable to update the remote crontab")

    def _run_host_task(self, session_token: Optional[str], task: sqlite3.Row) -> None:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            runner = self._host_paths(self._remote_home(client), task["task_id"])["runner"]
            self._run_remote(client, f"nohup {shlex.quote(runner)} manual >/dev/null 2>&1 &", "Scheduled Task Run Failed", "Unable to start the remote task")

    def _remove_host_task_files(self, session_token: Optional[str], task: sqlite3.Row) -> None:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            paths = self._host_paths(self._remote_home(client), task["task_id"])
            self._run_remote(client, f"rm -rf {shlex.quote(paths['runner'])} {shlex.quote(paths['logs_task_dir'])} {shlex.quote(paths['runs_dir'])} {shlex.quote(paths['state'])} {shlex.quote(paths['lock'])} {shlex.quote(paths['upload'])}", "Scheduled Task Delete Failed", "Unable to remove remote task files")

    def _store_uploaded_script(self, session_token: Optional[str], task: sqlite3.Row, content: Optional[str]) -> None:
        if content is None:
            return
        if task["target"] == "container":
            script_path = self._uploaded_script_path(task)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(content, encoding="utf-8")
            script_path.chmod(0o700)
            return
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            paths = self._host_paths(self._remote_home(client), task["task_id"])
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            self._run_remote(client, f"mkdir -p {shlex.quote(paths['uploads_dir'])} && printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(paths['upload'])} && chmod 700 {shlex.quote(paths['upload'])}", "Scheduled Task Upload Failed", "Unable to write the remote task script")

    def _remove_uploaded_script(self, session_token: Optional[str], task: sqlite3.Row) -> None:
        if task["target"] == "container":
            self._uploaded_script_path(task).unlink(missing_ok=True)
            return
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            upload_path = self._host_paths(self._remote_home(client), task["task_id"])["upload"]
            self._run_remote(client, f"rm -f {shlex.quote(upload_path)}", "Scheduled Task Delete Failed", "Unable to remove remote task script")

    def _read_host_state(self, session_token: Optional[str], task: sqlite3.Row) -> dict[str, str]:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            home = self._remote_home(client)
            paths = self._host_paths(home, task["task_id"])
            marker = shlex.quote(self._runner_version_marker)
            runner = shlex.quote(paths["runner"])
            version_matches = self._remote_output(client, f"grep -Fxq {marker} {runner} 2>/dev/null; printf '%s' $?")
            if version_matches.strip() != "0":
                self._write_host_runner(client, task, home)
            path = paths["state"]
            content = self._remote_output(client, f"cat {shlex.quote(path)} 2>/dev/null || true")
        return dict(line.split("=", 1) for line in content.splitlines() if "=" in line)

    def _read_host_log(self, session_token: Optional[str], task: sqlite3.Row) -> str:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            path = self._host_paths(self._remote_home(client), task["task_id"])["log"]
            return self._remote_output(client, f"tail -n 200 -- {shlex.quote(path)} 2>/dev/null || true")

    def _read_host_run_log(self, session_token: Optional[str], task: sqlite3.Row, log_path: str, before: Optional[int]) -> dict[str, Any]:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            command = f"wc -l < {shlex.quote(log_path)} 2>/dev/null || printf '0'"
            total_lines = int(self._remote_output(client, command).strip() or "0")
            end_line = min(total_lines, before) if before is not None else total_lines
            start_line = max(1, end_line - self._log_read_line_limit + 1)
            if end_line < 1:
                content = ""
            else:
                content = self._remote_output(client, f"sed -n '{start_line},{end_line}p' {shlex.quote(log_path)} 2>/dev/null | head -c {self._log_read_byte_limit}")
        return {"content": content, "next_before": start_line - 1 if start_line > 1 else None}

    def _read_log_window(self, path: Path, before: Optional[int]) -> dict[str, Any]:
        if not path.is_file():
            return {"content": "", "next_before": None}
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        end_line = min(len(lines), before) if before is not None else len(lines)
        start_line = max(0, end_line - self._log_read_line_limit)
        content = "\n".join(lines[start_line:end_line]).encode("utf-8")[: self._log_read_byte_limit].decode("utf-8", errors="ignore")
        return {"content": content, "next_before": start_line if start_line else None}

    def _sync_task_runs(self, session_token: Optional[str], task: sqlite3.Row) -> None:
        records = self._read_host_runs(session_token, task) if task["target"] == "host" else self._read_local_runs(task["task_id"])
        self._sync_task_run_records(task, records)
        if task["target"] == "container":
            self._finalize_interrupted_runs(task)

    def _finalize_interrupted_runs(self, task: sqlite3.Row) -> None:
        """Close runs that were killed before they could report a result.

        A run is recorded as `running` when it starts and rewritten when it ends. The local runner
        holds the current run id, so any other run still marked `running` was interrupted (task
        cancelled, container restarted) and would otherwise stay `running` in the history forever,
        even after a later run of the same task had already succeeded.
        """
        current_run_id = str(self._read_state(str(task["task_id"])).get("run_id") or "")
        # An interrupted run of a cancelled task is a cancellation, not a failure.
        final_status = "cancelled" if str(task["queue_state"] or "") == "cancelled" else "failed"
        statement = (
            "UPDATE scheduled_task_runs SET status = ?, finished_at = COALESCE(NULLIF(finished_at, ''), ?) "
            "WHERE task_id = ? AND status = 'running'"
        )
        parameters: list[Any] = [final_status, self._now_iso(), task["task_id"]]
        if final_status != "cancelled":
            # A live runner owns the run recorded in its state file; other runs were interrupted.
            statement += " AND run_id != ?"
            parameters.append(current_run_id)
        with self._db_connect() as connection:
            connection.execute(statement, parameters)
            connection.commit()

    def _sync_task_run_records(self, task: sqlite3.Row, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        # The runner writes "running" when a run starts and rewrites it when the run ends. A run that
        # was closed from the platform side (a cancelled pull, a container restart) therefore came
        # back to life on the next read, so a cancelled prewarm kept showing "running" forever.
        terminal = {"success", "failed", "skipped", "cancelled"}
        cancelled_run_id = self._read_state(str(task["task_id"])).get("run_id") if task["queue_state"] == "cancelled" else None
        with self._db_connect() as connection:
            stored = {
                row["run_id"]: row["status"]
                for row in connection.execute("SELECT run_id, status FROM scheduled_task_runs WHERE task_id = ?", (task["task_id"],))
            }
            for record in records:
                if record.get("task_id") != task["task_id"] or not record.get("run_id"):
                    continue
                if record["run_id"] == cancelled_run_id:
                    record = {**record, "status": "cancelled", "finished_at": record.get("finished_at") or self._now_iso()}
                incoming = record.get("status", "running")
                if stored.get(record["run_id"]) == "cancelled" or (incoming == "running" and stored.get(record["run_id"]) in terminal):
                    continue
                connection.execute(
                    "INSERT INTO scheduled_task_runs (run_id, task_id, started_at, finished_at, status, exit_code, trigger, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET finished_at = excluded.finished_at, status = excluded.status, exit_code = excluded.exit_code, log_path = excluded.log_path",
                    (record["run_id"], task["task_id"], record.get("started_at"), record.get("finished_at"), record.get("status", "running"), record.get("exit_code"), record.get("trigger", "cron"), record.get("log_path", "")),
                )
            latest = connection.execute("SELECT status, COALESCE(finished_at, started_at) AS run_at FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC LIMIT 1", (task["task_id"],)).fetchone()
            previous = connection.execute("SELECT last_status, last_run_at FROM scheduled_tasks WHERE task_id = ?", (task["task_id"],)).fetchone()
            connection.commit()
        if latest and previous and (previous["last_status"] != latest["status"] or previous["last_run_at"] != latest["run_at"]):
            self._write_task(task["task_id"], last_status=latest["status"], last_run_at=latest["run_at"], updated_at=self._now_iso())
        else:
            # Rewriting a row that did not change would only move `updated_at`, which the console
            # stream digests: every poll would then broadcast a snapshot and redraw the list.
            pass
        self._prune_run_index(task["task_id"])

    def _sync_host_task_runs_batch(self, session_token: Optional[str], profile_id: str, tasks: list[sqlite3.Row]) -> None:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=profile_id)
        with self.host_access_service._open_file_client(profile) as client:
            home = self._remote_home(client)
            run_dirs = " ".join(shlex.quote(self._host_paths(home, task["task_id"])["runs_dir"]) for task in tasks)
            content = self._remote_output(client, f"for run_dir in {run_dirs}; do for record in \"$run_dir\"/*.json; do [ -f \"$record\" ] && cat \"$record\"; done; done; true")
        records_by_task: dict[str, list[dict[str, Any]]] = {str(task["task_id"]): [] for task in tasks}
        for line in content.splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            task_id = str(record.get("task_id") or "")
            if task_id in records_by_task:
                records_by_task[task_id].append(record)
        for task in tasks:
            self._sync_task_run_records(task, records_by_task[str(task["task_id"])])

    def _read_local_runs(self, task_id: str) -> list[dict[str, Any]]:
        records = []
        for path in self._runs_dir(task_id).glob("*.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return records

    def _read_host_runs(self, session_token: Optional[str], task: sqlite3.Row) -> list[dict[str, Any]]:
        profile = self.host_access_service.get_connection_profile(session_token, profile_id=task["profile_id"])
        with self.host_access_service._open_file_client(profile) as client:
            home = self._remote_home(client)
            paths = self._host_paths(home, task["task_id"])
            marker = shlex.quote(self._runner_version_marker)
            runner = shlex.quote(paths["runner"])
            if self._remote_output(client, f"grep -Fxq {marker} {runner} 2>/dev/null; printf '%s' $?").strip() != "0":
                self._write_host_runner(client, task, home)
            content = self._remote_output(client, f"for record in {shlex.quote(paths['runs_dir'])}/*.json; do [ -f \"$record\" ] && cat \"$record\"; done; true")
        records = []
        for line in content.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def _prune_run_index(self, task_id: str) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - self._run_retention_days * 86400
        with self._db_connect() as connection:
            rows = connection.execute("SELECT run_id, started_at, status FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC, run_id DESC", (task_id,)).fetchall()
            stale = [row["run_id"] for index, row in enumerate(rows) if index >= self._run_retention_count or self._parse_timestamp(row["started_at"]) < cutoff]
            if stale:
                connection.executemany("DELETE FROM scheduled_task_runs WHERE run_id = ?", [(run_id,) for run_id in stale])
                connection.commit()

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> float:
        try:
            return datetime.fromisoformat(value or "").timestamp()
        except ValueError:
            return 0

    @staticmethod
    def _is_cron_schedule(schedule: Any) -> bool:
        """Only five-field cron expressions may reach the system crontab."""
        value = str(schedule or "").strip()
        return bool(value) and not value.startswith("@") and len(value.split()) == 5

    @staticmethod
    def _host_paths(home: str, task_id: str) -> dict[str, str]:
        root = f"{home}/.local/state/websoft9/scheduled-tasks"
        return {"scripts_dir": f"{root}/scripts", "logs_dir": f"{root}/logs", "runs_root": f"{root}/runs", "states_dir": f"{root}/state", "uploads_dir": f"{root}/uploads", "runner": f"{root}/scripts/{task_id}.sh", "upload": f"{root}/uploads/{task_id}.sh", "logs_task_dir": f"{root}/logs/{task_id}", "runs_dir": f"{root}/runs/{task_id}", "state": f"{root}/state/{task_id}.state", "lock": f"{root}/state/{task_id}.lock"}

    def _runner_content(self, state_path: str, lock_path: str, logs_dir: str, runs_dir: str, task_id: str, command: str, timeout_seconds: int = 0, retry_count: int = 0, prewarm: bool = False) -> str:
        state = shlex.quote(state_path)
        lock = shlex.quote(lock_path)
        logs = shlex.quote(logs_dir)
        runs = shlex.quote(runs_dir)
        quoted_task_id = shlex.quote(task_id)
        user_command = shlex.quote(command)
        execution = f"timeout {int(timeout_seconds)} bash -c {user_command}" if timeout_seconds else f"bash -c {user_command}"
        cleanup = (
            "find \"$RUNS\" -type f -name '*.json' -mtime +7 -delete\nfind \"$LOGS\" -type f -name '*.log' -mtime +7 -delete\n"
            "ls -1t \"$RUNS\"/*.json 2>/dev/null | tail -n +51 | while read -r stale; do rm -f \"$stale\" \"$LOGS/$(basename \"$stale\" .json).log\"; done\n"
        )
        completion = f"exec 9>&-\ntimeout 30 {shlex.quote(PLATFORM_CLI_PATH)} images dispatch --quiet || true\n" if prewarm else ""
        return (
            f"#!/bin/bash\n{self._runner_version_marker}\nset -u\n"
            f"STATE={state}\nLOCK={lock}\nLOGS={logs}\nRUNS={runs}\nTASK_ID={quoted_task_id}\n"
            "write_state() { printf 'run_id=%s\\nstatus=%s\\nstarted_at=%s\\nfinished_at=%s\\nexit_code=%s\\n' \"$1\" \"$2\" \"$3\" \"$4\" \"$5\" > \"${STATE}.tmp\" && mv \"${STATE}.tmp\" \"$STATE\"; }\n"
            "write_log() { printf '[%s] %s\\n' \"$(date -Iseconds)\" \"$1\" >> \"$LOG\"; }\n"
            "write_run() { printf '{\"run_id\":\"%s\",\"task_id\":\"%s\",\"started_at\":\"%s\",\"finished_at\":\"%s\",\"status\":\"%s\",\"exit_code\":%s,\"trigger\":\"%s\",\"log_path\":\"%s\"}\\n' \"$run_id\" \"$TASK_ID\" \"$started_at\" \"$1\" \"$2\" \"$3\" \"$trigger\" \"$LOG\" > \"${RUN}.tmp\" && mv \"${RUN}.tmp\" \"$RUN\"; }\n"
            "trigger=\"${1:-cron}\"\n"
            "run_id=\"$(date +%s%N)-$$\"\nLOG=\"$LOGS/$run_id.log\"\nRUN=\"$RUNS/$run_id.json\"\nstarted_at=$(date -Iseconds)\nmkdir -p \"$LOGS\" \"$RUNS\"\nexec 9>\"$LOCK\"\nif ! flock -n 9; then\n  write_log \"SKIPPED trigger=$trigger reason=previous_execution_running\"\n  write_run \"$started_at\" skipped 0\n  exit 0\nfi\n"
            "started_epoch=$(date +%s)\nwrite_state \"$run_id\" running \"$started_at\" \"\" \"\"\nwrite_run \"\" running null\nwrite_log \"START trigger=$trigger\"\n"
            "attempt=0\n"
            "while true; do\n"
            "  attempt=$((attempt + 1))\n"
            f"  {execution} >> \"$LOG\" 2>&1\n"
            "  exit_code=$?\n"
            f"  if [ \"$exit_code\" -eq 0 ] || [ \"$exit_code\" -eq {SKIPPED_EXIT_CODE} ] || [ \"$attempt\" -gt {int(retry_count)} ]; then break; fi\n"
            f"  write_log \"RETRY trigger=$trigger attempt=$((attempt + 1))/{int(retry_count) + 1} exit_code=$exit_code\"\n"
            "done\n"
            f"if [ \"$exit_code\" -eq 0 ]; then status=success; elif [ \"$exit_code\" -eq {SKIPPED_EXIT_CODE} ]; then status=skipped; write_log \"SKIPPED trigger=$trigger reason=command_reported_skip\"; else status=failed; fi\nfinished_at=$(date -Iseconds)\nduration=$(( $(date +%s) - started_epoch ))\nwrite_state \"$run_id\" \"$status\" \"$started_at\" \"$finished_at\" \"$exit_code\"\nwrite_log \"END trigger=$trigger status=$status exit_code=$exit_code duration=${{duration}}s\"\nwrite_run \"$finished_at\" \"$status\" \"$exit_code\"\n"
            + cleanup + completion
            + f"if [ \"$exit_code\" -eq {SKIPPED_EXIT_CODE} ]; then exit 0; fi\nexit \"$exit_code\"\n"
        )

    def _remote_output(self, client: Any, command: str) -> str:
        try:
            _, stdout, stderr = client.exec_command(command, timeout=15)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            error_text = stderr.read().decode("utf-8", errors="replace").strip()
        except Exception as exc:
            raise CustomException(503, "Scheduled Task Host Unavailable", f"Unable to communicate with the SSH host: {exc}") from exc
        if exit_code != 0:
            raise CustomException(503, "Scheduled Task Host Unavailable", error_text or "The SSH host command failed")
        return output

    def _run_remote(self, client: Any, command: str, title: str, prefix: str) -> None:
        try:
            _, stdout, stderr = client.exec_command(command, timeout=15)
            exit_code = stdout.channel.recv_exit_status()
            error_text = stderr.read().decode("utf-8", errors="replace").strip()
        except Exception as exc:
            raise CustomException(503, title, f"{prefix}: {exc}") from exc
        if exit_code != 0:
            raise CustomException(503, title, f"{prefix}: {error_text or 'remote command failed'}")

    def _sync_tasks(self, tasks: list[sqlite3.Row]) -> None:
        self._ensure_storage()
        for task in tasks:
            self._write_runner(task)
        self.cron_file.parent.mkdir(parents=True, exist_ok=True)
        previous_contents = self.cron_file.read_bytes() if self.cron_file.exists() else None
        previous_mode = self.cron_file.stat().st_mode if self.cron_file.exists() else None
        lines = ["SHELL=/bin/bash", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "",
             f"* * * * * root {PLATFORM_CLI_PATH} images dispatch --quiet"]
        for task in tasks:
            # `@once` marks a task this platform dispatches by hand, not a cron expression. Writing it
            # produced an invalid line in /etc/cron.d, which made cron reject the entire file and
            # silently stopped every scheduled task on the platform.
            if not self._is_cron_schedule(task["schedule"]):
                continue
            lines.append(f"{task['schedule']} root {self._runner_path(task['task_id'])}")
        rendered = ("\n".join(lines) + "\n").encode("utf-8")
        if previous_contents == rendered:
            # Startup reconciles this file on every boot, and restarting cron for an identical
            # file would interrupt nothing but still cost a service restart.
            return
        temporary = self.cron_file.with_suffix(".tmp")
        temporary.write_bytes(rendered)
        temporary.chmod(0o644)
        temporary.replace(self.cron_file)
        try:
            self._cron_reloader()
        except Exception:
            if previous_contents is None:
                self.cron_file.unlink(missing_ok=True)
            else:
                rollback = self.cron_file.with_suffix(".rollback")
                rollback.write_bytes(previous_contents)
                rollback.chmod(previous_mode or 0o644)
                rollback.replace(self.cron_file)
            try:
                self._cron_reloader()
            except Exception:
                pass
            raise

    def _write_runner(self, task: sqlite3.Row) -> None:
        self._scripts_dir().mkdir(parents=True, exist_ok=True)
        self._task_logs_dir(task["task_id"]).mkdir(parents=True, exist_ok=True)
        self._runs_dir(task["task_id"]).mkdir(parents=True, exist_ok=True)
        self._states_dir().mkdir(parents=True, exist_ok=True)
        runner = self._runner_path(task["task_id"])
        state = shlex.quote(str(self._state_path(task["task_id"])))
        lock = shlex.quote(str(self._lock_path(task["task_id"])))
        log = shlex.quote(str(self._log_path(task["task_id"])))
        command = self._task_command(task, str(self._uploaded_script_path(task)))
        runner.write_text(
            self._runner_content(str(self._state_path(task["task_id"])), str(self._lock_path(task["task_id"])), str(self._task_logs_dir(task["task_id"])), str(self._runs_dir(task["task_id"])), task["task_id"], command, task["timeout_seconds"], task["retry_count"], prewarm=str(task["category"] or "") == "prewarm"),
            encoding="utf-8",
        )
        runner.chmod(0o700)

    def _upgrade_local_runner_if_needed(self, task: sqlite3.Row) -> None:
        runner = self._runner_path(task["task_id"])
        if not runner.is_file() or self._runner_version_marker not in runner.read_text(encoding="utf-8", errors="replace"):
            self._write_runner(task)

    def _ensure_storage(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._db_connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    task_id TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    target TEXT NOT NULL,
                    profile_id TEXT,
                    schedule TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    command TEXT NOT NULL,
                    execution_mode TEXT NOT NULL DEFAULT 'command',
                    script_path TEXT,
                    script_name TEXT,
                    timeout_seconds INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL,
                    last_run_at TEXT,
                    last_status TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    next_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    origin TEXT NOT NULL DEFAULT 'user',
                    category TEXT,
                    subject_app TEXT,
                    subject_version TEXT,
                    queue_state TEXT,
                    claimed_at TEXT,
                    claimed_by TEXT,
                    runner_pgid INTEGER,
                    UNIQUE(operator_id, name)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_task_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    exit_code INTEGER,
                    trigger TEXT NOT NULL,
                    log_path TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_task_started ON scheduled_task_runs (task_id, started_at DESC)")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(scheduled_tasks)")}
            for name, definition in (("execution_mode", "TEXT NOT NULL DEFAULT 'command'"), ("script_path", "TEXT"), ("script_name", "TEXT"), ("timeout_seconds", "INTEGER NOT NULL DEFAULT 0"), ("retry_count", "INTEGER NOT NULL DEFAULT 0"), ("origin", "TEXT NOT NULL DEFAULT 'user'"), ("category", "TEXT"), ("subject_app", "TEXT"), ("subject_version", "TEXT"), ("queue_state", "TEXT"), ("claimed_at", "TEXT"), ("claimed_by", "TEXT"), ("runner_pgid", "INTEGER")):
                if name not in columns:
                    connection.execute(f"ALTER TABLE scheduled_tasks ADD COLUMN {name} {definition}")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_prewarm ON scheduled_tasks(category, subject_app, subject_version, operator_id)")
            legacy_id = "system:image-prewarm-dispatch"
            legacy = connection.execute("SELECT task_id FROM scheduled_tasks WHERE task_id = ? AND origin = ?", (legacy_id, SYSTEM_ORIGIN)).fetchone()
            if legacy:
                connection.execute("DELETE FROM scheduled_task_runs WHERE task_id = ?", (legacy_id,))
                connection.execute("DELETE FROM scheduled_tasks WHERE task_id = ?", (legacy_id,))
            connection.commit()
        if legacy:
            for path in (self._runner_path(legacy_id), self._state_path(legacy_id), self._lock_path(legacy_id)):
                path.unlink(missing_ok=True)
            for path in (self._task_logs_dir(legacy_id), self._runs_dir(legacy_id)):
                shutil.rmtree(path, ignore_errors=True)
        self._seed_system_tasks()

    def _seed_system_tasks(self) -> None:
        """Create the product's own tasks once, and never overwrite an existing row.

        The platform's maintenance jobs used to live only in the image crontab. Keeping them in
        the same store as an operator's tasks is what makes their run history and logs visible,
        and `INSERT OR IGNORE` means a restart or an upgrade only fills in what is missing.
        """
        now = self._now_iso()
        timezone_name = self._platform_timezone()
        with self._db_connect() as connection:
            for definition in SYSTEM_TASKS:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO scheduled_tasks (
                        task_id, operator_id, name, target, profile_id, schedule, timezone, command, execution_mode, script_path, script_name, timeout_seconds, retry_count, enabled,
                        last_run_at, last_status, sync_status, next_run_at, created_at, updated_at, origin
                    ) VALUES (?, ?, ?, 'container', NULL, ?, ?, ?, 'command', NULL, NULL, ?, 0, 1, NULL, 'never', 'synced', ?, ?, ?, ?)
                    """,
                    (
                        definition["task_id"],
                        SYSTEM_OPERATOR_ID,
                        definition["name"],
                        definition["schedule"],
                        timezone_name,
                        definition["command"],
                        definition["timeout_seconds"],
                        self._next_run(definition["schedule"], timezone_name),
                        now,
                        now,
                        SYSTEM_ORIGIN,
                    ),
                )
                # A platform task cannot be renamed by an operator, so its stored name may safely
                # follow the definition; `INSERT OR IGNORE` alone would keep an older name.
                connection.execute(
                    "UPDATE scheduled_tasks SET name = ? WHERE task_id = ? AND origin = ? AND name != ?",
                    (definition["name"], definition["task_id"], SYSTEM_ORIGIN, definition["name"]),
                )
            connection.commit()

    def _db_connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_file))
        connection.row_factory = sqlite3.Row
        return connection

    def _insert_task(self, task: dict[str, Any]) -> None:
        with self._db_connect() as connection:
            connection.execute(
                """
                INSERT INTO scheduled_tasks (
                    task_id, operator_id, name, target, profile_id, schedule, timezone, command, execution_mode, script_path, script_name, timeout_seconds, retry_count, enabled,
                    last_run_at, last_status, sync_status, next_run_at, created_at, updated_at,
                    category, subject_app, subject_version, queue_state, claimed_at, claimed_by, runner_pgid
                ) VALUES (
                    :task_id, :operator_id, :name, :target, :profile_id, :schedule, :timezone, :command, :execution_mode, :script_path, :script_name, :timeout_seconds, :retry_count, :enabled,
                    :last_run_at, :last_status, :sync_status, :next_run_at, :created_at, :updated_at,
                    :category, :subject_app, :subject_version, :queue_state, :claimed_at, :claimed_by, :runner_pgid
                )
                """,
                task,
            )
            connection.commit()

    def _write_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._db_connect() as connection:
            connection.execute(f"UPDATE scheduled_tasks SET {assignments} WHERE task_id = ?", [*fields.values(), task_id])
            connection.commit()

    def _delete_task(self, task_id: str) -> None:
        with self._db_connect() as connection:
            connection.execute("DELETE FROM scheduled_tasks WHERE task_id = ?", (task_id,))
            connection.commit()

    def _get_task(self, operator_id: str, task_id: str) -> sqlite3.Row:
        self._ensure_storage()
        with self._db_connect() as connection:
            task = connection.execute(
                "SELECT * FROM scheduled_tasks WHERE task_id = ? AND (operator_id = ? OR origin = ?)",
                (task_id, operator_id, SYSTEM_ORIGIN),
            ).fetchone()
        if task is None:
            raise CustomException(404, "Scheduled Task Not Found", "The requested task does not exist")
        return task

    @staticmethod
    def _require_mutable(task: sqlite3.Row) -> None:
        """Refuse a write to a platform task: it is part of the product, not the operator's."""
        if str(task["origin"] or "") == SYSTEM_ORIGIN:
            raise CustomException(
                403,
                "Platform Task Read-only",
                "Platform tasks are maintained by the product and cannot be edited, deleted, disabled or run manually",
            )
        if str(task["category"] or "") == "prewarm":
            raise CustomException(
                403,
                "Prewarm Task Managed",
                "Image prewarm tasks must be managed through their dedicated controls",
            )

    def _get_task_by_id(self, task_id: str) -> sqlite3.Row:
        self._ensure_storage()
        with self._db_connect() as connection:
            task = connection.execute("SELECT * FROM scheduled_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if task is None:
            raise CustomException(404, "Scheduled Task Not Found", "The requested task does not exist")
        return task

    def _list_tasks(self, operator_id: str) -> list[sqlite3.Row]:
        with self._db_connect() as connection:
            return connection.execute(
                "SELECT * FROM scheduled_tasks WHERE operator_id = ? ORDER BY created_at DESC", (operator_id,)
            ).fetchall()

    def _list_system_tasks(self) -> list[sqlite3.Row]:
        """The platform's own tasks, listed apart from an operator's own."""
        with self._db_connect() as connection:
            return connection.execute(
                "SELECT * FROM scheduled_tasks WHERE origin = ? ORDER BY created_at ASC", (SYSTEM_ORIGIN,)
            ).fetchall()

    def _list_enabled_tasks(self) -> list[sqlite3.Row]:
        with self._db_connect() as connection:
            return connection.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY created_at ASC").fetchall()

    def _task_name_exists(self, operator_id: str, name: str) -> bool:
        with self._db_connect() as connection:
            return connection.execute(
                "SELECT 1 FROM scheduled_tasks WHERE operator_id = ? AND name = ?", (operator_id, name)
            ).fetchone() is not None

    def _next_run(self, schedule: str, timezone_name: Optional[str] = None) -> Optional[str]:
        if schedule == "@once":
            return None
        try:
            current_time = datetime.now(ZoneInfo(timezone_name or "UTC"))
        except (ZoneInfoNotFoundError, ValueError):
            current_time = datetime.now(timezone.utc)
        return croniter(schedule, current_time).get_next(datetime).astimezone(timezone.utc).isoformat()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _platform_timezone() -> str:
        """Zone this container's schedules are interpreted and displayed in.

        `TZ` wins when the deployment declared one, because that is the value the install
        states. Falling back to a literal "UTC" would instead make the console compute next
        run times in UTC while cron fires them in the container's own local time, so the
        container is asked when no usable `TZ` is present.
        """
        declared = os.getenv("TZ", "").strip()
        if declared:
            try:
                ZoneInfo(declared)
                return declared
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning(f"Ignoring unusable TZ={declared!r}: it is not a known IANA zone")
        return _container_local_zone()

    def _scripts_dir(self) -> Path:
        return self.data_dir / "scripts"

    def _uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    def _logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def _task_logs_dir(self, task_id: str) -> Path:
        return self._logs_dir() / task_id

    def _runs_dir(self, task_id: str) -> Path:
        return self.data_dir / "runs" / task_id

    def _states_dir(self) -> Path:
        return self.data_dir / "state"

    @staticmethod
    def _prewarm_instance_id() -> str:
        path = Path(os.getenv("WEBSOFT9_PREWARM_INSTANCE_ID_FILE", "/run/websoft9/prewarm-instance-id"))
        try:
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        instance_id = str(uuid.uuid4())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(instance_id, encoding="utf-8")
        except OSError:
            logger.warning("Unable to persist the prewarm dispatcher instance identifier")
        return instance_id

    @staticmethod
    def _prewarm_runner_alive(pgid: object) -> bool:
        """True while any process of the run is still running.

        `os.killpg` alone would answer "alive" for the runner shell even after the pull it started
        was killed, and also for a not yet reaped zombie, so liveness is read from the session.
        """
        return bool(ScheduledTaskService._prewarm_session_pids(pgid))

    def _runner_path(self, task_id: str) -> Path:
        return self._scripts_dir() / f"{task_id}.sh"

    def _log_path(self, task_id: str) -> Path:
        return self._logs_dir() / f"{task_id}.log"

    def _state_path(self, task_id: str) -> Path:
        return self._states_dir() / f"{task_id}.state"

    def _lock_path(self, task_id: str) -> Path:
        return self._states_dir() / f"{task_id}.lock"

    def _uploaded_script_path(self, task: sqlite3.Row) -> Path:
        return self._uploads_dir() / f"{task['task_id']}.sh"

    def _task_command(self, task: sqlite3.Row, uploaded_script_path: Optional[str] = None) -> str:
        if task["execution_mode"] == "path":
            return f"bash -- {shlex.quote(task['script_path'])}"
        if task["execution_mode"] == "upload":
            return f"bash -- {shlex.quote(uploaded_script_path or str(self._uploaded_script_path(task)))}"
        return task["command"]

    def _read_state(self, task_id: str) -> dict[str, str]:
        state_path = self._state_path(task_id)
        if not state_path.is_file():
            return {}
        return dict(line.split("=", 1) for line in state_path.read_text(encoding="utf-8").splitlines() if "=" in line)

    def _execution_path(self, task) -> str:
        task_id = task["task_id"]
        if task["execution_mode"] == "path":
            return task["script_path"] or ""
        if task["target"] == "container":
            if task["execution_mode"] == "upload":
                return str(self._uploaded_script_path(task))
            return str(self._runner_path(task_id))
        remote_root = "~/.local/state/websoft9/scheduled-tasks"
        if task["execution_mode"] == "upload":
            return f"{remote_root}/uploads/{task_id}.sh"
        return f"{remote_root}/scripts/{task_id}.sh"

    def _public_task(self, task: sqlite3.Row) -> dict[str, Any]:
        return {
            "task_id": task["task_id"], "name": task["name"], "target": task["target"],
            "profile_id": task["profile_id"], "schedule": task["schedule"], "timezone": task["timezone"],
            "command": task["command"], "execution_mode": task["execution_mode"], "script_path": task["script_path"], "script_name": task["script_name"], "timeout_seconds": task["timeout_seconds"], "retry_count": task["retry_count"], "enabled": bool(task["enabled"]), "last_run_at": task["last_run_at"],
            "last_status": task["last_status"], "sync_status": task["sync_status"], "next_run_at": self._next_run(task["schedule"], task["timezone"]),
            "created_at": task["created_at"], "updated_at": task["updated_at"],
            "execution_path": self._execution_path(task),
            "origin": str(task["origin"] or "user"),
            "category": task["category"], "subject_app": task["subject_app"], "subject_version": task["subject_version"],
            "queue_state": task["queue_state"],
        }

    @staticmethod
    def _reload_cron() -> None:
        config_path = os.getenv("WEBSOFT9_SUPERVISOR_CONFIG", "/etc/supervisor/conf.d/websoft9-platform.conf")
        subprocess.run(["supervisorctl", "-c", config_path, "restart", "cron"], check=True, capture_output=True, text=True)