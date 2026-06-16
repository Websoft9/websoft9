import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


PLATFORM_RUNTIME_LOG_PATH = os.getenv("WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH", "/data/logs/platform-runtime.log")


def normalize_runtime_level(value: Optional[str]) -> str:
    normalized = str(value or "info").strip().lower()
    if normalized in {"warn", "warning"}:
        return "warning"
    if normalized == "error":
        return "error"
    return "info"


def default_component_for_logger(logger_name: str) -> str:
    normalized = (logger_name or "apphub").strip().lower()
    if normalized.startswith("uvicorn"):
        return "apphub-api"
    if normalized in {"root", "src", "apphub"}:
        return "apphub-api"
    return normalized.replace(".", "-") or "apphub-api"


class PlatformRuntimeFileHandler(logging.FileHandler):
    def __init__(self, filename: str = PLATFORM_RUNTIME_LOG_PATH, mode: str = "a", encoding: Optional[str] = "utf-8", delay: bool = False):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename=filename, mode=mode, encoding=encoding, delay=delay)


class PlatformRuntimeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": normalize_runtime_level(record.levelname),
            "component": getattr(record, "runtime_component", None) or default_component_for_logger(record.name),
            "domain": getattr(record, "runtime_domain", "runtime"),
            "event": getattr(record, "runtime_event", "log"),
            "message": record.getMessage(),
        }

        context = getattr(record, "runtime_context", None)
        if isinstance(context, dict) and context:
            payload["context"] = context

        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))