from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.logger import logger, set_tracking_context


MAX_SUB_LOGS = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class InstallStateStore:
    def __init__(self, data_dir: str | None = None):
        self._lock = threading.RLock()
        self.reconfigure(data_dir)

    def reconfigure(self, data_dir: str | None = None) -> None:
        base_dir = data_dir or os.getenv("WEBSOFT9_INSTALL_TRACKING_DIR") or "/data/config/apphub"
        self.data_dir = Path(base_dir)
        self.database_file = self.data_dir / "install-tracking.sqlite"
        self._ensure_storage()

    def _db_connect(self) -> sqlite3.Connection:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_file, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_storage(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._db_connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS install_tasks (
                    tracking_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    app_name TEXT,
                    app_official INTEGER NOT NULL DEFAULT 1,
                    status INTEGER NOT NULL,
                    error TEXT,
                    reserved_ports TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS install_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    stage_order INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tracking_id, stage_name),
                    FOREIGN KEY (tracking_id) REFERENCES install_tasks(tracking_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS install_stage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage_id INTEGER NOT NULL,
                    entry_order INTEGER NOT NULL,
                    level TEXT NOT NULL DEFAULT 'info',
                    message TEXT NOT NULL,
                    raw_payload TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (stage_id) REFERENCES install_stages(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_install_tasks_status ON install_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_install_stages_tracking_id ON install_stages(tracking_id, stage_order);
                CREATE INDEX IF NOT EXISTS idx_install_stage_logs_stage_id ON install_stage_logs(stage_id, entry_order);
                """
            )
            connection.commit()

    def _normalize_ports(self, reserved_ports: Any) -> list[int]:
        normalized: list[int] = []
        for value in reserved_ports or []:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                continue
        return sorted(set(normalized))

    def _serialize_log_payload(self, log: Any) -> tuple[str, str | None, str]:
        level = "info"
        if log is None:
            return "", None, level
        if isinstance(log, dict):
            raw_payload = _json_dumps(log)
            message_parts = []
            for key in ("status", "message", "details", "id"):
                value = log.get(key)
                if value not in (None, ""):
                    prefix = "#" if key == "id" else ""
                    message_parts.append(f"{prefix}{value}")
            if isinstance(log.get("level"), str) and log.get("level"):
                level = str(log["level"]).lower()
            message = " ".join(message_parts) if message_parts else raw_payload
            return message, raw_payload, level
        if isinstance(log, (list, tuple)):
            raw_payload = _json_dumps(list(log))
            return raw_payload, raw_payload, level
        if isinstance(log, (str, int, float, bool)):
            return str(log), _json_dumps(log), level
        raw_payload = _json_dumps(str(log))
        return str(log), raw_payload, level

    def _decode_raw_payload(self, row: sqlite3.Row) -> Any:
        raw_payload = row["raw_payload"]
        level = row["level"]
        created_at = row["created_at"]
        message = row["message"]

        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                payload = raw_payload
        else:
            payload = message

        if isinstance(payload, dict):
            payload.setdefault("message", message)
            payload.setdefault("level", level)
            payload.setdefault("timestamp", created_at)
            return payload

        if payload == "":
            return {
                "message": "",
                "level": level,
                "timestamp": created_at,
            }

        return {
            "message": str(payload),
            "level": level,
            "timestamp": created_at,
        }

    def _get_stage_row(self, connection: sqlite3.Connection, tracking_id: str, stage_name: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT id, tracking_id, stage_name, stage_order FROM install_stages WHERE tracking_id = ? AND stage_name = ?",
            (tracking_id, stage_name),
        ).fetchone()

    def _ensure_stage(self, connection: sqlite3.Connection, tracking_id: str, stage_name: str) -> sqlite3.Row:
        now = _utc_now()
        stage_row = self._get_stage_row(connection, tracking_id, stage_name)
        if stage_row is not None:
            connection.execute(
                "UPDATE install_stages SET updated_at = ? WHERE id = ?",
                (now, stage_row["id"]),
            )
            return self._get_stage_row(connection, tracking_id, stage_name)

        next_order = connection.execute(
            "SELECT COALESCE(MAX(stage_order), 0) + 1 AS next_order FROM install_stages WHERE tracking_id = ?",
            (tracking_id,),
        ).fetchone()["next_order"]
        connection.execute(
            "INSERT INTO install_stages (tracking_id, stage_name, stage_order, started_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (tracking_id, stage_name, next_order, now, now),
        )
        return self._get_stage_row(connection, tracking_id, stage_name)

    def create_task(self, app_id: str, app_name: str | None, tracking_id: str | None = None, reserved_ports: Any = None, status: int = 3, app_official: bool = True, error: str | None = None, logs: list[dict[str, Any]] | None = None) -> str:
        tracking_id = tracking_id or str(uuid.uuid4())
        now = _utc_now()
        with self._lock, self._db_connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO install_tasks (tracking_id, app_id, app_name, app_official, status, error, reserved_ports, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM install_tasks WHERE tracking_id = ?), ?), ?)
                """,
                (
                    tracking_id,
                    app_id,
                    app_name,
                    1 if app_official else 0,
                    status,
                    error,
                    _json_dumps(self._normalize_ports(reserved_ports)),
                    tracking_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "DELETE FROM install_stages WHERE tracking_id = ?",
                (tracking_id,),
            )
            if logs:
                for stage in logs:
                    stage_name = str(stage.get("title") or "")
                    stage_row = self._ensure_stage(connection, tracking_id, stage_name)
                    sub_logs = stage.get("sub_logs") or []
                    for entry_order, log_entry in enumerate(sub_logs, start=1):
                        message, raw_payload, level = self._serialize_log_payload(log_entry)
                        connection.execute(
                            "INSERT INTO install_stage_logs (stage_id, entry_order, level, message, raw_payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (stage_row["id"], entry_order, level, message, raw_payload, _utc_now()),
                        )
            connection.commit()
        return tracking_id

    def append_log(self, tracking_id: str, stage_name: str, log: Any) -> None:
        with self._lock, self._db_connect() as connection:
            stage_row = self._ensure_stage(connection, tracking_id, stage_name)
            message, raw_payload, level = self._serialize_log_payload(log)
            now = _utc_now()

            if message != "" or raw_payload not in (None, '""'):
                next_order = connection.execute(
                    "SELECT COALESCE(MAX(entry_order), 0) + 1 AS next_order FROM install_stage_logs WHERE stage_id = ?",
                    (stage_row["id"],),
                ).fetchone()["next_order"]
                connection.execute(
                    "INSERT INTO install_stage_logs (stage_id, entry_order, level, message, raw_payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (stage_row["id"], next_order, level, message, raw_payload, now),
                )

                overflow_rows = connection.execute(
                    "SELECT id FROM install_stage_logs WHERE stage_id = ? ORDER BY entry_order DESC, id DESC LIMIT -1 OFFSET ?",
                    (stage_row["id"], MAX_SUB_LOGS),
                ).fetchall()
                if overflow_rows:
                    connection.executemany(
                        "DELETE FROM install_stage_logs WHERE id = ?",
                        [(row["id"],) for row in overflow_rows],
                    )

            connection.execute(
                "UPDATE install_tasks SET updated_at = ? WHERE tracking_id = ?",
                (now, tracking_id),
            )
            connection.commit()

        set_tracking_context(tracking_id=tracking_id, stage=stage_name)
        logger.install(message or f"Stage entered: {stage_name}")
        set_tracking_context()

    def update_task_status(self, tracking_id: str, status: int, error: str | None = None) -> None:
        with self._lock, self._db_connect() as connection:
            connection.execute(
                "UPDATE install_tasks SET status = ?, error = ?, updated_at = ? WHERE tracking_id = ?",
                (status, error, _utc_now(), tracking_id),
            )
            connection.commit()

    def delete_task(self, tracking_id: str) -> None:
        with self._lock, self._db_connect() as connection:
            connection.execute("DELETE FROM install_tasks WHERE tracking_id = ?", (tracking_id,))
            connection.commit()

    def delete_tasks_by_app_id(self, app_id: str, statuses: tuple[int, ...] | None = None) -> None:
        with self._lock, self._db_connect() as connection:
            if statuses:
                placeholders = ", ".join("?" for _ in statuses)
                connection.execute(
                    f"DELETE FROM install_tasks WHERE app_id = ? AND status IN ({placeholders})",
                    (app_id, *statuses),
                )
            else:
                connection.execute("DELETE FROM install_tasks WHERE app_id = ?", (app_id,))
            connection.commit()

    def has_task(self, tracking_id: str, statuses: tuple[int, ...] | None = None) -> bool:
        return self.get_task(tracking_id, statuses=statuses) is not None

    def get_task(self, tracking_id: str, statuses: tuple[int, ...] | None = None) -> dict[str, Any] | None:
        with self._lock, self._db_connect() as connection:
            query = "SELECT * FROM install_tasks WHERE tracking_id = ?"
            params: list[Any] = [tracking_id]
            if statuses:
                placeholders = ", ".join("?" for _ in statuses)
                query += f" AND status IN ({placeholders})"
                params.extend(statuses)
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            return self._task_row_to_dict(connection, row)

    def list_tasks(self, statuses: tuple[int, ...]) -> list[tuple[str, dict[str, Any]]]:
        with self._lock, self._db_connect() as connection:
            placeholders = ", ".join("?" for _ in statuses)
            rows = connection.execute(
                f"SELECT * FROM install_tasks WHERE status IN ({placeholders}) ORDER BY created_at ASC",
                statuses,
            ).fetchall()
            return [(row["tracking_id"], self._task_row_to_dict(connection, row)) for row in rows]

    def upsert_task_from_payload(self, tracking_id: str, payload: dict[str, Any]) -> None:
        self.create_task(
            app_id=payload.get("app_id", ""),
            app_name=payload.get("app_name"),
            tracking_id=tracking_id,
            reserved_ports=payload.get("reserved_ports") or [],
            status=int(payload.get("status", 3)),
            app_official=bool(payload.get("app_official", True)),
            error=payload.get("error"),
            logs=payload.get("logs") or [],
        )

    def _task_row_to_dict(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        stages = connection.execute(
            "SELECT id, stage_name, stage_order FROM install_stages WHERE tracking_id = ? ORDER BY stage_order ASC, id ASC",
            (row["tracking_id"],),
        ).fetchall()
        grouped_logs: list[dict[str, Any]] = []
        for stage_row in stages:
            log_rows = connection.execute(
                "SELECT message, raw_payload, level, created_at FROM install_stage_logs WHERE stage_id = ? ORDER BY entry_order ASC, id ASC",
                (stage_row["id"],),
            ).fetchall()
            grouped_logs.append(
                {
                    "title": stage_row["stage_name"],
                    "sub_logs": [self._decode_raw_payload(log_row) for log_row in log_rows],
                }
            )

        try:
            reserved_ports = set(json.loads(row["reserved_ports"] or "[]"))
        except json.JSONDecodeError:
            reserved_ports = set()

        return {
            "app_id": row["app_id"],
            "app_name": row["app_name"],
            "app_official": bool(row["app_official"]),
            "status": row["status"],
            "tracking_id": row["tracking_id"],
            "logs": grouped_logs,
            "reserved_ports": reserved_ports,
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class InstallStateCollection:
    def __init__(self, store: InstallStateStore, statuses: tuple[int, ...]):
        self.store = store
        self.statuses = statuses

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return self.store.list_tasks(self.statuses)

    def values(self) -> list[dict[str, Any]]:
        return [item for _, item in self.items()]

    def get(self, tracking_id: str, default: Any = None) -> Any:
        item = self.store.get_task(tracking_id, statuses=self.statuses)
        return default if item is None else item

    def pop(self, tracking_id: str, default: Any = None) -> Any:
        item = self.get(tracking_id)
        if item is None:
            return default
        self.store.delete_task(tracking_id)
        return item

    def __contains__(self, tracking_id: str) -> bool:
        return self.store.has_task(tracking_id, statuses=self.statuses)

    def __getitem__(self, tracking_id: str) -> dict[str, Any]:
        item = self.get(tracking_id)
        if item is None:
            raise KeyError(tracking_id)
        return item

    def __setitem__(self, tracking_id: str, payload: dict[str, Any]) -> None:
        self.store.upsert_task_from_payload(tracking_id, payload)

    def __iter__(self):
        for key, _ in self.items():
            yield key

    def __len__(self) -> int:
        return len(self.items())


_install_state_store = InstallStateStore()
appInstalling = InstallStateCollection(_install_state_store, (3,))
appInstallingError = InstallStateCollection(_install_state_store, (4,))


def configure_install_state_store(data_dir: str | None = None) -> None:
    _install_state_store.reconfigure(data_dir)


def start_app_installation(app_id, app_name, app_uuid=None, reserved_ports=None):
    return _install_state_store.create_task(app_id, app_name, tracking_id=app_uuid, reserved_ports=reserved_ports, status=3)


def add_installing_logs(app_uuid, stage, log):
    _install_state_store.append_log(app_uuid, stage, log)


def remove_installation_logs(app_uuid):
    return None


def modify_app_information(app_uuid, error):
    _install_state_store.update_task_status(app_uuid, status=4, error=error)
    set_tracking_context(tracking_id=app_uuid, stage="error")
    logger.error(error)
    set_tracking_context()


def remove_app_installation(app_uuid):
    _install_state_store.delete_task(app_uuid)


def remove_app_from_errors(app_uuid):
    if app_uuid in appInstallingError:
        _install_state_store.delete_task(app_uuid)


def remove_app_from_errors_by_app_id(app_id):
    _install_state_store.delete_tasks_by_app_id(app_id, statuses=(4,))
