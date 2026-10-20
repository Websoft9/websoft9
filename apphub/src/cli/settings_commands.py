from __future__ import annotations

import sys
from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


@click.group(name="settings")
def settings_group():
    """Inspect and manage masked platform settings, mirrors, SMTP, and upgrade readiness."""


@settings_group.group(name="mirrors")
def settings_mirrors_group():
    """Inspect, test, refresh, and configure Docker registry accelerators."""


@settings_group.group(name="smtp")
def settings_smtp_group():
    """Inspect, configure, and test platform SMTP email settings."""


@settings_group.group(name="upgrade")
def settings_upgrade_group():
    """Inspect platform upgrade status, check releases, and stage upgrade artifacts."""


@settings_group.command(name="summary")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def settings_summary_command(as_json: bool) -> None:
    """Read masked platform settings summary."""
    def action() -> dict[str, Any]:
        from src.services.settings_manager import SettingsManager

        return SettingsManager().read_summary(readonly=True)

    def render_text(payload: dict[str, Any]) -> str:
        groups = payload.get("groups") or []
        lines = []
        for group in groups:
            lines.append(f"[{group.get('id')}]")
            for item in group.get("items") or []:
                lines.append(f"  {item.get('section')}.{item.get('key')} = {item.get('value')}")
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_mirrors_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_mirrors_command(as_json: bool) -> None:
    """List configured and default Docker registry accelerators."""
    def action() -> dict[str, Any]:
        from src.services.mirror_registry import MirrorRegistry

        registry = MirrorRegistry()
        source = registry.source()
        operator_entries = [entry.masked() for entry in registry.store.list_entries()]
        effective = [acc.url for acc in registry.accelerators(refresh=False)]
        return {
            "source": source,
            "effective_mirrors": effective,
            "operator_entries": operator_entries,
            "default_entries": registry.default_entries(),
        }

    def render_text(payload: dict[str, Any]) -> str:
        effective = payload.get("effective_mirrors") or []
        return f"Mirror source={payload.get('source')} effective={', '.join(effective) if effective else 'none'}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_mirrors_group.command(name="test")
@click.argument("url", required=False)
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def test_mirrors_command(url: str | None, as_json: bool) -> None:
    """Probe reachability and usability of configured or specified Docker mirror(s)."""
    def action() -> dict[str, Any]:
        from src.services.docker_mirror_store import validate_mirror_url
        from src.services.mirror_registry import Accelerator, MirrorRegistry

        registry = MirrorRegistry()
        if url:
            try:
                normalized = validate_mirror_url(url)
            except ValueError as exc:
                raise CLIError("INVALID_ARGUMENT", str(exc), exit_code=2) from exc
            targets = [Accelerator(url=normalized)]
        else:
            targets = registry.accelerators(refresh=False)

        results = [registry.probe(target) for target in targets]
        return {
            "items": results,
            "total": len(results),
            "all_usable": all(bool(item.get("usable")) for item in results) if results else False,
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No Docker mirrors to test."
        return "\n".join(
            f"- {item.get('url')}: usable={item.get('usable')} reachable={item.get('reachable')} reason={item.get('reason')} ({item.get('latency_ms')}ms)"
            for item in items
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_mirrors_group.command(name="refresh")
@click.option("--yes", "-y", is_flag=True, help="Confirm refreshing default mirror list from artifact channel.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def refresh_mirrors_command(yes: bool, as_json: bool) -> None:
    """Refresh the channel's default Docker mirror list and export host-visible list."""
    def action() -> dict[str, Any]:
        from src.services.mirror_registry import MirrorRegistry

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", "Refreshing default Docker mirror list requires --yes confirmation")
            if not click.confirm("Refresh default Docker mirror list from the artifact server?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        registry = MirrorRegistry()
        refreshed = registry.refresh_default_list(force=True)
        registry.export_host_visible_list()
        return {
            "refreshed": bool(refreshed),
            "default_entries": registry.default_entries(),
            "effective_mirrors": [acc.url for acc in registry.accelerators(refresh=False)],
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Default mirror list refreshed={payload.get('refreshed')} entries={', '.join(payload.get('default_entries') or [])}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_mirrors_group.command(name="set")
@click.option("--mirror", "mirrors", multiple=True, help="Accelerator URL to configure in order (repeatable).")
@click.option("--clear", is_flag=True, help="Clear operator-configured mirrors and fall back to defaults.")
@click.option("--yes", "-y", is_flag=True, help="Confirm updating Docker mirror configuration.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def set_mirrors_command(mirrors: tuple[str, ...], clear: bool, yes: bool, as_json: bool) -> None:
    """Configure ordered Docker registry accelerators."""
    def action() -> dict[str, Any]:
        from src.services.docker_mirror_store import validate_mirror_url
        from src.services.mirror_registry import MirrorRegistry

        if clear and mirrors:
            raise CLIError("INVALID_ARGUMENT", "--clear cannot be combined with --mirror", exit_code=2)
        if not clear and not mirrors:
            raise CLIError("INVALID_ARGUMENT", "Provide at least one --mirror URL or --clear", exit_code=2)

        prepared_urls: list[str] = []
        for item in mirrors:
            try:
                prepared_urls.append(validate_mirror_url(item))
            except ValueError as exc:
                raise CLIError("INVALID_ARGUMENT", str(exc), exit_code=2) from exc

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    "Updating Docker mirrors requires --yes confirmation",
                    details={"mirrors": prepared_urls, "clear": clear},
                )
            if not click.confirm(f"Update Docker mirrors to {prepared_urls if not clear else 'default (clear custom entries)'}?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        registry = MirrorRegistry()
        entries = registry.store.replace_entries([{"url": u, "enabled": True} for u in prepared_urls])
        registry.export_host_visible_list()
        return {
            "source": registry.source(),
            "operator_entries": [entry.masked() for entry in entries],
            "effective_mirrors": [acc.url for acc in registry.accelerators(refresh=False)],
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Updated Docker mirrors: source={payload.get('source')} effective={', '.join(payload.get('effective_mirrors') or [])}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_smtp_group.command(name="get")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def get_smtp_command(as_json: bool) -> None:
    """Read masked SMTP configuration."""
    def action() -> dict[str, Any]:
        from src.services.smtp_service import SmtpService

        return SmtpService().get_masked_settings()

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"SMTP: enabled={payload.get('enabled')} host={payload.get('host') or '-'}:{payload.get('port')} "
            f"encryption={payload.get('encryption')} from={payload.get('from_email') or '-'} password_set={payload.get('password_set')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_smtp_group.command(name="set")
@click.option("--enabled/--disabled", default=True, show_default=True, help="Enable or disable SMTP delivery.")
@click.option("--host", required=True, help="SMTP server hostname or IP.")
@click.option("--port", type=click.IntRange(min=1, max=65535), default=587, show_default=True, help="SMTP server port.")
@click.option("--encryption", type=click.Choice(["starttls", "ssl", "none"], case_sensitive=False), default="starttls", show_default=True, help="SMTP transport encryption.")
@click.option("--from-email", required=True, help="Sender email address.")
@click.option("--from-name", default="Websoft9", show_default=True, help="Sender display name.")
@click.option("--username", default="", help="Optional SMTP username.")
@click.option("--password-stdin", is_flag=True, help="Read SMTP password from standard input.")
@click.option("--yes", "-y", is_flag=True, help="Confirm saving SMTP settings.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def set_smtp_command(
    enabled: bool,
    host: str,
    port: int,
    encryption: str,
    from_email: str,
    from_name: str,
    username: str,
    password_stdin: bool,
    yes: bool,
    as_json: bool,
) -> None:
    """Update platform SMTP settings."""
    def action() -> dict[str, Any]:
        from src.services.smtp_service import SmtpService

        password: str | None = None
        if password_stdin:
            password = sys.stdin.read().rstrip("\r\n")
            if password == "******":
                raise CLIError("INVALID_ARGUMENT", "Refusing to save masked password placeholder '******'", exit_code=2)

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    "Saving SMTP settings requires --yes confirmation",
                    details={"host": host, "port": port, "from_email": from_email},
                )
            if not click.confirm(f"Save SMTP settings ({host}:{port}, from={from_email}, enabled={enabled})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        return SmtpService().save_settings(
            enabled=enabled,
            host=host,
            port=port,
            encryption=encryption.lower(),
            username=username,
            password=password,
            from_email=from_email,
            from_name=from_name,
        )

    def render_text(payload: dict[str, Any]) -> str:
        return f"Saved SMTP settings: host={payload.get('host')}:{payload.get('port')} enabled={payload.get('enabled')}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_smtp_group.command(name="test")
@click.option("--to", "to_email", required=True, help="Recipient email address for test message.")
@click.option("--yes", "-y", is_flag=True, help="Confirm sending test email.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def test_smtp_command(to_email: str, yes: bool, as_json: bool) -> None:
    """Send a test email using the configured SMTP server."""
    def action() -> dict[str, Any]:
        from src.services.smtp_service import SmtpService

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Sending test email to '{to_email}' requires --yes confirmation")
            if not click.confirm(f"Send test email to '{to_email}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        SmtpService().send_email(
            to_email=to_email.strip(),
            subject="Websoft9 SMTP Test",
            body_text="This is a test email from the Websoft9 CLI.",
        )
        return {
            "status": "sent",
            "to_email": to_email.strip(),
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Test email sent to {payload.get('to_email')}."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_upgrade_group.command(name="status")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def upgrade_status_command(as_json: bool) -> None:
    """Inspect current platform upgrade state without refreshing remote artifacts."""
    def action() -> dict[str, Any]:
        from src.api.v1.routers.settings import _upgrade_status_payload

        return _upgrade_status_payload(refresh_latest=False)

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Upgrade status: current={payload.get('current_version')} latest={payload.get('latest_version')} "
            f"channel={payload.get('channel')} state={payload.get('state')} upgrade_available={payload.get('upgrade_available')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_upgrade_group.command(name="check")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def upgrade_check_command(as_json: bool) -> None:
    """Check artifact channel for the latest release version without starting a download."""
    def action() -> dict[str, Any]:
        from src.api.v1.routers.settings import _is_newer_stable_version
        from src.services.product_runtime_state import read_release_channel, read_release_version
        from src.services.release_checker import ReleaseVersionChecker
        from src.services.upgrade_manager import UpgradeManager

        current_version = read_release_version() or ""
        channel = read_release_channel()
        latest_version = ReleaseVersionChecker().ensure_latest_version(channel=channel, force=True)
        status = UpgradeManager().status()
        return {
            **status,
            "current_version": current_version,
            "channel": channel,
            "latest_version": latest_version or current_version,
            "upgrade_available": _is_newer_stable_version(latest_version, current_version),
        }

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Release check ({payload.get('channel')}): current={payload.get('current_version')} "
            f"latest={payload.get('latest_version')} upgrade_available={payload.get('upgrade_available')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_upgrade_group.command(name="prepare")
@click.option("--yes", "-y", is_flag=True, help="Confirm staging platform upgrade artifacts in background.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def upgrade_prepare_command(yes: bool, as_json: bool) -> None:
    """Stage upgrade artifacts in the background without replacing the running container."""
    def action() -> dict[str, Any]:
        from src.cli.upgrade_dispatch import dispatch_upgrade_preparation

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", "Staging platform upgrade artifacts requires --yes confirmation")
            if not click.confirm("Download and stage platform upgrade artifacts in the background?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        return dispatch_upgrade_preparation()

    def render_text(payload: dict[str, Any]) -> str:
        return f"Upgrade preparation started: run_id={payload.get('run_id')} state={payload.get('state')}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@settings_upgrade_group.command(name="logs")
@click.argument("run_id")
@click.option("--tail", type=click.IntRange(min=1, max=1000), default=200, show_default=True, help="Number of tail lines to read.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def upgrade_logs_command(run_id: str, tail: int, as_json: bool) -> None:
    """Read tail lines of a platform upgrade run log."""
    def action() -> dict[str, Any]:
        from src.services.upgrade_manager import UpgradeManager

        return UpgradeManager().read_log(run_id, tail=tail)

    def render_text(payload: dict[str, Any]) -> str:
        lines = payload.get("lines") or []
        return "\n".join(lines) if lines else f"No upgrade log lines for run '{payload.get('run_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
