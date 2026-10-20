from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import MAX_TEXT_BUDGET_BYTES, mask_sensitive_text, run_cli_action, truncate_utf8_text


@click.group(name="task")
def task_group():
    """Inspect platform scheduled tasks, run histories, and image prewarm records."""


@task_group.group(name="prewarm-records")
def task_prewarm_records_group():
    """Inspect image prewarm queue records."""


@task_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_tasks_command(as_json: bool) -> None:
    """List platform system tasks and user scheduled tasks."""
    def action() -> dict[str, Any]:
        from src.services.scheduled_tasks import ScheduledTaskService

        payload = ScheduledTaskService().collect_tasks_local()
        return {
            "system_tasks": payload.get("system_tasks") or [],
            "tasks": payload.get("tasks") or [],
        }

    def render_text(payload: dict[str, Any]) -> str:
        sys_tasks = payload.get("system_tasks") or []
        user_tasks = payload.get("tasks") or []
        lines = [f"System Tasks ({len(sys_tasks)}):"]
        for item in sys_tasks:
            lines.append(
                f"- {item.get('task_id')} ({item.get('name')}): schedule={item.get('schedule')} "
                f"enabled={item.get('enabled')} last_status={item.get('last_status')}"
            )
        lines.append(f"User Tasks ({len(user_tasks)}):")
        for item in user_tasks:
            lines.append(
                f"- {item.get('task_id')} ({item.get('name')}): schedule={item.get('schedule')} "
                f"enabled={item.get('enabled')} last_status={item.get('last_status')}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@task_group.command(name="runs")
@click.argument("task_id")
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True, help="Maximum execution records to return.")
@click.option("--offset", type=click.IntRange(min=0), default=0, show_default=True, help="Zero-based pagination offset.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_task_runs_command(task_id: str, limit: int, offset: int, as_json: bool) -> None:
    """List execution history for a scheduled task."""
    def action() -> dict[str, Any]:
        from src.services.scheduled_tasks import ScheduledTaskService

        return ScheduledTaskService().collect_runs_local(task_id, offset=offset, limit=limit)

    def render_text(payload: dict[str, Any]) -> str:
        runs = payload.get("runs") or []
        if not runs:
            return f"No execution runs found for task '{task_id}'."
        lines = [f"Task Runs ({len(runs)}/{payload.get('total', len(runs))}):"]
        for item in runs:
            lines.append(
                f"- {item.get('run_id')} status={item.get('status')} exit_code={item.get('exit_code')} "
                f"started_at={item.get('started_at')} trigger={item.get('trigger')}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@task_group.command(name="log")
@click.argument("task_id")
@click.argument("run_id")
@click.option("--before", type=click.IntRange(min=1), default=None, help="Read lines before the given line number (logs up to 1 MiB; larger logs return a bounded tail without pagination).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def task_run_log_command(task_id: str, run_id: str, before: int | None, as_json: bool) -> None:
    """Read bounded execution log output for a container scheduled task run."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.services.scheduled_tasks import ScheduledTaskService

        window = ScheduledTaskService().collect_run_log_local(task_id, run_id, before=before)
        masked = mask_sensitive_text(str(window.get("content") or ""))
        clipped, truncated = truncate_utf8_text(masked, MAX_TEXT_BUDGET_BYTES, keep_tail=True)
        return (
            {
                "task_id": task_id,
                "run_id": run_id,
                "content": clipped,
                "next_before": window.get("next_before"),
            },
            truncated or bool(window.get("truncated")),
        )

    def render_text(payload: dict[str, Any]) -> str:
        return str(payload.get("content") or "")

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@task_prewarm_records_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_prewarm_records_command(as_json: bool) -> None:
    """List queued, running, and completed image prewarm records."""
    def action() -> dict[str, Any]:
        from src.services.scheduled_tasks import ScheduledTaskService

        payload = ScheduledTaskService().collect_tasks_local()
        records = payload.get("prewarm_records") or []
        return {
            "items": records,
            "total": len(records),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No image prewarm records found."
        lines = [f"Image Prewarm Records ({len(items)}):"]
        for item in items:
            lines.append(
                f"- {item.get('task_id')} app={item.get('subject_app')} version={item.get('subject_version')} "
                f"queue_state={item.get('queue_state')} last_status={item.get('last_status')}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
