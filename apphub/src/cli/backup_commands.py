from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


@click.group(name="backup")
def backup_group():
    """Manage application volume backups with Restic.

    This is not a platform-wide backup or a native SQL database dump.
    """


def _summarize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    tags = snapshot.get("tags") or []
    paths = snapshot.get("paths") or []
    return {
        "id": snapshot.get("short_id") or snapshot.get("id"),
        "full_id": snapshot.get("id"),
        "time": snapshot.get("time"),
        "app_id": tags[0] if isinstance(tags, list) and tags else None,
        "tags": tags if isinstance(tags, list) else [],
        "paths": paths if isinstance(paths, list) else [],
        "hostname": snapshot.get("hostname"),
    }


@backup_group.command(name="list")
@click.option("--app-id", help="Filter snapshots by application ID tag.")
@click.option("--refresh", is_flag=True, help="Bypass in-memory snapshot cache.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_backups_command(app_id: str | None, refresh: bool, as_json: bool) -> None:
    """List Restic volume backup snapshots."""
    def action() -> dict[str, Any]:
        from src.services.back_manager import BackupManager

        snapshots = BackupManager().list_snapshots(app_id=app_id, use_cache=not refresh) or []
        items = [_summarize_snapshot(item) for item in snapshots if isinstance(item, dict)]
        return {
            "app_id": app_id,
            "items": items,
            "total": len(items),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No backup snapshots found."
        lines = [f"Backup Snapshots ({len(items)}):"]
        for item in items:
            lines.append(
                f"- {item.get('id')} app={item.get('app_id') or '-'} time={item.get('time')} "
                f"paths={', '.join(item.get('paths') or [])}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@backup_group.command(name="create")
@click.argument("app_id")
@click.option("--yes", "-y", is_flag=True, help="Confirm creating a volume snapshot.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def create_backup_command(app_id: str, yes: bool, as_json: bool) -> None:
    """Create a Restic volume snapshot for an application."""
    def action() -> dict[str, Any]:
        from src.services.back_manager import BackupManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Creating backup snapshot for '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id},
                )
            if not click.confirm(f"Create volume backup snapshot for application '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        manager = BackupManager()
        manager.create_backup(app_id)
        snapshots = manager.list_snapshots(app_id=app_id, use_cache=False) or []
        latest = _summarize_snapshot(snapshots[-1]) if snapshots and isinstance(snapshots[-1], dict) else None
        return {
            "app_id": app_id,
            "status": "created",
            "snapshot": latest,
        }

    def render_text(payload: dict[str, Any]) -> str:
        snap = payload.get("snapshot") or {}
        return f"Created backup snapshot for '{payload.get('app_id')}' (snapshot_id={snap.get('id') or '-'})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@backup_group.command(name="delete")
@click.argument("snapshot_id")
@click.option("--yes", "-y", is_flag=True, help="Confirm deleting the backup snapshot.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def delete_backup_command(snapshot_id: str, yes: bool, as_json: bool) -> None:
    """Delete a Restic backup snapshot by ID."""
    def action() -> dict[str, Any]:
        from src.services.back_manager import BackupManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Deleting backup snapshot '{snapshot_id}' requires --yes confirmation",
                    details={"snapshot_id": snapshot_id},
                )
            if not click.confirm(f"Permanently delete backup snapshot '{snapshot_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        BackupManager().delete_snapshot(snapshot_id)
        return {
            "deleted_snapshot_id": snapshot_id,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Deleted backup snapshot '{payload.get('deleted_snapshot_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@backup_group.command(name="restore")
@click.argument("app_id")
@click.argument("snapshot_id")
@click.option("--yes", "-y", is_flag=True, help="Confirm overwriting application volume data with the snapshot.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def restore_backup_command(app_id: str, snapshot_id: str, yes: bool, as_json: bool) -> None:
    """Overwrite volume data from a matching snapshot; restore inactive stacks with app restore first."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger
        from src.services.back_manager import BackupManager

        app = AppManger().get_app_by_id(
            app_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        volumes = [v.get("Name") for v in (getattr(app, "volumes", None) or []) if isinstance(v, dict) and v.get("Name")]
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Restoring snapshot '{snapshot_id}' for '{app_id}' will overwrite volumes {volumes} and requires --yes confirmation",
                    details={"app_id": app_id, "snapshot_id": snapshot_id, "volumes": volumes},
                )
            if not click.confirm(f"Stop '{app_id}', overwrite volumes {volumes} with snapshot '{snapshot_id}', and restart containers?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        BackupManager().restore_backup(app_id, snapshot_id)
        return {
            "app_id": app_id,
            "snapshot_id": snapshot_id,
            "restored_volumes": volumes,
            "status": "restored",
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Restored snapshot '{payload.get('snapshot_id')}' for '{payload.get('app_id')}' (volumes={', '.join(payload.get('restored_volumes') or [])})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
