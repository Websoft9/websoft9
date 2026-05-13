import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.core.exception import CustomException
from src.schemas.runtimeLogs import RuntimeLogEntry, RuntimeLogsQuery, RuntimeLogsSourceSummary
from src.services.product_auth import ProductAuthService
from src.utils.runtime_logging import PLATFORM_RUNTIME_LOG_PATH, normalize_runtime_level


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

        threshold = query.threshold()
        if threshold is not None:
            entries = [entry for entry in entries if self._within_threshold(entry, threshold)]

        if query.level:
            entries = [entry for entry in entries if entry.level == query.level]

        if query.keyword:
            keyword = query.keyword.lower()
            entries = [entry for entry in entries if keyword in entry.raw.lower() or keyword in entry.message.lower()]

        if len(entries) > query.limit:
            entries = entries[-query.limit:]

        return entries

    def _read_entries(self, limit: int) -> list[RuntimeLogEntry]:
        if not self.log_path.exists():
            raise CustomException(503, "Runtime Logs Unavailable", f"Platform runtime log source {self.log_path} is not available")

        tail = max(limit * 10, 400)
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = deque((line.rstrip("\n") for line in handle if line.strip()), maxlen=tail)
        except OSError as exc:
            raise CustomException(503, "Runtime Logs Unavailable", f"Failed to read platform runtime logs: {exc}")

        entries: list[RuntimeLogEntry] = []
        for line in lines:
            entry = self._parse_line(line)
            if entry is not None:
                entries.append(entry)
        return entries

    def _parse_line(self, raw_line: str) -> Optional[RuntimeLogEntry]:
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

        return RuntimeLogEntry(timestamp=timestamp, level=normalize_runtime_level(str(payload.get("level") or "info")), message=message, raw=raw_line)

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