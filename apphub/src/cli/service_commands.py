from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import CLIError, MAX_TEXT_BUDGET_BYTES, mask_sensitive_text, run_cli_action, truncate_utf8_text


SUPPORTED_SERVICES = ["platform-gateway", "apphub-api", "gitea", "portainer", "nginx-proxy-manager"]


@click.group(name="service")
def service_group():
    """Inspect Websoft9 core platform services and their logs.

    Application containers are managed with app or docker container commands.
    """


def _bound_log_entries(raw_entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    bounded: list[dict[str, Any]] = []
    used_bytes = 0
    truncated = False
    for entry in reversed(raw_entries):
        msg = mask_sensitive_text(str(entry.get("message") or ""))
        encoded = msg.encode("utf-8", errors="replace")
        if used_bytes + len(encoded) > MAX_TEXT_BUDGET_BYTES:
            remaining = MAX_TEXT_BUDGET_BYTES - used_bytes
            if remaining > 0 and not bounded:
                clipped, _ = truncate_utf8_text(msg, remaining, keep_tail=True)
                copied = dict(entry)
                copied["message"] = clipped
                bounded.append(copied)
            truncated = True
            break
        copied = dict(entry)
        copied["message"] = msg
        bounded.append(copied)
        used_bytes += len(encoded)
    bounded.reverse()
    return bounded, truncated


@service_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_services_command(as_json: bool) -> None:
    """List core Websoft9 control-plane services and health indicators."""
    def action() -> dict[str, Any]:
        from src.services.core_services import CoreServicesService

        summaries = CoreServicesService().collect_services()
        services = [
            {
                "key": item.key,
                "label": item.label,
                "runtime_state": item.runtime_state,
                "runtime_detail": item.runtime_detail,
                "health_state": item.health_state,
                "updated_at": item.updated_at,
                "logs_available": bool(item.logs_available),
                "indicators": [ind.model_dump(exclude_none=True) for ind in (item.indicators or [])],
            }
            for item in summaries
        ]
        warnings: list[str] = []
        if services and all(item.get("runtime_state") == "unavailable" for item in services):
            warnings.append("Supervisor runtime status was unavailable for all platform services.")
        return {
            "services": services,
            "warnings": warnings,
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("services") or []
        lines = [f"Core Services ({len(items)}):"]
        for item in items:
            lines.append(
                f"- {item.get('key')} ({item.get('label')}): runtime={item.get('runtime_state')} "
                f"health={item.get('health_state')} logs_available={item.get('logs_available')}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@service_group.command(name="logs")
@click.argument("service_key", type=click.Choice(SUPPORTED_SERVICES, case_sensitive=False))
@click.option("--limit", type=click.IntRange(min=1, max=1000), default=200, show_default=True, help="Maximum log entries to return.")
@click.option(
    "--level",
    type=click.Choice(["all", "info", "warning", "error", "fatal"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter by log severity level.",
)
@click.option(
    "--time-range",
    "time_range",
    type=click.Choice(["all", "15m", "1h", "6h", "24h", "7d"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter entries by age.",
)
@click.option("--keyword", help="Case-insensitive substring filter.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def service_logs_command(
    service_key: str,
    limit: int,
    level: str,
    time_range: str,
    keyword: str | None,
    as_json: bool,
) -> None:
    """Read filtered logs for a core platform service."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.schemas.coreServices import ServiceLogsQuery
        from src.services.core_services import CoreServicesService

        query = ServiceLogsQuery(
            keyword=keyword,
            level=None if level.lower() == "all" else level.lower(),
            time_range=time_range.lower(),
            limit=limit,
        )
        response = CoreServicesService().collect_service_logs(service_key.lower(), query)
        if not response.available:
            raise CLIError(
                "LOGS_UNAVAILABLE",
                response.unavailable_reason or f"Logs for service '{service_key}' are unavailable",
                details={"service": service_key.lower()},
            )

        raw_entries = [
            {
                "id": entry.id,
                "timestamp": entry.timestamp,
                "level": entry.level,
                "source": entry.source,
                "message": entry.message,
            }
            for entry in (response.entries or [])
        ]
        entries, truncated = _bound_log_entries(raw_entries)
        warnings = ["Service log output exceeded 64 KiB text budget and was truncated."] if truncated else []
        return (
            {
                "source": response.service,
                "entries": entries,
                "warnings": warnings,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        entries = payload.get("entries") or []
        if not entries:
            return f"No log entries matched for service '{payload.get('source')}'."
        return "\n".join(
            f"{entry.get('timestamp') or '-'} [{entry.get('level') or 'info'}] ({entry.get('source') or '-'}) {entry.get('message')}"
            for entry in entries
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@service_group.command(name="runtime-logs")
@click.option("--limit", type=click.IntRange(min=1, max=1000), default=200, show_default=True, help="Maximum log entries to return.")
@click.option(
    "--level",
    type=click.Choice(["info", "warning", "error"], case_sensitive=False),
    help="Filter by runtime log level.",
)
@click.option(
    "--time-range",
    "time_range",
    type=click.Choice(["15m", "1h", "6h", "24h", "7d"], case_sensitive=False),
    help="Filter entries by age.",
)
@click.option("--keyword", help="Case-insensitive substring filter.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def runtime_logs_command(
    limit: int,
    level: str | None,
    time_range: str | None,
    keyword: str | None,
    as_json: bool,
) -> None:
    """Read standardized platform runtime logs (excludes apphub-api)."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.core.exception import CustomException
        from src.schemas.runtimeLogs import RuntimeLogsQuery
        from src.services.runtime_logs import RuntimeLogsService

        query = RuntimeLogsQuery(
            level=level.lower() if level else None,
            time_range=time_range.lower() if time_range else None,
            keyword=keyword,
            limit=limit,
        )
        try:
            items = RuntimeLogsService().collect_runtime_logs(query)
        except CustomException as exc:
            raise CLIError("LOGS_UNAVAILABLE", str(exc.details or exc.message), details={"source": "runtime-console"}) from exc

        raw_entries = [
            {
                "id": entry.id,
                "timestamp": entry.timestamp,
                "level": entry.level,
                "source": entry.source,
                "message": entry.message,
            }
            for entry in items
        ]
        entries, truncated = _bound_log_entries(raw_entries)
        warnings = ["Runtime log output exceeded 64 KiB text budget and was truncated."] if truncated else []
        return (
            {
                "source": "runtime-console",
                "entries": entries,
                "warnings": warnings,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        entries = payload.get("entries") or []
        if not entries:
            return "No platform runtime log entries matched."
        return "\n".join(
            f"{entry.get('timestamp') or '-'} [{entry.get('level') or 'info'}] ({entry.get('source') or '-'}) {entry.get('message')}"
            for entry in entries
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
