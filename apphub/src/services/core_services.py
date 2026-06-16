import os
import re
import subprocess
from hashlib import sha1
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
NGINX_ACCESS_LOG_PATTERN = re.compile(
    r'^(?P<client>\S+)\s+-\s+-\s+\[(?P<ts>[^\]]+)\]\s+"(?P<request>[^"]+)"\s+(?P<status>\d{3})\s+(?P<bytes>\d+|-)(?:\s+"(?P<referrer>[^"]*)"\s+"(?P<agent>[^"]*)")?$'
)
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
    log_paths: Sequence[Path] = field(default_factory=tuple)
    markers: Sequence[Path] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealthProbeResult:
    ok: bool
    detail: Optional[str] = None


@dataclass
class ServiceLogFileCursor:
    path: Path
    device: int
    inode: int
    position: int


@dataclass
class ServiceLogsStreamCursor:
    service_key: str
    query: ServiceLogsQuery
    entries: list[ServiceLogEntry] = field(default_factory=list)
    unavailable_reason: Optional[str] = None
    file_cursors: dict[str, ServiceLogFileCursor] = field(default_factory=dict)


@dataclass
class ServiceLogsStreamDelta:
    entries: list[ServiceLogEntry] = field(default_factory=list)
    snapshot: Optional[ServiceLogsResponse] = None


DEFAULT_SERVICE_DEFINITIONS = (
    ServiceDefinition(
        key="platform-gateway",
        label="Platform Gateway",
        description="Websoft9 entry gateway service",
        supervisor_program="platform-gateway",
        health_url=os.getenv("WEBSOFT9_PLATFORM_GATEWAY_HEALTH_URL", "http://127.0.0.1:9000/w9gateway/healthz"),
        health_verify_tls=False,
        log_root=Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")),
        log_paths=(
            Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")) / "platform-gateway-access.log",
            Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")) / "platform-gateway-error.log",
        ),
    ),
    ServiceDefinition(
        key="apphub-api",
        label="AppHub",
        description="Websoft9 API and orchestration service",
        supervisor_program="apphub-api",
        health_url=os.getenv("WEBSOFT9_APPHUB_HEALTH_URL", "http://127.0.0.1:8080/api/healthz"),
        log_root=Path("/websoft9/apphub/logs"),
    ),
    ServiceDefinition(
        key="gitea",
        label="Gitea",
        description="Git repository service",
        supervisor_program="gitea",
        health_url=os.getenv("WEBSOFT9_GITEA_HEALTH_URL", "http://127.0.0.1:3000/"),
        workspace_route="repository",
        integration_key="gitea",
        log_root=Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")) / "gitea",
        markers=(Path(os.getenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", "/data/gitea/credential")),),
    ),
    ServiceDefinition(
        key="portainer",
        label="Portainer",
        description="Container management service",
        supervisor_program="portainer",
        health_url=os.getenv("WEBSOFT9_PORTAINER_HEALTH_URL", "http://127.0.0.1:9004/api/system/status"),
        health_verify_tls=True,
        workspace_route="containers",
        integration_key="portainer",
        log_root=Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")) / "portainer",
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
        log_root=Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", "/data/logs")) / "nginx-proxy-manager",
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
        entries = self._filter_log_entries(entries, query)
        return self._build_service_logs_payload(definition, query, entries, unavailable_reason)

    def open_service_logs_stream(self, session_token: Optional[str], service_key: str, query: ServiceLogsQuery) -> tuple[ServiceLogsResponse, ServiceLogsStreamCursor]:
        response = self.get_service_logs(session_token, service_key, query)
        definition = self._get_definition(service_key)
        cursor = ServiceLogsStreamCursor(
            service_key=definition.key,
            query=query.model_copy(deep=True),
            entries=list(response.entries),
            unavailable_reason=response.unavailable_reason,
            file_cursors=self._capture_log_file_cursors(definition),
        )
        return response, cursor

    def poll_service_logs_stream(self, session_token: Optional[str], cursor: ServiceLogsStreamCursor) -> ServiceLogsStreamDelta:
        self.auth_service._require_authenticated_operator(session_token)
        definition = self._get_definition(cursor.service_key)
        files = self._recent_log_files(definition.log_root, definition.log_paths)
        unavailable_reason = "Service raw logs are not currently available"

        if not files:
            if cursor.unavailable_reason == unavailable_reason and not cursor.entries:
                cursor.file_cursors = {}
                return ServiceLogsStreamDelta()
            cursor.entries = []
            cursor.unavailable_reason = unavailable_reason
            cursor.file_cursors = {}
            return ServiceLogsStreamDelta(snapshot=self._build_service_logs_payload(definition, cursor.query, [], unavailable_reason))

        current_file_keys = {str(path) for path in files}
        previous_file_keys = set(cursor.file_cursors)
        if previous_file_keys != current_file_keys:
            return self._reset_service_logs_stream(session_token, definition, cursor)

        incremental_entries: list[ServiceLogEntry] = []
        next_file_cursors: dict[str, ServiceLogFileCursor] = {}

        for path in files:
            file_key = str(path)
            previous = cursor.file_cursors.get(file_key)
            if previous is None:
                return self._reset_service_logs_stream(session_token, definition, cursor)

            try:
                stat = path.stat()
            except OSError:
                return self._reset_service_logs_stream(session_token, definition, cursor)

            if stat.st_ino != previous.inode or stat.st_dev != previous.device or stat.st_size < previous.position:
                return self._reset_service_logs_stream(session_token, definition, cursor)

            try:
                file_entries, position = self._read_incremental_log_entries(path, previous.position)
            except OSError:
                return self._reset_service_logs_stream(session_token, definition, cursor)

            incremental_entries.extend(file_entries)
            next_file_cursors[file_key] = ServiceLogFileCursor(path=path, device=stat.st_dev, inode=stat.st_ino, position=position)

        filtered_new_entries = self._filter_log_entries(incremental_entries, cursor.query)
        next_entries = [*cursor.entries, *filtered_new_entries]
        removed_entries = False

        if cursor.query.time_range != "all":
            cutoff = self._now_provider().astimezone(timezone.utc) - TIME_RANGE_DELTAS[cursor.query.time_range]
            trimmed_entries = [entry for entry in next_entries if self._entry_at_or_after(entry, cutoff)]
            removed_entries = len(trimmed_entries) != len(next_entries)
            next_entries = trimmed_entries

        if len(next_entries) > cursor.query.limit:
            next_entries = next_entries[-cursor.query.limit:]

        cursor.file_cursors = next_file_cursors
        cursor.unavailable_reason = None

        if removed_entries:
            cursor.entries = next_entries
            return ServiceLogsStreamDelta(snapshot=self._build_service_logs_payload(definition, cursor.query, next_entries, None))

        if filtered_new_entries:
            cursor.entries = next_entries
            return ServiceLogsStreamDelta(entries=filtered_new_entries)

        cursor.entries = next_entries
        return ServiceLogsStreamDelta()

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

        logs_available = self._has_log_files(definition.log_root, definition.log_paths)
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
        if not definition.log_root.exists() and not definition.log_paths:
            return [], "Service raw logs are not currently available"

        files = self._recent_log_files(definition.log_root, definition.log_paths)
        if not files:
            return [], "Service raw logs are not currently available"

        lines: deque[tuple[str, str, str]] = deque(maxlen=max(limit * 10, 400))
        for path in files:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    while True:
                        offset = handle.tell()
                        line = handle.readline()
                        if not line:
                            break
                        stripped = self._sanitize_log_line(line)
                        if stripped:
                            lines.append((path.name, stripped, f"{path.name}:{offset}"))
            except OSError:
                continue

        entries = [self._parse_log_line(source, raw_line, fingerprint) for source, raw_line, fingerprint in lines]
        return [entry for entry in entries if entry is not None], None

    def _read_incremental_log_entries(self, path: Path, start_position: int) -> tuple[list[ServiceLogEntry], int]:
        entries: list[ServiceLogEntry] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(start_position)
            while True:
                offset = handle.tell()
                line = handle.readline()
                if not line:
                    break
                stripped = self._sanitize_log_line(line)
                if not stripped:
                    continue
                entry = self._parse_log_line(path.name, stripped, f"{path.name}:{offset}")
                if entry is not None:
                    entries.append(entry)
            position = handle.tell()
        return entries, position

    def _capture_log_file_cursors(self, definition: ServiceDefinition) -> dict[str, ServiceLogFileCursor]:
        files = self._recent_log_files(definition.log_root, definition.log_paths)
        cursors: dict[str, ServiceLogFileCursor] = {}
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            cursors[str(path)] = ServiceLogFileCursor(path=path, device=stat.st_dev, inode=stat.st_ino, position=stat.st_size)
        return cursors

    def _reset_service_logs_stream(self, session_token: Optional[str], definition: ServiceDefinition, cursor: ServiceLogsStreamCursor) -> ServiceLogsStreamDelta:
        response = self.get_service_logs(session_token, definition.key, cursor.query)
        cursor.entries = list(response.entries)
        cursor.unavailable_reason = response.unavailable_reason
        cursor.file_cursors = self._capture_log_file_cursors(definition)
        return ServiceLogsStreamDelta(snapshot=response)

    def _has_log_files(self, log_root: Path, log_paths: Sequence[Path]) -> bool:
        if any(self._is_supported_log_file(path) for path in log_paths):
            return True
        if not log_root.exists():
            return False
        for _root, _dirs, files in os.walk(log_root):
            if any(self._is_supported_log_file(Path(_root) / file_name) for file_name in files):
                return True
        return False

    def _recent_log_files(self, log_root: Path, log_paths: Sequence[Path]) -> list[Path]:
        explicit_paths = [path for path in log_paths if self._is_supported_log_file(path)]
        if explicit_paths:
            return sorted(explicit_paths, key=lambda path: path.stat().st_mtime)

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

    def _parse_log_line(self, source: str, raw_line: str, fingerprint: str) -> Optional[ServiceLogEntry]:
        raw = raw_line.strip()
        if not raw:
            return None

        nginx_access_match = NGINX_ACCESS_LOG_PATTERN.match(raw)
        if nginx_access_match:
            request = nginx_access_match.group("request").strip()
            status = nginx_access_match.group("status").strip()
            message = f'{request} | status={status}'
            return self._build_log_entry(source, fingerprint, raw, self._normalize_timestamp(nginx_access_match.group("ts")), "INF", message)

        portainer_match = PORTAINER_LOG_PATTERN.match(raw)
        if portainer_match:
            return self._build_log_entry(
                source,
                fingerprint,
                raw,
                self._normalize_timestamp(portainer_match.group("ts")),
                portainer_match.group("level"),
                portainer_match.group("message").strip(),
            )

        slash_match = SLASH_TIMESTAMP_PATTERN.match(raw)
        if slash_match:
            level, message = self._extract_message_level(slash_match.group("message").strip())
            return self._build_log_entry(source, fingerprint, raw, self._normalize_timestamp(slash_match.group("ts")), level or self._infer_default_level(message), message)

        match = ISO_PREFIX_PATTERN.match(raw)
        if match:
            timestamp = self._normalize_timestamp(match.group("ts"))
            level, message = self._extract_message_level(match.group("message").strip())
            return self._build_log_entry(source, fingerprint, raw, timestamp, level or self._infer_default_level(message), message)
        level, message = self._extract_message_level(raw)
        return self._build_log_entry(source, fingerprint, raw, None, level or self._infer_default_level(message), message)

    def _build_log_entry(self, source: str, fingerprint: str, raw: str, timestamp: Optional[str], level: Optional[str], message: str) -> ServiceLogEntry:
        entry_id = sha1("\x1f".join((source, fingerprint, timestamp or "", level or "", raw)).encode("utf-8")).hexdigest()
        return ServiceLogEntry(id=entry_id, timestamp=timestamp, level=level, source=source or None, message=message, raw=raw)

    def _filter_log_entries(self, entries: list[ServiceLogEntry], query: ServiceLogsQuery) -> list[ServiceLogEntry]:
        filtered_entries = entries
        if query.keyword:
            keyword = query.keyword.lower()
            filtered_entries = [entry for entry in filtered_entries if keyword in entry.raw.lower() or keyword in entry.message.lower()]
        if query.level:
            allowed_levels = QUERY_LEVEL_TO_ENTRY_LEVELS[query.level]
            filtered_entries = [entry for entry in filtered_entries if entry.level in allowed_levels]
        if query.time_range != "all":
            cutoff = self._now_provider().astimezone(timezone.utc) - TIME_RANGE_DELTAS[query.time_range]
            filtered_entries = [entry for entry in filtered_entries if self._entry_at_or_after(entry, cutoff)]
        if len(filtered_entries) > query.limit:
            filtered_entries = filtered_entries[-query.limit:]
        return filtered_entries

    def _build_service_logs_payload(
        self,
        definition: ServiceDefinition,
        query: ServiceLogsQuery,
        entries: list[ServiceLogEntry],
        unavailable_reason: Optional[str],
    ) -> ServiceLogsResponse:
        cursor = entries[-1].id if entries else None
        return ServiceLogsResponse(
            service=definition.key,
            available=unavailable_reason is None,
            keyword=query.keyword,
            level=query.level,
            time_range=query.time_range,
            limit=query.limit,
            entries=entries,
            cursor=cursor,
            unavailable_reason=unavailable_reason,
        )

    def _normalize_timestamp(self, value: str) -> Optional[str]:
        candidate = value.strip()
        for pattern in ("%Y/%m/%d %I:%M%p", "%Y/%m/%d %I:%M:%S%p", "%Y/%m/%d %H:%M:%S", "%d/%b/%Y:%H:%M:%S %z"):
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

    def _infer_default_level(self, message: str) -> str:
        normalized = message.strip().lower()
        if not normalized:
            return "INF"
        if "fatal" in normalized or "panic" in normalized:
            return "FTL"
        if "error" in normalized or "failed" in normalized or "exception" in normalized:
            return "ERR"
        if "warn" in normalized:
            return "WRN"
        return "INF"

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