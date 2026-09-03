import json

import click


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
    """Refresh the private application catalog."""
    from src.services.local_app_store import refresh_local_app_store

    try:
        report = refresh_local_app_store()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(report))
    else:
        click.echo(
            f"Private application catalog refreshed: "
            f"{report['loaded']} loaded, {report['skipped']} skipped."
        )
        for error in report["errors"]:
            click.echo(f"{error['app']}: {error['error']}", err=True)

    if report["skipped"]:
        raise click.exceptions.Exit(2)
