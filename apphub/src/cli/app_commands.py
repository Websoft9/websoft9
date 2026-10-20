import json
from typing import Any

import click

from src.cli.cli_output import CLIError, MAX_TEXT_BUDGET_BYTES, mask_sensitive_text, route_console_logs_to_stderr, run_cli_action, truncate_utf8_text


_STATUS_NAME_BY_CODE = {
    0: "unknown",
    1: "active",
    2: "inactive",
    3: "installing",
    4: "error",
    6: "cancelled",
}
_STATUS_CODE_BY_NAME = {name: code for code, name in _STATUS_NAME_BY_CODE.items()}


def _resolve_app_type(app: Any) -> str:
    if bool(getattr(app, "is_compose_app", False)):
        return "compose"
    if bool(getattr(app, "app_official", False)) or bool(getattr(app, "app_name", None)):
        return "store"
    return "external"


def _resolve_app_status(app: Any) -> dict[str, Any]:
    raw_status = getattr(app, "status", None)
    code = int(raw_status) if isinstance(raw_status, int) else 0
    return {
        "code": code,
        "name": _STATUS_NAME_BY_CODE.get(code, "unknown"),
    }


def _summarize_container(container: dict[str, Any]) -> dict[str, Any]:
    names = container.get("Names")
    raw_name = names[0] if isinstance(names, list) and names else container.get("Name") or ""
    state_obj = container.get("State")
    if isinstance(state_obj, dict):
        state = str(state_obj.get("Status") or "").strip() or None
        health = str((state_obj.get("Health") or {}).get("Status") or "").strip() or None
        exit_code = state_obj.get("ExitCode")
        oom_killed = state_obj.get("OOMKilled")
    else:
        state = str(state_obj or "").strip() or None
        status_text = str(container.get("Status") or "")
        health = "healthy" if "(healthy)" in status_text.lower() else ("unhealthy" if "(unhealthy)" in status_text.lower() else None)
        exit_code = None
        oom_killed = None
    return {
        "id": container.get("Id") or container.get("ID"),
        "name": str(raw_name).lstrip("/") or None,
        "image": container.get("Image"),
        "state": state,
        "status": container.get("Status"),
        "health": health,
        "exit_code": exit_code,
        "oom_killed": oom_killed,
    }


def _summarize_volume(volume: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": volume.get("Name") or volume.get("name"),
        "driver": volume.get("Driver") or volume.get("driver"),
    }


def _summarize_domain(domain: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": domain.get("id"),
        "domain_names": domain.get("domain_names") or [],
        "forward_scheme": domain.get("forward_scheme"),
        "forward_host": domain.get("forward_host"),
        "forward_port": domain.get("forward_port"),
        "certificate_id": domain.get("certificate_id"),
        "ssl_forced": domain.get("ssl_forced"),
    }


def _serialize_app_item(app: Any) -> dict[str, Any]:
    return {
        "app_id": getattr(app, "app_id", None),
        "endpoint_id": getattr(app, "endpointId", None),
        "type": _resolve_app_type(app),
        "status": _resolve_app_status(app),
        "app_name": getattr(app, "app_name", None),
        "app_dist": getattr(app, "app_dist", None),
        "version": getattr(app, "app_version", None),
        "proxy_enabled": bool(getattr(app, "proxy_enabled", False)),
        "tracking_id": getattr(app, "tracking_id", None),
        "phase": getattr(app, "phase", None),
        "cancel_requested": bool(getattr(app, "cancel_requested", False)),
        "error": getattr(app, "error", None),
    }


def _serialize_app_detail(app: Any) -> dict[str, Any]:
    containers = getattr(app, "containers", None) or []
    volumes = getattr(app, "volumes", None) or []
    domains = getattr(app, "domain_names", None) or []
    env = getattr(app, "env", None) or {}
    return {
        "app": _serialize_app_item(app),
        "containers": [_summarize_container(item) for item in containers if isinstance(item, dict)],
        "volumes": [_summarize_volume(item) for item in volumes if isinstance(item, dict)],
        "domains": [_summarize_domain(item) for item in domains if isinstance(item, dict)],
        "env_keys": sorted(str(key) for key in env.keys()) if isinstance(env, dict) else [],
        "logs": getattr(app, "logs", None) or [],
    }


def _render_app_list_text(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    total = payload.get("total", len(items))
    if not items:
        return f"No applications found (total={total})."
    lines = [f"Applications ({len(items)}/{total}):"]
    for item in items:
        status_name = (item.get("status") or {}).get("name", "unknown")
        version = item.get("version") or "-"
        app_name = item.get("app_name") or "-"
        line = f"- {item.get('app_id')} [{status_name}] type={item.get('type')} app={app_name} version={version}"
        if item.get("error"):
            line += f" error={item.get('error')}"
        lines.append(line)
    return "\n".join(lines)


def _render_app_inspect_text(payload: dict[str, Any]) -> str:
    app = payload.get("app") or {}
    status_name = (app.get("status") or {}).get("name", "unknown")
    containers = payload.get("containers") or []
    volumes = payload.get("volumes") or []
    domains = payload.get("domains") or []
    lines = [
        f"App ID: {app.get('app_id')}",
        f"Status: {status_name} ({(app.get('status') or {}).get('code')})",
        f"Type: {app.get('type')}",
        f"Template: {app.get('app_name') or '-'} ({app.get('version') or '-'})",
        f"Endpoint ID: {app.get('endpoint_id')}",
        f"Containers: {len(containers)}",
        f"Volumes: {len(volumes)}",
        f"Proxy Domains: {sum(len(d.get('domain_names') or []) for d in domains)}",
    ]
    if app.get("error"):
        lines.append(f"Error: {app.get('error')}")
    return "\n".join(lines)


def _parse_settings(set_values: tuple[str, ...]) -> dict[str, str]:
    settings: dict[str, str] = {}
    for item in set_values:
        if "=" not in item:
            raise click.ClickException(
                f"Invalid --set value '{item}': expected KEY=VALUE"
            )
        key, _, value = item.partition("=")
        key = key.strip()
        if not key:
            raise click.ClickException(
                f"Invalid --set value '{item}': key cannot be empty"
            )
        settings[key] = value
    return settings


@click.group(name="app")
def app_group():
    """Install and manage applications."""


@app_group.command(name="install")
@click.argument("app_name", required=False)
@click.option(
    "--app-id",
    "app_id",
    required=False,
    help="Unique application identifier (2-20 lowercase letters/numbers, cannot start with a number).",
)
@click.option(
    "--version",
    "version",
    help="Application version.",
)
@click.option(
    "--dist",
    "dist",
    default="community",
    show_default=True,
    help="Application distribution.",
)
@click.option(
    "--profile",
    "profile",
    help="Installation profile (e.g. external-db).",
)
@click.option(
    "--domain",
    "domains",
    multiple=True,
    help="Domain or IP for the app (repeatable).",
)
@click.option(
    "--no-proxy",
    "no_proxy",
    is_flag=True,
    help="Disable proxy access and use the single --domain host IP directly.",
)
@click.option(
    "--set",
    "set_values",
    multiple=True,
    metavar="KEY=VALUE",
    help="Pass a settings key/value into the app environment (repeatable).",
)
@click.option(
    "--from-json",
    "from_json",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Read the full appInstall JSON payload from a file.",
)
@click.option(
    "--endpoint-id",
    "endpoint_id",
    type=int,
    help="Endpoint ID to install on (defaults to the local endpoint).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print machine-readable JSON on completion.",
)
@click.pass_context
def install(
    context,
    app_name,
    app_id,
    version,
    dist,
    profile,
    domains,
    no_proxy,
    set_values,
    from_json,
    endpoint_id,
    as_json,
):
    """Install an application from the local app library."""
    from src.core.exception import CustomException
    from src.schemas.appInstall import Edition, appInstall

    def fail(message: str):
        raise click.ClickException(str(message or "Installation failed"))

    try:
        if from_json:
            with open(from_json, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            install_options = (
                "app_name",
                "app_id",
                "version",
                "dist",
                "profile",
                "domains",
                "no_proxy",
                "set_values",
            )
            conflicting_options = [
                name.replace("_", "-")
                for name in install_options
                if context.get_parameter_source(name) == click.core.ParameterSource.COMMANDLINE
            ]
            if conflicting_options:
                raise click.ClickException(
                    "--from-json cannot be combined with installation arguments: "
                    + ", ".join(conflicting_options)
                )
            install_payload = appInstall(**payload)
        else:
            if not app_name:
                raise click.ClickException("Missing <app_name>. Use --from-json to install from a JSON file.")
            if not app_id:
                raise click.ClickException("Missing option '--app-id'.")
            if not version:
                raise click.ClickException("Missing option '--version'.")
            if not domains:
                raise click.ClickException("Missing option '--domain'.")

            settings = _parse_settings(set_values)
            proxy_enabled = bool(domains) and not no_proxy

            install_payload = appInstall(
                app_name=app_name,
                edition=Edition(dist=dist, version=version),
                app_id=app_id,
                proxy_enabled=proxy_enabled,
                domain_names=list(domains),
                settings=settings or None,
                profile=profile,
            )

        from src.services.app_manager import AppManger
        from src.services.common_check import install_validate

        with route_console_logs_to_stderr():
            try:
                install_validate(install_payload, endpoint_id)
            except CustomException as exc:
                fail(exc.details or exc.message)

            app_manager = AppManger()
            tracked_app_id, tracking_id = app_manager.create_installation_tracking(install_payload)

            click.echo(
                f"Installing {install_payload.app_name} (app_id={tracked_app_id})...",
                err=True,
            )
            app_manager.install_app(install_payload, endpoint_id, tracked_app_id, tracking_id)

        if as_json:
            click.echo(json.dumps({"app_id": tracked_app_id, "tracking_id": tracking_id}))
        else:
            click.echo(
                f"Installed: {install_payload.app_name} "
                f"(app_id={tracked_app_id}, tracking_id={tracking_id})"
            )
    except click.ClickException:
        raise
    except CustomException as exc:
        fail(exc.details or exc.message)
    except Exception as exc:
        fail(str(exc))


@app_group.command(name="refresh")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print machine-readable JSON on completion.",
)
def refresh(as_json):
    """Rebuild local platform and custom application catalogs."""
    from src.services.local_app_store import refresh_local_app_store_catalog

    try:
        report = refresh_local_app_store_catalog()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(report))
    else:
        click.echo(
            f"Platform application manifests refreshed: "
            f"zh={report['official']['loaded'].get('zh', 0)}, "
            f"en={report['official']['loaded'].get('en', 0)}."
        )
        click.echo(
            f"Custom application catalog refreshed: "
            f"{report['custom']['loaded']} loaded, {report['custom']['skipped']} skipped."
        )
        for error in report["official"]["errors"]:
            click.echo(f"platform: {error['error']}", err=True)
        for error in report["custom"]["errors"]:
            click.echo(f"{error['app']}: {error['error']}", err=True)

    if report["official"]["errors"] or report["custom"]["skipped"]:
        raise click.exceptions.Exit(2)


@app_group.command(name="list")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID to query (defaults to the local endpoint).")
@click.option(
    "--type",
    "app_type",
    type=click.Choice(["all", "store", "compose", "external"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter applications by origin type.",
)
@click.option(
    "--status",
    "status_filter",
    type=click.Choice(["all", "unknown", "active", "inactive", "installing", "error", "cancelled"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter applications by runtime status.",
)
@click.option("--limit", type=click.IntRange(min=1, max=1000), default=100, show_default=True, help="Maximum number of items to return.")
@click.option("--offset", type=click.IntRange(min=0), default=0, show_default=True, help="Zero-based pagination offset.")
@click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Locale for application metadata.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_apps(endpoint_id, app_type, status_filter, limit, offset, locale, as_json):
    """List installed, compose, external, and tracked applications."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger

        apps = AppManger().get_apps(
            endpoint_id,
            locale=locale.lower(),
            reconcile_stale=False,
            readonly_install_state=True,
        )
        items = [_serialize_app_item(app) for app in apps]
        normalized_type = app_type.lower()
        if normalized_type != "all":
            items = [item for item in items if item.get("type") == normalized_type]
        normalized_status = status_filter.lower()
        if normalized_status != "all":
            expected_code = _STATUS_CODE_BY_NAME[normalized_status]
            items = [item for item in items if (item.get("status") or {}).get("code") == expected_code]

        items.sort(key=lambda item: str(item.get("app_id") or ""))
        total = len(items)
        sliced = items[offset : offset + limit]
        return {
            "items": sliced,
            "total": total,
            "limit": limit,
            "offset": offset,
            "warnings": [],
        }

    run_cli_action(action, as_json=as_json, text_renderer=_render_app_list_text)


@app_group.command(name="inspect")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID to query (defaults to the local endpoint).")
@click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Locale for application metadata.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def inspect_app(app_id, endpoint_id, locale, as_json):
    """Inspect a single application instance without mutating state."""
    def action() -> dict[str, Any]:
        from src.core.exception import CustomException
        from src.services.app_manager import AppManger

        try:
            app = AppManger().get_app_by_id(
                app_id,
                endpoint_id,
                locale=locale.lower(),
                reconcile_stale=False,
                readonly_install_state=True,
                strict_exists=True,
            )
        except CustomException as exc:
            if getattr(exc, "status_code", None) == 404 or "not found" in str(getattr(exc, "details", "")).lower():
                raise CLIError("APP_NOT_FOUND", f"Application '{app_id}' not found", details={"app_id": app_id}) from exc
            raise
        payload = _serialize_app_detail(app)
        payload["warnings"] = []
        return payload

    run_cli_action(action, as_json=as_json, text_renderer=_render_app_inspect_text)


def _run_app_lifecycle_command(
    app_id: str,
    endpoint_id: int | None,
    *,
    operation: str,
    as_json: bool,
) -> None:
    def action() -> dict[str, Any]:
        from src.core.exception import CustomException
        from src.services.app_manager import AppManger

        manager = AppManger()
        try:
            if operation == "start":
                manager.start_app(app_id, endpoint_id)
            elif operation == "stop":
                manager.stop_app(app_id, endpoint_id)
            elif operation == "restart":
                manager.restart_app(app_id, endpoint_id)
            else:
                raise CLIError("INVALID_ARGUMENT", f"Unsupported operation: {operation}", exit_code=2)
        except CustomException as exc:
            if getattr(exc, "status_code", None) == 404 or "not found" in str(getattr(exc, "details", "")).lower():
                raise CLIError("APP_NOT_FOUND", f"Application '{app_id}' not found", details={"app_id": app_id}) from exc
            raise

        app = manager.get_app_by_id(
            app_id,
            endpoint_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        return {
            "action": operation,
            "app_id": app_id,
            "endpoint_id": getattr(app, "endpointId", endpoint_id),
            "status": _resolve_app_status(app),
            "containers": [
                _summarize_container(item)
                for item in (getattr(app, "containers", None) or [])
                if isinstance(item, dict)
            ],
        }

    def render_text(payload: dict[str, Any]) -> str:
        status_name = (payload.get("status") or {}).get("name", "unknown")
        return f"Application '{payload.get('app_id')}' {operation} completed (status={status_name})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="start")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to the local endpoint).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def start_app_command(app_id, endpoint_id, as_json):
    """Start all containers for an active application stack."""
    _run_app_lifecycle_command(app_id, endpoint_id, operation="start", as_json=as_json)


@app_group.command(name="stop")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to the local endpoint).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def stop_app_command(app_id, endpoint_id, as_json):
    """Stop all containers for an application stack without removing it."""
    _run_app_lifecycle_command(app_id, endpoint_id, operation="stop", as_json=as_json)


@app_group.command(name="restart")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to the local endpoint).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def restart_app_command(app_id, endpoint_id, as_json):
    """Restart all containers for an active application stack."""
    _run_app_lifecycle_command(app_id, endpoint_id, operation="restart", as_json=as_json)


@app_group.command(name="validate-compose")
@click.option("--file", "compose_file", required=True, type=click.Path(exists=True, dir_okay=False, readable=True), help="Path to docker-compose.yml file.")
@click.option("--app-id", default="composeapp", show_default=True, help="Candidate application identifier (2-20 lowercase alphanumeric chars).")
@click.option("--env", "env_pairs", multiple=True, metavar="KEY=VALUE", help="Environment variable key=value pair (repeatable).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def validate_compose_command(compose_file, app_id, env_pairs, as_json):
    """Validate a Docker Compose file before deployment."""
    def action() -> dict[str, Any]:
        from pathlib import Path
        from src.schemas.appComposeInstall import ComposeEnvironmentEntry, ComposeValidationRequest
        from src.services.compose_install import validate_compose_installation

        settings = _parse_settings(env_pairs)
        env_entries = [ComposeEnvironmentEntry(key=k, value=v) for k, v in settings.items()]
        content = Path(compose_file).read_text(encoding="utf-8")
        request = ComposeValidationRequest(
            app_id=app_id,
            compose_content=content,
            env=env_entries,
        )
        response = validate_compose_installation(request)
        return response.model_dump()

    def render_text(payload: dict[str, Any]) -> str:
        services = ", ".join(payload.get("services") or [])
        return f"Compose validation passed: services=[{services}] ({payload.get('details')})"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="install-compose")
@click.option("--app-id", required=True, help="Application identifier prefix (2-20 lowercase letters/numbers).")
@click.option("--file", "compose_file", required=True, type=click.Path(exists=True, dir_okay=False, readable=True), help="Path to docker-compose.yml file.")
@click.option("--env", "env_pairs", multiple=True, metavar="KEY=VALUE", help="Environment variable key=value pair (repeatable).")
@click.option("--domain", default=None, help="Optional domain or IP for reverse proxy configuration.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID to install on (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm deploying custom Compose application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def install_compose_command(app_id, compose_file, env_pairs, domain, endpoint_id, yes, as_json):
    """Install a custom Docker Compose application."""
    def action() -> dict[str, Any]:
        from pathlib import Path
        from src.schemas.appComposeInstall import ComposeEnvironmentEntry, ComposeInstallRequest
        from src.services.compose_install import (
            install_compose_application,
            prepare_compose_install_tracking,
            validate_compose_installation,
        )

        settings = _parse_settings(env_pairs)
        env_entries = [ComposeEnvironmentEntry(key=k, value=v) for k, v in settings.items()]
        content = Path(compose_file).read_text(encoding="utf-8")
        payload = ComposeInstallRequest(
            app_id=app_id,
            compose_content=content,
            env=env_entries,
            domain=domain,
        )
        validation = validate_compose_installation(payload)
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Deploying custom Compose app '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "services": validation.services},
                )
            if not click.confirm(f"Deploy custom Compose app '{app_id}' with services {validation.services}?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        tracked_app_id, tracking_id = prepare_compose_install_tracking(payload)
        install_compose_application(payload, endpoint_id, tracked_app_id, tracking_id)
        return {
            "app_id": tracked_app_id,
            "tracking_id": tracking_id,
            "services": validation.services,
            "domain": domain,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Installed Compose app: app_id={payload.get('app_id')} tracking_id={payload.get('tracking_id')}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="redeploy")
@click.argument("app_id")
@click.option("--pull-image/--no-pull-image", "pull_image", default=False, show_default=True, help="Whether to force re-pulling images before redeploying.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm redeploying the application stack.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def redeploy_app_command(app_id, pull_image, endpoint_id, yes, as_json):
    """Redeploy an application stack from its Gitea configuration repository."""
    def action() -> dict[str, Any]:
        import asyncio
        from src.core.exception import CustomException
        from src.services.app_manager import AppManger
        from src.services.compose_app_manager import ComposeAppManager, _list_src_files, _parse_user_env
        from src.services.gitea_manager import GiteaManager

        manager = AppManger()
        try:
            app = manager.get_app_by_id(
                app_id,
                endpoint_id,
                reconcile_stale=False,
                readonly_install_state=True,
                strict_exists=True,
            )
        except CustomException as exc:
            if getattr(exc, "status_code", None) == 404 or "not found" in str(getattr(exc, "details", "")).lower():
                raise CLIError("APP_NOT_FOUND", f"Application '{app_id}' not found", details={"app_id": app_id}) from exc
            raise

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Redeploying application '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "pull_image": pull_image},
                )
            if not click.confirm(f"Redeploy application '{app_id}' (pull_image={pull_image})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        if getattr(app, "is_compose_app", False):
            ComposeAppManager().redeploy_compose_app(app_id, endpoint_id, pull_image=pull_image)
        else:
            asyncio.run(manager.redeploy_app(app_id, pull_image, endpoint_id))

        updated_app = manager.get_app_by_id(
            app_id,
            endpoint_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        return {
            "action": "redeploy",
            "app_id": app_id,
            "pull_image": pull_image,
            "status": _resolve_app_status(updated_app),
        }

    def render_text(payload: dict[str, Any]) -> str:
        status_name = (payload.get("status") or {}).get("name", "unknown")
        return f"Application '{payload.get('app_id')}' redeployed (status={status_name})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="update-compose")
@click.argument("app_id")
@click.option("--file", "compose_file", required=True, type=click.Path(exists=True, dir_okay=False, readable=True), help="Path to updated docker-compose.yml file.")
@click.option("--env", "env_pairs", multiple=True, metavar="KEY=VALUE", help="Environment variable key=value override (repeatable; preserves unspecified existing vars unless --replace-env is set).")
@click.option("--replace-env", is_flag=True, help="Replace all user environment variables instead of merging with existing .env.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm updating and redeploying the custom Compose application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def update_compose_command(app_id, compose_file, env_pairs, replace_env, endpoint_id, yes, as_json):
    """Update docker-compose.yml and .env of a custom Compose application and redeploy it."""
    def action() -> dict[str, Any]:
        from pathlib import Path
        from src.schemas.appComposeInstall import ComposeEnvironmentEntry, ComposeValidationRequest
        from src.services.compose_app_manager import ComposeAppManager
        from src.services.compose_install import validate_compose_installation

        content = Path(compose_file).read_text(encoding="utf-8")
        if "******" in content:
            raise CLIError("INVALID_ARGUMENT", "Refusing to update Compose file containing masked placeholder '******'", exit_code=2)

        overrides = _parse_settings(env_pairs)
        for k, v in overrides.items():
            if v == "******":
                raise CLIError("INVALID_ARGUMENT", f"Refusing to write masked placeholder '******' for key '{k}'", exit_code=2)

        compose_mgr = ComposeAppManager()
        current = compose_mgr.get_compose_content(app_id)
        existing_env = {entry["key"]: entry["value"] for entry in (current.get("env") or []) if isinstance(entry, dict) and entry.get("key")}
        merged_env = dict(overrides) if replace_env else {**existing_env, **overrides}
        env_list = [{"key": k, "value": v} for k, v in merged_env.items()]
        mounts = current.get("mounts") or []

        validation = validate_compose_installation(
            ComposeValidationRequest(
                app_id="composeupd",
                compose_content=content,
                env=[ComposeEnvironmentEntry(key=k, value=v) for k, v in merged_env.items()],
            )
        )
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Updating Compose application '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "services": validation.services},
                )
            if not click.confirm(f"Update and redeploy Compose application '{app_id}' (services={validation.services})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        compose_mgr.update_compose_content(
            app_id=app_id,
            compose_content=content,
            env=env_list,
            mounts=mounts,
            endpoint_id=endpoint_id,
        )
        return {
            "action": "update-compose",
            "app_id": app_id,
            "services": validation.services,
            "env_keys": sorted(merged_env.keys()),
            "preserved_mounts": [m.get("path") for m in mounts if isinstance(m, dict)],
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Updated and redeployed Compose app '{payload.get('app_id')}' (services={', '.join(payload.get('services') or [])})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="diagnose")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--lines", type=click.IntRange(min=1, max=1000), default=80, show_default=True, help="Number of tail log lines per abnormal container.")
@click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Locale for application metadata.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def diagnose_app_command(app_id, endpoint_id, lines, locale, as_json):
    """Collect deterministic diagnostic evidence and findings for an application."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.core.exception import CustomException
        from src.services.app_access_manager import AppAccessManager
        from src.services.app_manager import AppManger
        from src.services.portainer_manager import PortainerManager

        manager = AppManger()
        try:
            app = manager.get_app_by_id(
                app_id,
                endpoint_id,
                locale=locale.lower(),
                reconcile_stale=False,
                readonly_install_state=True,
                strict_exists=True,
            )
        except CustomException as exc:
            if getattr(exc, "status_code", None) == 404 or "not found" in str(getattr(exc, "details", "")).lower():
                raise CLIError("APP_NOT_FOUND", f"Application '{app_id}' not found", details={"app_id": app_id}) from exc
            raise

        app_summary = _serialize_app_item(app)
        status_code = (app_summary.get("status") or {}).get("code", 0)
        resolved_endpoint = getattr(app, "endpointId", endpoint_id)

        evidence: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        warnings: list[str] = []
        truncated = False
        used_text_bytes = 0

        # 1. Install tracking / stage evidence
        install_logs = getattr(app, "logs", None) or []
        if status_code in {3, 4, 6} or install_logs or app_summary.get("error"):
            evidence.append(
                {
                    "source": "install_state",
                    "status": "collected",
                    "data": {
                        "status": app_summary.get("status"),
                        "phase": app_summary.get("phase"),
                        "tracking_id": app_summary.get("tracking_id"),
                        "error": mask_sensitive_text(str(app_summary.get("error") or "")) or None,
                        "stages": install_logs[-10:],
                    },
                    "error": None,
                }
            )
        else:
            evidence.append({"source": "install_state", "status": "not_applicable", "data": None, "error": None})

        if status_code == 4 and app_summary.get("error"):
            findings.append(
                {
                    "code": "APP_ERROR_STATE",
                    "severity": "error",
                    "summary": mask_sensitive_text(str(app_summary.get("error"))),
                    "evidence_refs": ["install_state"],
                    "next_steps": ["Inspect install_state error details and container logs before retrying or redeploying."],
                }
            )
        elif status_code == 3:
            findings.append(
                {
                    "code": "APP_INSTALL_IN_PROGRESS",
                    "severity": "info",
                    "summary": f"Application installation is currently in progress (phase={app_summary.get('phase') or 'unknown'}).",
                    "evidence_refs": ["install_state"],
                    "next_steps": ["Wait for the active installation task to finish before running lifecycle actions."],
                }
            )

        # 2. Container inspect & logs evidence
        raw_containers = getattr(app, "containers", None) or []
        if status_code == 2 and not raw_containers:
            evidence.append({"source": "containers", "status": "not_applicable", "data": [], "error": None})
        else:
            portainer_mgr = PortainerManager()
            container_details: list[dict[str, Any]] = []
            for idx, item in enumerate(raw_containers[:20]):
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("Id") or "")
                summarized = _summarize_container(item)
                if cid and resolved_endpoint:
                    try:
                        full_info = portainer_mgr.get_container_by_id(resolved_endpoint, cid)
                        state_obj = full_info.get("State") or {}
                        summarized["state"] = state_obj.get("Status") or summarized.get("state")
                        summarized["exit_code"] = state_obj.get("ExitCode")
                        summarized["oom_killed"] = bool(state_obj.get("OOMKilled", False))
                        summarized["restart_count"] = full_info.get("RestartCount", 0)
                        health_obj = state_obj.get("Health") or {}
                        if isinstance(health_obj, dict) and health_obj.get("Status"):
                            summarized["health"] = health_obj.get("Status")
                    except Exception as exc:
                        warnings.append(f"container_inspect_failed:{cid[:12]}:{exc}")
                container_details.append(summarized)

                cname = summarized.get("name") or cid[:12]
                cstate = str(summarized.get("state") or "").lower()
                chealth = str(summarized.get("health") or "").lower()
                exit_code = summarized.get("exit_code")
                oom_killed = bool(summarized.get("oom_killed"))

                if oom_killed:
                    findings.append(
                        {
                            "code": "CONTAINER_OOM_KILLED",
                            "severity": "error",
                            "summary": f"Container '{cname}' was terminated due to Out-Of-Memory (OOMKilled=true).",
                            "evidence_refs": ["containers", f"container_logs:{cname}"],
                            "next_steps": ["Check host memory usage and container memory limits."],
                        }
                    )
                elif cstate in {"exited", "dead", "restarting"} and exit_code not in (None, 0):
                    findings.append(
                        {
                            "code": "CONTAINER_ABNORMAL_EXIT",
                            "severity": "error",
                            "summary": f"Container '{cname}' is in state '{cstate}' with exit_code={exit_code}.",
                            "evidence_refs": ["containers", f"container_logs:{cname}"],
                            "next_steps": [f"Review container_logs:{cname} for startup or configuration errors."],
                        }
                    )
                elif chealth == "unhealthy":
                    findings.append(
                        {
                            "code": "CONTAINER_UNHEALTHY",
                            "severity": "warning",
                            "summary": f"Container '{cname}' reported health='unhealthy'.",
                            "evidence_refs": ["containers", f"container_logs:{cname}"],
                            "next_steps": [f"Review container_logs:{cname} and service readiness."],
                        }
                    )

                should_collect_logs = (
                    oom_killed
                    or chealth == "unhealthy"
                    or cstate not in {"running"}
                    or status_code == 4
                    or idx == 0
                )
                if should_collect_logs and cid and resolved_endpoint:
                    source_key = f"container_logs:{cname}"
                    try:
                        raw_bytes, scan_trunc = portainer_mgr.portainer.read_container_logs_bounded(
                            resolved_endpoint,
                            cid,
                            {"stdout": "true", "stderr": "true", "follow": "false", "tail": str(lines)},
                            max_bytes=512 * 1024,
                            timeout_seconds=15,
                        )
                        if raw_bytes is None:
                            evidence.append({"source": source_key, "status": "unavailable", "data": None, "error": "Container logs not found"})
                        else:
                            decoded = AppAccessManager.decode_container_log_entries(raw_bytes, allow_partial_frame=scan_trunc)
                            tail_entries = decoded[-lines:] if len(decoded) > lines else decoded
                            bounded_entries: list[dict[str, str]] = []
                            for log_item in reversed(tail_entries):
                                masked_line = mask_sensitive_text(log_item.get("text") or "")
                                encoded_line = masked_line.encode("utf-8", errors="replace")
                                if used_text_bytes + len(encoded_line) > MAX_TEXT_BUDGET_BYTES:
                                    truncated = True
                                    break
                                bounded_entries.append({"stream": log_item.get("stream") or "unknown", "text": masked_line})
                                used_text_bytes += len(encoded_line)
                            bounded_entries.reverse()
                            if scan_trunc:
                                truncated = True
                            evidence.append({"source": source_key, "status": "collected", "data": bounded_entries, "error": None})
                    except Exception as exc:
                        evidence.append({"source": source_key, "status": "unavailable", "data": None, "error": mask_sensitive_text(str(exc))})

            evidence.insert(1, {"source": "containers", "status": "collected", "data": container_details, "error": None})

        return (
            {
                "app": app_summary,
                "evidence": evidence,
                "findings": findings,
                "warnings": warnings,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        app = payload.get("app") or {}
        findings = payload.get("findings") or []
        evidence = payload.get("evidence") or []
        lines_out = [
            f"Diagnosis for '{app.get('app_id')}' (status={(app.get('status') or {}).get('name')}, type={app.get('type')}):",
            f"Evidence sources: {len(evidence)}, Findings: {len(findings)}",
        ]
        for finding in findings:
            lines_out.append(f"- [{finding.get('severity')}] {finding.get('code')}: {finding.get('summary')}")
        if not findings:
            lines_out.append("- No known failure patterns detected in collected evidence.")
        return "\n".join(lines_out)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="uninstall")
@click.argument("app_id")
@click.option("--keep-data", "keep_data", is_flag=True, default=True, show_default=True, help="Keep application volumes and Gitea repository (transition to inactive).")
@click.option("--purge-data", "purge_data", is_flag=True, default=False, help="Permanently delete application stack, volumes, proxy, and repository.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm uninstalling the application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def uninstall_app_command(app_id, keep_data, purge_data, endpoint_id, yes, as_json):
    """Uninstall an active application (retains data by default unless --purge-data is set)."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger

        effective_purge = bool(purge_data)
        mode_desc = "PURGE ALL DATA (stack, volumes, repository, proxy)" if effective_purge else "KEEP DATA (transition to inactive)"
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Uninstalling '{app_id}' ({mode_desc}) requires --yes confirmation",
                    details={"app_id": app_id, "purge_data": effective_purge},
                )
            if not click.confirm(f"Uninstall application '{app_id}' [{mode_desc}]?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        AppManger().uninstall_app(app_id, purge_data=effective_purge, endpointId=endpoint_id)
        return {
            "action": "uninstall",
            "app_id": app_id,
            "purge_data": effective_purge,
            "resulting_state": "removed" if effective_purge else "inactive",
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Uninstalled '{payload.get('app_id')}' (purge_data={payload.get('purge_data')}, state={payload.get('resulting_state')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="restore")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm restoring the inactive application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def restore_inactive_app_command(app_id, endpoint_id, yes, as_json):
    """Restore an inactive (uninstalled with retained data) application stack."""
    def action() -> dict[str, Any]:
        import asyncio
        from src.services.app_manager import AppManger
        from src.services.compose_app_manager import ComposeAppManager

        manager = AppManger()
        app = manager.get_app_by_id(
            app_id,
            endpoint_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        if getattr(app, "status", None) != 2:
            raise CLIError("INVALID_REQUEST", f"Application '{app_id}' is not inactive (status={getattr(app, 'status', None)})")

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Restoring inactive application '{app_id}' requires --yes confirmation", details={"app_id": app_id})
            if not click.confirm(f"Restore inactive application '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        if getattr(app, "is_compose_app", False):
            ComposeAppManager().redeploy_compose_app(app_id, endpoint_id, pull_image=False)
        else:
            asyncio.run(manager.redeploy_app(app_id, False, endpoint_id))

        restored = manager.get_app_by_id(
            app_id,
            endpoint_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        return {
            "action": "restore",
            "app_id": app_id,
            "status": _resolve_app_status(restored),
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Restored application '{payload.get('app_id')}' (status={(payload.get('status') or {}).get('name')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="remove")
@click.argument("app_id")
@click.option("--purge-data", is_flag=True, required=True, help="Confirm permanent removal of inactive stack, volumes, repository, and proxy.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--yes", "-y", is_flag=True, help="Confirm permanent removal.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def remove_app_command(app_id, purge_data, endpoint_id, yes, as_json):
    """Permanently remove an inactive application and all retained volumes/repositories."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger

        manager = AppManger()
        app = manager.get_app_by_id(
            app_id,
            endpoint_id,
            reconcile_stale=False,
            readonly_install_state=True,
            strict_exists=True,
        )
        volumes = [v.get("Name") for v in (getattr(app, "volumes", None) or []) if isinstance(v, dict) and v.get("Name")]
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Permanently removing '{app_id}' and volumes {volumes} requires --yes confirmation",
                    details={"app_id": app_id, "volumes": volumes},
                )
            if not click.confirm(f"Permanently remove inactive application '{app_id}' and volumes {volumes}?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        manager.remove_app(app_id, endpoint_id)
        return {
            "action": "remove",
            "app_id": app_id,
            "purged_volumes": volumes,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Permanently removed application '{payload.get('app_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="clean-error")
@click.argument("app_id")
@click.option("--yes", "-y", is_flag=True, help="Confirm cleaning failed/cancelled installation record and orphaned repository/proxy resources.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def clean_error_app_command(app_id, yes, as_json):
    """Clean failed/cancelled tracking and orphaned repo/proxy resources; refuses existing deployments."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger
        from src.services.app_status import list_install_tasks_readonly

        active_installing = [item for _, item in list_install_tasks_readonly((3,), strict=True) if item.get("app_id") == app_id]
        if active_installing:
            raise CLIError("INVALID_REQUEST", f"Application '{app_id}' has an active installation in progress; cancel it first")

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Cleaning failed/cancelled installation '{app_id}' (including any orphaned repository and proxy; existing deployments are refused) requires --yes confirmation",
                    details={"app_id": app_id},
                )
            if not click.confirm(f"Clean failed/cancelled installation '{app_id}' and delete any orphaned repository and proxy (refuses existing deployments)?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        AppManger().remove_error_app(app_id)
        return {
            "action": "clean-error",
            "app_id": app_id,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Cleaned failed/cancelled installation '{payload.get('app_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="cancel")
@click.argument("app_id")
@click.option("--yes", "-y", is_flag=True, help="Confirm requesting cancellation of an active image pull.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def cancel_app_install_command(app_id, yes, as_json):
    """Request cancellation of an application installation during image pull."""
    def action() -> dict[str, Any]:
        from src.services.app_status import request_install_cancel

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Cancelling installation of '{app_id}' requires --yes confirmation", details={"app_id": app_id})
            if not click.confirm(f"Request cancellation for installing application '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        tracking_id = request_install_cancel(app_id)
        if tracking_id is None:
            raise CLIError("INVALID_REQUEST", f"Application '{app_id}' is not currently in a cancellable image-pull phase")
        return {
            "app_id": app_id,
            "tracking_id": tracking_id,
            "cancel_requested": True,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Cancellation requested for '{payload.get('app_id')}' (tracking_id={payload.get('tracking_id')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="credentials")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def app_credentials_command(app_id, endpoint_id, as_json):
    """Inspect credential descriptors and login guidance for an application (secrets masked)."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        overview = AppAccessManager().get_access_overview(app_id, endpoint_id)
        return {
            "app_id": app_id,
            "credentials": [item.model_dump() for item in (overview.credentials or [])],
            "cli_commands": overview.cli_commands or [],
            "login_help": overview.credential_login_help,
        }

    def render_text(payload: dict[str, Any]) -> str:
        creds = payload.get("credentials") or []
        fields = ", ".join(f"{c.get('field')}({c.get('source')})" for c in creds) or "none"
        return f"App '{payload.get('app_id')}' credential descriptors: {fields}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.command(name="php-info")
@click.argument("app_id")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def app_php_info_command(app_id, endpoint_id, as_json):
    """Inspect PHP runtime version and loaded extensions for a PHP-capable application."""
    def action() -> dict[str, Any]:
        from src.services.app_manager import AppManger

        return AppManger().get_php_info(app_id, endpoint_id)

    def render_text(payload: dict[str, Any]) -> str:
        return f"PHP Version: {payload.get('version')}"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_group.group(name="custom-fields")
def app_custom_fields_group():
    """Get or update custom metadata fields for an application."""


@app_custom_fields_group.command(name="get")
@click.argument("app_id")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def get_custom_fields_command(app_id, as_json):
    """Get custom metadata fields for an application."""
    def action() -> dict[str, Any]:
        from src.services.app_status import get_app_custom_fields

        fields = get_app_custom_fields(app_id, readonly=True)
        return {"app_id": app_id, "fields": fields}

    def render_text(payload: dict[str, Any]) -> str:
        fields = payload.get("fields") or []
        if not fields:
            return f"No custom fields for '{payload.get('app_id')}'."
        return "\n".join(f"- {f.get('field_name')} ({f.get('field_type')}): {f.get('field_value')}" for f in fields)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@app_custom_fields_group.command(name="set")
@click.argument("app_id")
@click.option("--field", "field_pairs", multiple=True, required=True, metavar="NAME=VALUE", help="Custom field key=value pair (repeatable).")
@click.option("--yes", "-y", is_flag=True, help="Confirm saving custom metadata fields.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def set_custom_fields_command(app_id, field_pairs, yes, as_json):
    """Save custom metadata fields for an application."""
    def action() -> dict[str, Any]:
        from src.services.app_status import save_app_custom_fields

        parsed = _parse_settings(field_pairs)
        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Saving custom fields for '{app_id}' requires --yes confirmation", details={"app_id": app_id})
            if not click.confirm(f"Save {len(parsed)} custom field(s) for '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        fields_payload = [
            {"field_name": k, "field_value": v, "field_type": "text"}
            for k, v in parsed.items()
        ]
        saved = save_app_custom_fields(app_id, fields_payload)
        return {"app_id": app_id, "fields": saved}

    def render_text(payload: dict[str, Any]) -> str:
        return f"Saved {len(payload.get('fields') or [])} custom field(s) for '{payload.get('app_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
