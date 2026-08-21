from __future__ import annotations

import os
import base64
import json
import shlex
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
from src.services.host_access import HostAccessService
from src.services.product_auth import ProductAuthService


class ScheduledTaskService:
    """Persist and run simple platform-container cron tasks."""

    _lock = threading.RLock()
    _host_capability_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
    _background_syncing: set[str] = set()
    _background_syncing_task_ids: dict[str, set[str]] = {}
    _runner_version_marker = "# websoft9-task-runner-version: 4"
    _run_retention_count = 50
    _run_retention_days = 7
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
        operator_id = str(operator["id"])
        with self._lock:
            syncing_task_ids = self._background_syncing_task_ids.get(operator_id, set()).copy()
        tasks = []
        for task in self._list_tasks(operator_id):
            public_task = self._public_task(task)
            public_task["syncing"] = task["task_id"] in syncing_task_ids
            tasks.append(public_task)
        return {
            "tasks": tasks,
        }

    def start_sync(self, session_token: Optional[str]) -> dict[str, str]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        self._ensure_storage()
        self._start_background_sync(session_token, str(operator["id"]))
        return {"status": "started"}

    def _start_background_sync(self, session_token: Optional[str], operator_id: str) -> None:
        with self._lock:
            if operator_id in self._background_syncing:
                return
            self._background_syncing.add(operator_id)
        threading.Thread(target=self._sync_operator_tasks_in_background, args=(session_token, operator_id), daemon=True).start()

    def _sync_operator_tasks_in_background(self, session_token: Optional[str], operator_id: str) -> None:
        try:
            tasks = self._list_tasks(operator_id)
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
        }
        with self._lock:
            self._ensure_storage()
            if self._task_name_exists(operator["id"], task["name"]):
                raise CustomException(409, "Scheduled Task Already Exists", "A task with this name already exists")
            self._insert_task(task)
            if normalized["execution_mode"] == "upload":
                self._store_uploaded_script(session_token, self._get_task(operator["id"], task["task_id"]), normalized["script_content"])
            self._sync_or_mark_failed(session_token, task["task_id"])
        return self._public_task(self._get_task(operator["id"], task["task_id"]))

    def update_task(self, session_token: Optional[str], task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        normalized = self._normalize_payload(payload)
        capability = self._host_capability_or_none(session_token, normalized)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
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
            self._write_task(task_id, enabled=int(enabled), updated_at=self._now_iso())
            self._sync_or_mark_failed(session_token, task_id)
        return self._public_task(self._get_task(operator["id"], task_id))

    def delete_task(self, session_token: Optional[str], task_id: str) -> None:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
            if task["target"] == "host":
                self._sync_host_tasks(session_token, task["profile_id"], exclude_task_id=task_id)
                self._remove_host_task_files(session_token, task)
            else:
                self._sync_without_task(task_id)
            self._delete_task(task_id)
            for path in (self._runner_path(task_id), self._log_path(task_id), self._state_path(task_id), self._lock_path(task_id), self._uploaded_script_path(task)):
                path.unlink(missing_ok=True)
            self._task_logs_dir(task_id).unlink(missing_ok=True) if self._task_logs_dir(task_id).is_file() else None
            if self._task_logs_dir(task_id).is_dir():
                subprocess.run(["rm", "-rf", str(self._task_logs_dir(task_id)), str(self._runs_dir(task_id))], check=False)

    def run_task(self, session_token: Optional[str], task_id: str) -> dict[str, Any]:
        operator = self.auth_service._require_authenticated_operator(session_token)
        with self._lock:
            task = self._get_task(operator["id"], task_id)
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
        self._get_task(operator["id"], task_id)
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

    def _normalize_payload(self, payload: dict[str, Any], require_upload_content: bool = False) -> dict[str, Any]:
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
        timeout_seconds = int(payload.get("timeout_seconds") or 0)
        retry_count = int(payload.get("retry_count") or 0)
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
        if len(schedule.split()) != 5 or "\n" in schedule:
            raise CustomException(400, "Invalid Schedule", "Schedule must be a five-field cron expression")
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
        self._sync_tasks([task for task in self._list_enabled_tasks() if task["target"] == "container"])

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
        return [task for task in rows if task["task_id"] != exclude_task_id]

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

    def _sync_task_run_records(self, task: sqlite3.Row, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        with self._db_connect() as connection:
            for record in records:
                if record.get("task_id") != task["task_id"] or not record.get("run_id"):
                    continue
                connection.execute(
                    "INSERT INTO scheduled_task_runs (run_id, task_id, started_at, finished_at, status, exit_code, trigger, log_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET finished_at = excluded.finished_at, status = excluded.status, exit_code = excluded.exit_code, log_path = excluded.log_path",
                    (record["run_id"], task["task_id"], record.get("started_at"), record.get("finished_at"), record.get("status", "running"), record.get("exit_code"), record.get("trigger", "cron"), record.get("log_path", "")),
                )
            latest = connection.execute("SELECT status, COALESCE(finished_at, started_at) AS run_at FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC LIMIT 1", (task["task_id"],)).fetchone()
            connection.commit()
        if latest:
            self._write_task(task["task_id"], last_status=latest["status"], last_run_at=latest["run_at"], updated_at=self._now_iso())
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
            rows = connection.execute("SELECT run_id, started_at FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC", (task_id,)).fetchall()
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
    def _host_paths(home: str, task_id: str) -> dict[str, str]:
        root = f"{home}/.local/state/websoft9/scheduled-tasks"
        return {"scripts_dir": f"{root}/scripts", "logs_dir": f"{root}/logs", "runs_root": f"{root}/runs", "states_dir": f"{root}/state", "uploads_dir": f"{root}/uploads", "runner": f"{root}/scripts/{task_id}.sh", "upload": f"{root}/uploads/{task_id}.sh", "logs_task_dir": f"{root}/logs/{task_id}", "runs_dir": f"{root}/runs/{task_id}", "state": f"{root}/state/{task_id}.state", "lock": f"{root}/state/{task_id}.lock"}

    def _runner_content(self, state_path: str, lock_path: str, logs_dir: str, runs_dir: str, task_id: str, command: str, timeout_seconds: int = 0, retry_count: int = 0) -> str:
        state = shlex.quote(state_path)
        lock = shlex.quote(lock_path)
        logs = shlex.quote(logs_dir)
        runs = shlex.quote(runs_dir)
        quoted_task_id = shlex.quote(task_id)
        user_command = shlex.quote(command)
        execution = f"timeout {int(timeout_seconds)} bash -c {user_command}" if timeout_seconds else f"bash -c {user_command}"
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
            f"  if [ \"$exit_code\" -eq 0 ] || [ \"$attempt\" -gt {int(retry_count)} ]; then break; fi\n"
            f"  write_log \"RETRY trigger=$trigger attempt=$((attempt + 1))/{int(retry_count) + 1} exit_code=$exit_code\"\n"
            "done\n"
            "if [ \"$exit_code\" -eq 0 ]; then status=success; else status=failed; fi\nfinished_at=$(date -Iseconds)\nduration=$(( $(date +%s) - started_epoch ))\nwrite_state \"$run_id\" \"$status\" \"$started_at\" \"$finished_at\" \"$exit_code\"\nwrite_log \"END trigger=$trigger status=$status exit_code=$exit_code duration=${duration}s\"\nwrite_run \"$finished_at\" \"$status\" \"$exit_code\"\nfind \"$RUNS\" -type f -name '*.json' -mtime +7 -delete\nfind \"$LOGS\" -type f -name '*.log' -mtime +7 -delete\nls -1t \"$RUNS\"/*.json 2>/dev/null | tail -n +51 | while read -r stale; do rm -f \"$stale\" \"$LOGS/$(basename \"$stale\" .json).log\"; done\nexit \"$exit_code\"\n"
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
        lines = ["SHELL=/bin/bash", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", ""]
        for task in tasks:
            lines.append(f"{task['schedule']} root {self._runner_path(task['task_id'])}")
        temporary = self.cron_file.with_suffix(".tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
            self._runner_content(str(self._state_path(task["task_id"])), str(self._lock_path(task["task_id"])), str(self._task_logs_dir(task["task_id"])), str(self._runs_dir(task["task_id"])), task["task_id"], command, task["timeout_seconds"], task["retry_count"]),
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
            for name, definition in (("execution_mode", "TEXT NOT NULL DEFAULT 'command'"), ("script_path", "TEXT"), ("script_name", "TEXT"), ("timeout_seconds", "INTEGER NOT NULL DEFAULT 0"), ("retry_count", "INTEGER NOT NULL DEFAULT 0")):
                if name not in columns:
                    connection.execute(f"ALTER TABLE scheduled_tasks ADD COLUMN {name} {definition}")
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
                    last_run_at, last_status, sync_status, next_run_at, created_at, updated_at
                ) VALUES (
                    :task_id, :operator_id, :name, :target, :profile_id, :schedule, :timezone, :command, :execution_mode, :script_path, :script_name, :timeout_seconds, :retry_count, :enabled,
                    :last_run_at, :last_status, :sync_status, :next_run_at, :created_at, :updated_at
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
                "SELECT * FROM scheduled_tasks WHERE operator_id = ? AND task_id = ?", (operator_id, task_id)
            ).fetchone()
        if task is None:
            raise CustomException(404, "Scheduled Task Not Found", "The requested task does not exist")
        return task

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

    def _list_enabled_tasks(self) -> list[sqlite3.Row]:
        with self._db_connect() as connection:
            return connection.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY created_at ASC").fetchall()

    def _task_name_exists(self, operator_id: str, name: str) -> bool:
        with self._db_connect() as connection:
            return connection.execute(
                "SELECT 1 FROM scheduled_tasks WHERE operator_id = ? AND name = ?", (operator_id, name)
            ).fetchone() is not None

    def _next_run(self, schedule: str, timezone_name: Optional[str] = None) -> str:
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
        return os.getenv("TZ") or "UTC"

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

    def _public_task(self, task: sqlite3.Row) -> dict[str, Any]:
        return {
            "task_id": task["task_id"], "name": task["name"], "target": task["target"],
            "profile_id": task["profile_id"], "schedule": task["schedule"], "timezone": task["timezone"],
            "command": task["command"], "execution_mode": task["execution_mode"], "script_path": task["script_path"], "script_name": task["script_name"], "timeout_seconds": task["timeout_seconds"], "retry_count": task["retry_count"], "enabled": bool(task["enabled"]), "last_run_at": task["last_run_at"],
            "last_status": task["last_status"], "sync_status": task["sync_status"], "next_run_at": self._next_run(task["schedule"], task["timezone"]),
            "created_at": task["created_at"], "updated_at": task["updated_at"],
        }

    @staticmethod
    def _reload_cron() -> None:
        config_path = os.getenv("WEBSOFT9_SUPERVISOR_CONFIG", "/etc/supervisor/conf.d/websoft9-platform.conf")
        subprocess.run(["supervisorctl", "-c", config_path, "restart", "cron"], check=True, capture_output=True, text=True)