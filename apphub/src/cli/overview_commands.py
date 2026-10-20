from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import run_cli_action


@click.group(name="overview")
def overview_group():
    """Inspect platform overview, edition quota, and readiness."""


def _render_overview_status_text(payload: dict[str, Any]) -> str:
    product = payload.get("product") or {}
    host = payload.get("host") or {}
    apps = payload.get("apps") or {}
    runtime = payload.get("host_runtime") or payload.get("runtime") or {}
    services = payload.get("services") or {}
    lines = [
        f"Product: {product.get('edition_name') or product.get('edition_key') or '-'} v{product.get('version') or '-'}",
        f"Host: {host.get('hostname') or '-'} ({host.get('os_name') or '-'}, {host.get('architecture') or '-'})",
        f"Apps: installed={apps.get('installed_count')} active={apps.get('active_count')} inactive={apps.get('inactive_count')} installing={apps.get('installing_count')} error={apps.get('error_count')}",
        f"Resources: cpu={runtime.get('cpu_percent')}% mem={runtime.get('memory_percent')}% disk={runtime.get('disk_percent')}% health={runtime.get('health_state')}",
        f"Services: total={services.get('total_count')} healthy={services.get('healthy_count')} degraded={services.get('degraded_count')} unavailable={services.get('unavailable_count')}",
    ]
    return "\n".join(lines)


@overview_group.command(name="status")
@click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Locale for catalog metadata.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def overview_status(locale: str, as_json: bool) -> None:
    """Collect platform overview metrics, app counts, and service summaries."""
    def action() -> dict[str, Any]:
        from src.services.overview_service import OverviewService

        response = OverviewService().collect_overview(locale=locale.lower())
        return response.model_dump()

    run_cli_action(action, as_json=as_json, text_renderer=_render_overview_status_text)


@overview_group.command(name="edition")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def overview_edition(as_json: bool) -> None:
    """Inspect product edition, version, and application quota."""
    def action() -> dict[str, Any]:
        from src.services.product_metadata import read_product_metadata

        return read_product_metadata(readonly=True)

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Edition: {payload.get('edition_name') or payload.get('edition_key')} "
            f"(key={payload.get('edition_key')}, version={payload.get('version')}, max_apps={payload.get('max_apps')})"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@overview_group.command(name="readiness")
@click.option("--setup", "check_setup", is_flag=True, help="Include setup and marketplace bootstrap readiness checks.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def overview_readiness(check_setup: bool, as_json: bool) -> None:
    """Check whether platform databases, credentials, and core services are ready."""
    def action() -> dict[str, Any]:
        from src.services.platform_readiness import PlatformReadinessService

        service = PlatformReadinessService()
        ready, pending = service.check_setup() if check_setup else service.check()
        return {
            "ready": bool(ready),
            "pending": list(pending),
            "scope": "setup" if check_setup else "platform",
        }

    def render_text(payload: dict[str, Any]) -> str:
        if payload.get("ready"):
            return f"Platform readiness ({payload.get('scope')}): READY"
        pending = ", ".join(payload.get("pending") or []) or "unknown"
        return f"Platform readiness ({payload.get('scope')}): PENDING ({pending})"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
