import os
import re
import subprocess
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import requests

from src.core.exception import CustomException
from src.schemas.coreServices import CoreServiceSummary, ISO_PREFIX_PATTERN, ServiceIndicator, ServiceLogEntry, ServiceLogsQuery, ServiceLogsResponse
from src.services.product_auth import ProductAuthService


ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
PORTAINER_LOG_PATTERN = re.compile(
    r"^(?P<ts>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}(?::\d{2})?(?:AM|PM)?)\s+"
    r"(?P<level>[A-Z]{3})\s+"
    r"(?P<source>\S+)\s+>\s*"
    r"(?P<message>.+)$"
)
SLASH_TIMESTAMP_PATTERN = re.compile(r"^(?P<ts>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<message>.+)$")
BRACKET_LEVEL_PATTERN = re.compile(r"^(?:HTTPRequest\s+)?\[(?P<level>[IWEF])\]\s+(?P<message>.+)$")
NGINX_LEVEL_PATTERN = re.compile(r"^\[(?P<level>error|warn|warning|notice|info)\]\s+(?P<message>.+)$", re.IGNORECASE)
LOG_LEVEL_ALIASES = {
    "I": "INF",
    "W": "WRN",
    "E": "ERR",
    "F": "FTL",
    "INFO": "INF",
    "NOTICE": "INF",
    "WARN": "WRN",
    "WARNING": "WRN",
    "ERROR": "ERR",
    "FATAL": "FTL",
}
QUERY_LEVEL_TO_ENTRY_LEVELS = {
    "info": {"INF"},
    "warning": {"WRN"},
    "error": {"ERR"},
    "fatal": {"FTL"},
}
TIME_RANGE_DELTAS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    label: str
    description: str
    supervisor_program: Optional[str]
    health_url: str
    health_verify_tls: bool = True
    workspace_route: Optional[str] = None
    integration_key: Optional[str] = None
    log_root: Path = Path("/")
    markers: Sequence[Path] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealthProbeResult:
    ok: bool
    detail: Optional[str] = None


DEFAULT_SERVICE_DEFINITIONS = (
    ServiceDefinition(
        key="gitea",
        label="Gitea",
        description="Git repository service",
        supervisor_program="gitea",
        health_url=os.getenv("WEBSOFT9_GITEA_HEALTH_URL", "http://127.0.0.1:3000/"),
        workspace_route="repository",
        integration_key="gitea",
        log_root=Path("/var/log/websoft9/gitea"),
        markers=(Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential")),),
    ),
    ServiceDefinition(
        key="portainer",
        label="Portainer",
        description="Container management service",
        supervisor_program="portainer",
        health_url=os.getenv("WEBSOFT9_PORTAINER_HEALTH_URL", "https://127.0.0.1:9443/api/system/status"),
        health_verify_tls=False,
        workspace_route="containers",
        integration_key="portainer",
        log_root=Path("/var/log/websoft9/portainer"),
        markers=(Path(os.getenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", "/data/portainer/credential")),),
    ),
    ServiceDefinition(
        key="nginx-proxy-manager",
        label="Nginx Proxy Manager",
        description="Reverse proxy and certificate service",
        supervisor_program=None,
        health_url=os.getenv("WEBSOFT9_NPM_HEALTH_URL", "http://127.0.0.1:81/"),
        workspace_route="gateway",
        integration_key="npm",
        log_root=Path("/var/log/websoft9/nginx-proxy-manager"),
        markers=(
            Path(os.getenv("WEBSOFT9_NPM_CREDENTIAL_PATH", "/data/nginx-proxy-manager/credential.json")),
            Path(os.getenv("WEBSOFT9_NPM_CERT_MARKER", "/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert")),
        ),
    ),
)


class CoreServicesService:
    def __init__(
        self,
        auth_service: Optional[ProductAuthService] = None,
        service_definitions: Optional[Sequence[ServiceDefinition]] = None,
        supervisor_status_loader: Optional[Callable[[], dict[str, str]]] = None,
        health_probe: Optional[Callable[[ServiceDefinition], HealthProbeResult]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.auth_service = auth_service or ProductAuthService()
        self.service_definitions = tuple(service_definitions or DEFAULT_SERVICE_DEFINITIONS)
        self._supervisor_status_loader = supervisor_status_loader or self._load_supervisor_statuses
        self._health_probe = health_probe or self._probe_health
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def list_services(self, session_token: Optional[str]) -> list[CoreServiceSummary]:
        self.auth_service._require_authenticated_operator(session_token)
        statuses = self._safe_load_supervisor_statuses()
        updated_at = self._timestamp_now()

        payload: list[CoreServiceSummary] = []
        for definition in self.service_definitions:
            payload.append(self._build_summary(definition, statuses, updated_at))
        return payload

    def get_service_logs(self, session_token: Optional[str], service_key: str, query: ServiceLogsQuery) -> ServiceLogsResponse:
        self.auth_service._require_authenticated_operator(session_token)
        definition = self._get_definition(service_key)
        entries, unavailable_reason = self._read_service_logs(definition, query.limit)
        if query.keyword:
            keyword = query.keyword.lower()
            entries = [entry for entry in entries if keyword in entry.raw.lower() or keyword in entry.message.lower()]
        if query.level:
            allowed_levels = QUERY_LEVEL_TO_ENTRY_LEVELS[query.level]
            entries = [entry for entry in entries if entry.level in allowed_levels]
        if query.time_range != "all":
            cutoff = self._now_provider().astimezone(timezone.utc) - TIME_RANGE_DELTAS[query.time_range]
            entries = [entry for entry in entries if self._entry_at_or_after(entry, cutoff)]
        if len(entries) > query.limit:
            entries = entries[-query.limit:]
        return ServiceLogsResponse(
            service=definition.key,
            available=unavailable_reason is None,
            keyword=query.keyword,
            level=query.level,
            time_range=query.time_range,
            limit=query.limit,
            entries=entries,
            unavailable_reason=unavailable_reason,
        )

    def _build_summary(self, definition: ServiceDefinition, statuses: dict[str, str], updated_at: str) -> CoreServiceSummary:
        indicators: list[ServiceIndicator] = []
        raw_supervisor_status = statuses.get(definition.supervisor_program or "") if definition.supervisor_program else None

        try:
            health_result = self._health_probe(definition)
            indicators.append(
                ServiceIndicator(
                    key="health-endpoint",
                    status="ok" if health_result.ok else "degraded",
                    value=health_result.detail,
                )
            )
        except Exception as exc:
            health_result = HealthProbeResult(ok=False, detail=str(exc))
            indicators.append(ServiceIndicator(key="health-endpoint", status="error", detail=str(exc)))

        marker_states = [marker.exists() for marker in definition.markers]
        for marker, exists in zip(definition.markers, marker_states):
            indicators.append(
                ServiceIndicator(
                    key="bootstrap-marker",
                    status="ok" if exists else "missing",
                    value=self._describe_marker(marker),
                )
            )

        logs_available = self._has_log_files(definition.log_root)
        indicators.append(
            ServiceIndicator(
                key="log-root",
                status="ok" if logs_available else "missing",
                value="ready" if logs_available else "missing",
            )
        )

        runtime_state, runtime_detail = self._resolve_runtime_state(raw_supervisor_status, health_result)
        health_state = self._resolve_health_state(runtime_state, health_result, marker_states, indicators)

        return CoreServiceSummary(
            key=definition.key,
            label=definition.label,
            description=definition.description,
            runtime_state=runtime_state,
            runtime_detail=runtime_detail,
            health_state=health_state,
            updated_at=updated_at,
            workspace_route=definition.workspace_route,
            integration_key=definition.integration_key,
            logs_available=logs_available,
            runtime_logs_href=f"/logs?keyword={definition.key}",
            indicators=indicators,
        )

    def _resolve_runtime_state(self, raw_supervisor_status: Optional[str], health_result: HealthProbeResult) -> tuple[str, Optional[str]]:
        if raw_supervisor_status:
            normalized = raw_supervisor_status.strip().upper()
            if normalized == "RUNNING":
                return "running", normalized.lower()
            if normalized in {"STARTING", "BACKOFF"}:
                if health_result.ok:
                    return "running", f"{normalized.lower()}-endpoint-responding"
                return "starting", normalized.lower()
            return "stopped", normalized.lower()
        if health_result.ok:
            return "running", "endpoint-responding"
        return "unavailable", health_result.detail

    def _resolve_health_state(
        self,
        runtime_state: str,
        health_result: HealthProbeResult,
        marker_states: list[bool],
        indicators: list[ServiceIndicator],
    ) -> str:
        markers_ok = all(marker_states) if marker_states else True
        indicator_has_error = any(indicator.status == "error" for indicator in indicators)
        if runtime_state in {"stopped", "unavailable"} and not health_result.ok:
            return "unavailable"
        if health_result.ok and markers_ok and not indicator_has_error:
            return "healthy"
        if runtime_state == "running" or health_result.ok:
            return "degraded"
        return "unavailable"

    def _get_definition(self, service_key: str) -> ServiceDefinition:
        normalized = service_key.strip().lower()
        for definition in self.service_definitions:
            if definition.key == normalized:
                return definition
        raise CustomException(404, "Service Not Found", f"Service {service_key} is not supported")

    def _safe_load_supervisor_statuses(self) -> dict[str, str]:
        try:
            return self._supervisor_status_loader()
        except Exception:
            return {}

    def _load_supervisor_statuses(self) -> dict[str, str]:
        supervisor_config = os.getenv("WEBSOFT9_SUPERVISOR_CONFIG", "/etc/supervisor/conf.d/websoft9-platform.conf")
        result = subprocess.run(
            ["supervisorctl", "-c", supervisor_config, "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or result.stdout.strip() or "supervisorctl status failed")

        statuses: dict[str, str] = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            statuses[parts[0].strip()] = parts[1].strip()
        return statuses

    def _probe_health(self, definition: ServiceDefinition) -> HealthProbeResult:
        response = requests.get(definition.health_url, timeout=2, verify=definition.health_verify_tls)
        if response.status_code < 500:
            return HealthProbeResult(ok=True, detail=f"HTTP {response.status_code}")
        return HealthProbeResult(ok=False, detail=f"HTTP {response.status_code}")

    def _read_service_logs(self, definition: ServiceDefinition, limit: int) -> tuple[list[ServiceLogEntry], Optional[str]]:
        if not definition.log_root.exists():
            return [], "Service raw logs are not currently available"

        files = self._recent_log_files(definition.log_root)
        if not files:
            return [], "Service raw logs are not currently available"

        lines: deque[tuple[str, str]] = deque(maxlen=max(limit * 10, 400))
        for path in files:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        stripped = self._sanitize_log_line(line)
                        if stripped:
                            lines.append((path.name, stripped))
            except OSError:
                continue

        entries = [self._parse_log_line(source, raw_line) for source, raw_line in lines]
        return [entry for entry in entries if entry is not None], None

    def _has_log_files(self, log_root: Path) -> bool:
        if not log_root.exists():
            return False
        for _root, _dirs, files in os.walk(log_root):
            if any(self._is_supported_log_file(Path(_root) / file_name) for file_name in files):
                return True
        return False

    def _recent_log_files(self, log_root: Path) -> list[Path]:
        candidates: list[tuple[float, Path]] = []
        for root, _dirs, files in os.walk(log_root):
            for file_name in files:
                path = Path(root) / file_name
                if not self._is_supported_log_file(path):
                    continue
                try:
                    modified_at = path.stat().st_mtime
                except OSError:
                    continue
                candidates.append((modified_at, path))

        candidates.sort(key=lambda item: item[0], reverse=True)
        recent_paths = [path for _modified_at, path in candidates[:8]]
        return sorted(recent_paths, key=lambda path: path.stat().st_mtime)

    def _describe_marker(self, marker: Path) -> str:
        name = marker.name.lower()
        if "credential" in name:
            return "credential"
        if "cert" in name or "certificate" in name:
            return "certificate"
        return marker.name

    def _parse_log_line(self, source: str, raw_line: str) -> Optional[ServiceLogEntry]:
        raw = raw_line.strip()
        if not raw:
            return None

        portainer_match = PORTAINER_LOG_PATTERN.match(raw)
        if portainer_match:
            return ServiceLogEntry(
                timestamp=self._normalize_timestamp(portainer_match.group("ts")),
                level=portainer_match.group("level"),
                source=None,
                message=portainer_match.group("message").strip(),
                raw=raw,
            )

        slash_match = SLASH_TIMESTAMP_PATTERN.match(raw)
        if slash_match:
            level, message = self._extract_message_level(slash_match.group("message").strip())
            return ServiceLogEntry(
                timestamp=self._normalize_timestamp(slash_match.group("ts")),
                level=level,
                source=None,
                message=message,
                raw=raw,
            )

        match = ISO_PREFIX_PATTERN.match(raw)
        if match:
            timestamp = self._normalize_timestamp(match.group("ts"))
            level, message = self._extract_message_level(match.group("message").strip())
            return ServiceLogEntry(timestamp=timestamp, level=level, source=None, message=message, raw=raw)
        level, message = self._extract_message_level(raw)
        return ServiceLogEntry(timestamp=None, level=level, source=None, message=message, raw=raw)

    def _normalize_timestamp(self, value: str) -> Optional[str]:
        candidate = value.strip()
        for pattern in ("%Y/%m/%d %I:%M%p", "%Y/%m/%d %I:%M:%S%p", "%Y/%m/%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(candidate, pattern).replace(tzinfo=timezone.utc)
                return parsed.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue

        candidate = candidate.replace(" ", "T")
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")

    def _is_supported_log_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() != ".gz"

    def _sanitize_log_line(self, line: str) -> str:
        stripped = ANSI_ESCAPE_PATTERN.sub("", line.rstrip("\n"))
        stripped = CONTROL_CHAR_PATTERN.sub("", stripped)
        return stripped.strip()

    def _extract_message_level(self, message: str) -> tuple[Optional[str], str]:
        bracket_match = BRACKET_LEVEL_PATTERN.match(message)
        if bracket_match:
            level = LOG_LEVEL_ALIASES.get(bracket_match.group("level"), bracket_match.group("level"))
            return level, bracket_match.group("message").strip()

        nginx_match = NGINX_LEVEL_PATTERN.match(message)
        if nginx_match:
            level = LOG_LEVEL_ALIASES.get(nginx_match.group("level").upper(), nginx_match.group("level").upper())
            return level, nginx_match.group("message").strip()

        return None, message

    def _entry_at_or_after(self, entry: ServiceLogEntry, cutoff: datetime) -> bool:
        if not entry.timestamp:
            return False
        try:
            parsed = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed >= cutoff

    def _timestamp_now(self) -> str:
        return self._now_provider().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")