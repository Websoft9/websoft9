import json
import os
from hashlib import sha1
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.core.exception import CustomException
from src.schemas.runtimeLogs import RuntimeLogEntry, RuntimeLogsQuery, RuntimeLogsSourceSummary
from src.services.product_auth import ProductAuthService
from src.utils.runtime_logging import PLATFORM_RUNTIME_LOG_PATH, normalize_runtime_level


@dataclass
class RuntimeLogCursor:
    device: int
    inode: int
    position: int


@dataclass
class RuntimeLogsStreamCursor:
    query: RuntimeLogsQuery
    entries: list[RuntimeLogEntry]
    file_cursor: Optional[RuntimeLogCursor]


@dataclass
class RuntimeLogsStreamDelta:
    entries: list[RuntimeLogEntry]
    snapshot: Optional[list[RuntimeLogEntry]] = None


class RuntimeLogsService:
    def __init__(
        self,
        auth_service: Optional[ProductAuthService] = None,
        log_path: Optional[str] = None,
    ):
        self.auth_service = auth_service or ProductAuthService()
        self.log_path = Path(log_path or os.getenv("WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH", PLATFORM_RUNTIME_LOG_PATH))
        self.excluded_components = {"apphub-api"}

    def list_sources(self, session_token: Optional[str]) -> list[RuntimeLogsSourceSummary]:
        self.auth_service._require_authenticated_operator(session_token)
        return [
            RuntimeLogsSourceSummary(
                description="Standardized Websoft9 platform runtime logs collected from the dedicated platform runtime log source.",
            )
        ]

    def get_runtime_logs(self, session_token: Optional[str], query: RuntimeLogsQuery) -> list[RuntimeLogEntry]:
        self.auth_service._require_authenticated_operator(session_token)
        entries = self._read_entries(limit=query.limit)

        return self._filter_entries(entries, query)

    def open_runtime_logs_stream(self, session_token: Optional[str], query: RuntimeLogsQuery) -> tuple[list[RuntimeLogEntry], RuntimeLogsStreamCursor]:
        entries = self.get_runtime_logs(session_token, query)
        return entries, RuntimeLogsStreamCursor(
            query=query.model_copy(deep=True),
            entries=list(entries),
            file_cursor=self._capture_file_cursor(),
        )

    def poll_runtime_logs_stream(self, session_token: Optional[str], cursor: RuntimeLogsStreamCursor) -> RuntimeLogsStreamDelta:
        self.auth_service._require_authenticated_operator(session_token)
        next_cursor = self._capture_file_cursor()
        previous_cursor = cursor.file_cursor

        if previous_cursor is None or next_cursor is None:
            snapshot = self.get_runtime_logs(session_token, cursor.query)
            cursor.entries = list(snapshot)
            cursor.file_cursor = next_cursor
            return RuntimeLogsStreamDelta(entries=[], snapshot=snapshot)

        if next_cursor.inode != previous_cursor.inode or next_cursor.device != previous_cursor.device or next_cursor.position < previous_cursor.position:
            snapshot = self.get_runtime_logs(session_token, cursor.query)
            cursor.entries = list(snapshot)
            cursor.file_cursor = next_cursor
            return RuntimeLogsStreamDelta(entries=[], snapshot=snapshot)

        incremental_entries, position = self._read_incremental_entries(previous_cursor.position)
        next_file_cursor = RuntimeLogCursor(device=next_cursor.device, inode=next_cursor.inode, position=position)
        filtered_new_entries = self._filter_entries(incremental_entries, cursor.query)
        next_entries = [*cursor.entries, *filtered_new_entries]
        removed_entries = False

        threshold = cursor.query.threshold()
        if threshold is not None:
            trimmed_entries = [entry for entry in next_entries if self._within_threshold(entry, threshold)]
            removed_entries = len(trimmed_entries) != len(next_entries)
            next_entries = trimmed_entries

        if len(next_entries) > cursor.query.limit:
            next_entries = next_entries[-cursor.query.limit:]

        cursor.file_cursor = next_file_cursor

        if removed_entries:
            cursor.entries = next_entries
            return RuntimeLogsStreamDelta(entries=[], snapshot=next_entries)

        if filtered_new_entries:
            cursor.entries = next_entries
            return RuntimeLogsStreamDelta(entries=filtered_new_entries, snapshot=None)

        cursor.entries = next_entries
        return RuntimeLogsStreamDelta(entries=[], snapshot=None)

    def _read_entries(self, limit: int) -> list[RuntimeLogEntry]:
        if not self.log_path.exists():
            raise CustomException(503, "Runtime Logs Unavailable", f"Platform runtime log source {self.log_path} is not available")

        tail = max(limit * 10, 400)
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = deque(maxlen=tail)
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    stripped = line.rstrip("\n")
                    if stripped.strip():
                        lines.append((stripped, offset))
        except OSError as exc:
            raise CustomException(503, "Runtime Logs Unavailable", f"Failed to read platform runtime logs: {exc}")

        entries: list[RuntimeLogEntry] = []
        for line, offset in lines:
            entry = self._parse_line(line, f"runtime:{offset}")
            if entry is not None:
                entries.append(entry)
        return entries

    def _read_incremental_entries(self, start_position: int) -> tuple[list[RuntimeLogEntry], int]:
        if not self.log_path.exists():
            raise CustomException(503, "Runtime Logs Unavailable", f"Platform runtime log source {self.log_path} is not available")

        entries: list[RuntimeLogEntry] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                handle.seek(start_position)
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    stripped = line.rstrip("\n")
                    if not stripped.strip():
                        continue
                    entry = self._parse_line(stripped, f"runtime:{offset}")
                    if entry is not None:
                        entries.append(entry)
                position = handle.tell()
        except OSError as exc:
            raise CustomException(503, "Runtime Logs Unavailable", f"Failed to read platform runtime logs: {exc}")
        return entries, position

    def _capture_file_cursor(self) -> Optional[RuntimeLogCursor]:
        if not self.log_path.exists():
            return None
        try:
            stat = self.log_path.stat()
        except OSError:
            return None
        return RuntimeLogCursor(device=stat.st_dev, inode=stat.st_ino, position=stat.st_size)

    def _parse_line(self, raw_line: str, fingerprint: str) -> Optional[RuntimeLogEntry]:
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        if str(payload.get("domain") or "runtime").strip().lower() != "runtime":
            return None

        component = str(payload.get("component") or "").strip().lower()
        if component in self.excluded_components:
            return None

        timestamp = self._normalize_timestamp(payload.get("ts"))
        message = self._compose_message(payload)
        if not message:
            return None

        level = normalize_runtime_level(str(payload.get("level") or "info"))
        source = str(payload.get("component") or "runtime-console").strip() or "runtime-console"
        entry_id = sha1("\x1f".join((fingerprint, timestamp or "", level, source, raw_line)).encode("utf-8")).hexdigest()
        return RuntimeLogEntry(id=entry_id, timestamp=timestamp, level=level, source=source, message=message, raw=raw_line)

    def _filter_entries(self, entries: list[RuntimeLogEntry], query: RuntimeLogsQuery) -> list[RuntimeLogEntry]:
        filtered_entries = entries

        threshold = query.threshold()
        if threshold is not None:
            filtered_entries = [entry for entry in filtered_entries if self._within_threshold(entry, threshold)]

        if query.level:
            filtered_entries = [entry for entry in filtered_entries if entry.level == query.level]

        if query.keyword:
            keyword = query.keyword.lower()
            filtered_entries = [entry for entry in filtered_entries if keyword in entry.raw.lower() or keyword in entry.message.lower()]

        if len(filtered_entries) > query.limit:
            filtered_entries = filtered_entries[-query.limit:]

        return filtered_entries

    def _compose_message(self, payload: dict) -> str:
        message = str(payload.get("message") or "").strip()
        component = str(payload.get("component") or "").strip()
        if not message:
            return ""
        if component and not message.startswith("["):
            return f"[{component}] {message}"
        return message

    def _normalize_timestamp(self, value: object) -> Optional[str]:
        candidate = str(value or "").strip()
        if not candidate:
            return None

        normalized_candidate = candidate.replace(" ", "T")
        if normalized_candidate.endswith("Z"):
            normalized_candidate = normalized_candidate[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized_candidate)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")

    def _within_threshold(self, entry: RuntimeLogEntry, threshold: datetime) -> bool:
        if not entry.timestamp:
            return False
        try:
            parsed = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed >= threshold