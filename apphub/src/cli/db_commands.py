from __future__ import annotations

import sys
from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


@click.group(name="database")
def db_group():
    """Inspect external database connections used by applications.

    This does not manage Websoft9's internal databases or execute arbitrary SQL.
    """


@db_group.command(name="list")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID to inspect (defaults to local endpoint).")
@click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Locale for application metadata.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_external_dbs_command(endpoint_id: int | None, locale: str, as_json: bool) -> None:
    """List external database bindings grouped across installed applications."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger

        records = AppManger().get_external_databases(endpoint_id, locale=locale.lower(), readonly=True)
        items = [
            {
                "type": record.get("type"),
                "address": record.get("address"),
                "database_name": record.get("database_name"),
                "username": record.get("username"),
                "has_password": bool(record.get("password") and record.get("password") != "-"),
                "apps": record.get("apps") or [],
            }
            for record in records
            if isinstance(record, dict)
        ]
        return {
            "items": items,
            "total": len(items),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No external database connections found."
        lines = [f"External Databases ({len(items)}):"]
        for item in items:
            app_ids = ", ".join(str(app.get("app_id")) for app in (item.get("apps") or []))
            lines.append(
                f"- [{item.get('type')}] {item.get('address')} db={item.get('database_name')} "
                f"user={item.get('username')} apps={app_ids or '-'}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@db_group.command(name="test")
@click.option("--type", "db_type", required=True, type=click.Choice(["mysql", "postgresql"], case_sensitive=False), help="Database engine type.")
@click.option("--host", required=True, help="Database host or IP address.")
@click.option("--port", required=True, type=click.IntRange(min=1, max=65535), help="Database port.")
@click.option("--database", "database_name", required=True, help="Target database name.")
@click.option("--username", required=True, help="Database username.")
@click.option("--password-stdin", is_flag=True, help="Read database password from standard input.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def test_external_db_command(
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password_stdin: bool,
    as_json: bool,
) -> None:
    """Test connectivity and version of an external MySQL/MariaDB or PostgreSQL database."""
    def action() -> dict[str, Any]:
        from src.services.install_profile import validate_external_database_connection

        if password_stdin:
            password = sys.stdin.read().rstrip("\r\n")
        else:
            if as_json:
                raise CLIError("INVALID_ARGUMENT", "Use --password-stdin when running app database test with --json", exit_code=2)
            password = click.prompt("Database password", hide_input=True)

        if not password:
            raise CLIError("INVALID_ARGUMENT", "Database password cannot be empty", exit_code=2)

        conn = validate_external_database_connection(
            db_type.lower(),
            host,
            port,
            database_name,
            username,
            password,
        )
        version_str = ".".join(str(part) for part in conn.version) if conn.version else None
        return {
            "status": "success",
            "requested_type": db_type.lower(),
            "database_type": conn.database_type,
            "version": version_str,
            "host": host,
            "port": port,
            "database_name": database_name,
            "username": username,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Database connection succeeded: type={payload.get('database_type')} "
            f"version={payload.get('version') or '-'} target={payload.get('host')}:{payload.get('port')}/{payload.get('database_name')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
