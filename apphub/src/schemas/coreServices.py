import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


SUPPORTED_SERVICE_KEYS = {"platform-gateway", "apphub-api", "gitea", "portainer", "nginx-proxy-manager"}
SUPPORTED_LOG_LEVELS = {"info", "warning", "error", "fatal"}
SUPPORTED_LOG_TIME_RANGES = {"all", "15m", "1h", "6h", "24h", "7d"}


def _normalize_keyword(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_service_key(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SUPPORTED_SERVICE_KEYS:
        raise ValueError("service must be one of: platform-gateway, apphub-api, gitea, portainer, nginx-proxy-manager")
    return normalized


class ServiceIndicator(BaseModel):
    key: str
    status: str
    value: Optional[str] = None
    detail: Optional[str] = None


class CoreServiceSummary(BaseModel):
    key: str
    label: str
    description: str
    runtime_state: str
    runtime_detail: Optional[str] = None
    health_state: str
    updated_at: str
    workspace_route: Optional[str] = None
    integration_key: Optional[str] = None
    logs_available: bool = False
    runtime_logs_href: Optional[str] = None
    indicators: list[ServiceIndicator] = Field(default_factory=list)


class CoreServicesInventoryResponse(BaseModel):
    services: list[CoreServiceSummary]


class ServiceLogsQuery(BaseModel):
    keyword: Optional[str] = None
    level: Optional[str] = None
    time_range: str = Field(default="all")
    limit: int = Field(default=200, ge=1, le=20000)

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_keyword(value)

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized == "all":
            return None
        if normalized not in SUPPORTED_LOG_LEVELS:
            raise ValueError("level must be one of: info, warning, error, fatal")
        return normalized

    @field_validator("time_range", mode="before")
    @classmethod
    def normalize_time_range(cls, value: Optional[str]) -> str:
        normalized = str(value or "all").strip().lower() or "all"
        if normalized not in SUPPORTED_LOG_TIME_RANGES:
            raise ValueError("time_range must be one of: all, 15m, 1h, 6h, 24h, 7d")
        return normalized


class ServiceLogEntry(BaseModel):
    timestamp: Optional[str] = None
    level: Optional[str] = None
    source: Optional[str] = None
    message: str
    raw: str


class ServiceLogsResponse(BaseModel):
    service: str
    available: bool = True
    keyword: Optional[str] = None
    level: Optional[str] = None
    time_range: str = "all"
    limit: int
    entries: list[ServiceLogEntry] = Field(default_factory=list)
    unavailable_reason: Optional[str] = None


ISO_PREFIX_PATTERN = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ][0-9:.+-Z]+)\s+(?P<message>.+)$")