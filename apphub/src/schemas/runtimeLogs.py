from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


ALLOWED_LOG_LEVELS = {"error", "warning", "info"}
ALLOWED_TIME_RANGES = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


def _normalize_keyword(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_level(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in ALLOWED_LOG_LEVELS:
        raise ValueError("Level must be one of: error, warning, info")
    return normalized


def _normalize_time_range(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized not in ALLOWED_TIME_RANGES:
        raise ValueError("time_range must be one of: 15m, 1h, 6h, 24h, 7d")
    return normalized


class RuntimeLogEntry(BaseModel):
    timestamp: Optional[str] = None
    level: str = "info"
    source: str = "runtime-console"
    message: str
    raw: str


class RuntimeLogsQuery(BaseModel):
    level: Optional[str] = None
    keyword: Optional[str] = None
    time_range: Optional[str] = None
    limit: int = Field(default=200, ge=1, le=20000)

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_level(value)

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_keyword(value)

    @field_validator("time_range", mode="before")
    @classmethod
    def normalize_time_range(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_time_range(value)

    def threshold(self, now: Optional[datetime] = None) -> Optional[datetime]:
        if not self.time_range:
            return None
        current = now or datetime.now(timezone.utc)
        return current - ALLOWED_TIME_RANGES[self.time_range]


class RuntimeLogsSourceSummary(BaseModel):
    key: str = "runtime-console"
    label: str = "Runtime Console"
    description: str


class RuntimeLogsResponse(BaseModel):
    source: str = "runtime-console"
    level: Optional[str] = None
    keyword: Optional[str] = None
    time_range: Optional[str] = None
    limit: int
    entries: list[RuntimeLogEntry]


class RuntimeLogsSourcesResponse(BaseModel):
    sources: list[RuntimeLogsSourceSummary]