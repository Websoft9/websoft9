import configparser
import sys
import os
import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import click
from src.core.runtime_paths import resolve_apphub_config_path
from src.services.product_metadata import write_product_edition
from src.services.settings_manager import SettingsManager
from src.services.product_auth import ProductAuthService
from src.core.exception import CustomException
from src.core.logger import logger
from src.services.appstore_sync_manager import AppStoreSyncManager
from src.services.scheduled_tasks import SKIPPED_EXIT_CODE, ScheduledTaskService
from src.services.product_runtime_state import read_release_channel
from src.services.release_checker import ReleaseVersionChecker
from src.cli.app_commands import app_group


UPGRADE_DISPATCH_URL = "http://127.0.0.1:8080/api/settings/internal/upgrade/auto-prepare"
UPGRADE_DISPATCH_SECRET_HEADER = "x-websoft9-upgrade-dispatch-secret"


def _dispatch_auto_download() -> bool:
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    secret_path = os.getenv(
        "WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE",
        f"{data_root}/config/internal-gateway-auth/trust_key",
    )
    try:
        with open(secret_path, encoding="utf-8") as handle:
            secret = handle.read().strip()
    except OSError as exc:
        raise click.ClickException(f"Unable to read the upgrade dispatcher credential: {exc}") from exc
    if not secret:
        raise click.ClickException("The upgrade dispatcher credential is empty")

    request = Request(
        UPGRADE_DISPATCH_URL,
        data=b"",
        headers={UPGRADE_DISPATCH_SECRET_HEADER: secret},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed loopback URL
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        raise click.ClickException(f"Unable to dispatch the upgrade download to AppHub: {exc}") from exc
    return bool(payload.get("started"))

@click.group()
def cli():
    pass


cli.add_command(app_group)


@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', required=True, help='The key name')
@click.option('--value', required=True,help='The value of the key')
def setconfig(section, key, value):
    """Set a config value"""
    try:
        SettingsManager().write_section(section, key, value)
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

# 新增 setsysconfig 方法
@cli.command()
@click.option('--section', required=True, help='The section name')
@click.option('--key', required=True, help='The key name')
@click.option('--value', required=True, help='The value of the key')
def setsysconfig(section, key, value):
    """Set a system config value"""
    try:
        system_config_path = resolve_apphub_config_path('system.ini')
        config = configparser.ConfigParser()
        config.read(system_config_path, encoding="utf-8")
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, key, value)
        with open(system_config_path, 'w', encoding="utf-8") as configfile:
            config.write(configfile)
        click.echo(f"Set [{section}] {key}={value} in system.ini successfully.")
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.option('--section', help='The section name')
@click.option('--key', help='The key name')
def getconfig(section, key):
    """Get a config value or all config as JSON"""
    try:
        config_path = resolve_apphub_config_path('config.ini')
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        if section is None:
            all_config = {s: dict(config.items(s)) for s in config.sections()}
            click.echo(json.dumps(all_config))
        elif key is None:
            value = dict(config.items(section)) if section in config.sections() else {}
            click.echo(json.dumps(value))
        else:
            value = config.get(section, key) if config.has_option(section, key) else ""
            click.echo(f"{value}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(hidden=True)
@click.argument('edition_key')
def setedition(edition_key):
    """Set runtime product edition state"""
    try:
        edition = write_product_edition(edition_key)
        click.echo(f"Set product edition to {edition.key} (max_apps={edition.max_apps})")
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument('target', required=True, type=click.Choice(['apps'], case_sensitive=False))
@click.option('--channel', type=click.Choice(['release', 'rc', 'dev'], case_sensitive=False), help='Deprecated; use "appstore sync --channel"')
@click.option('--dev', is_flag=True, help='Deprecated; use "appstore sync --dev"')
@click.option('--force-refresh', is_flag=True, help='Deprecated; use "appstore sync --force-refresh"')
def upgrade(target, channel, dev, force_refresh):
    """Upgrade apps (deprecated no-op)"""
    # Deprecated compatibility shim. External automation still calls `upgrade apps`, but
    # App Store synchronization is now triggered explicitly through `appstore sync`.
    # Keep the command cheap and successful so those callers keep working unchanged.
    click.echo("'upgrade apps' no longer synchronizes App Store resources; run 'websoft9 appstore sync' instead.")


@cli.group()
def appstore():
    """Manage the local App Store dataset"""


@cli.group()
def images():
    """Manage application image preparation"""


@images.command(name="dispatch")
@click.option('--skip-if-running', is_flag=True, help=f'Exit with code {SKIPPED_EXIT_CODE} when another dispatcher is active')
@click.option('--quiet', is_flag=True, help='Suppress normal dispatch output for internal queue checks')
def images_dispatch(skip_if_running, quiet):
    """Start the next queued image prewarm task, if any."""
    try:
        result = ScheduledTaskService().dispatch_prewarm()
    except Exception as exc:
        logger.warning(f"Image prewarm dispatch failed: {exc}")
        raise click.ClickException(str(exc)) from exc
    if result["status"] == "skipped" and skip_if_running:
        raise click.exceptions.Exit(SKIPPED_EXIT_CODE)
    if not quiet:
        click.echo(json.dumps(result))


def _human_size(value) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.2f}GB"


def _format_prewarm_event(event, state) -> str:
    """Render one prewarm event as a readable log line, or '' when it repeats itself.

    Docker reports every layer on every chunk it receives, so the raw stream repeats the same headers
    hundreds of times and buries the useful information. Each layer status is therefore printed once
    and download progress only when it crosses another 10% step.
    """
    if not isinstance(event, dict):
        return ""

    kind = event.get("event")
    if kind == "image-ready":
        return f"[prewarm] {event.get('image')} already present"
    if kind == "image-pull-started":
        state["image"] = str(event.get("image") or "")
        return f"[prewarm] pulling {state['image']}"
    if kind == "image-pull-completed":
        return f"[prewarm] pulled {event.get('image')}"

    status = str(event.get("status") or "").strip()
    if not status:
        return ""

    layer = str(event.get("id") or "-")
    progress = event.get("progressDetail") or {}
    current = progress.get("current")
    total = progress.get("total")

    if status.lower() == "downloading" and isinstance(current, int) and isinstance(total, int) and total > 0:
        percent = int(current * 100 / total)
        key = (state["image"], layer)
        # A finished layer is reported repeatedly, so 100% is throttled like every other step.
        if percent - state["steps"].get(key, -10) < 10:
            return ""
        state["steps"][key] = percent
        return f"[prewarm]   {layer} {status} {percent}% ({_human_size(current)}/{_human_size(total)})"

    key = (state["image"], layer, status)
    if key in state["seen"]:
        return ""
    state["seen"].add(key)
    return f"[prewarm]   {layer} {status}"


@images.command(name="prewarm")
@click.option("--app", "app_name", required=True, help="Application key from the local App Store library")
@click.option("--version", required=True, help="Supported community application version")
def images_prewarm(app_name, version):
    """Pull all images required by one application version."""
    try:
        from src.services.image_prewarm import ImagePrewarmService

        state = {"image": "", "steps": {}, "seen": set()}

        def report(event):
            line = _format_prewarm_event(event, state)
            if line:
                click.echo(line)

        click.echo(json.dumps(ImagePrewarmService().prewarm(app_name, version, on_progress=report), ensure_ascii=False))
    except CustomException as exc:
        raise click.ClickException(exc.details) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@appstore.command(name='sync')
@click.option('--channel', type=click.Choice(['release', 'rc', 'dev'], case_sensitive=False), help='Sync using the specified artifact channel')
@click.option('--dev', is_flag=True, help='Sync using dev environment')
@click.option('--force-refresh', is_flag=True, help='Force a full App Store sync instead of using incremental update detection')
@click.option('--no-wait', is_flag=True, help='Return immediately and keep the sync running in the background')
@click.option('--skip-if-running', is_flag=True, help=f'Exit with code {SKIPPED_EXIT_CODE} instead of failing when another sync is already running')
def appstore_sync(channel, dev, force_refresh, no_wait, skip_if_running):
    """Synchronize App Store assets"""
    try:
        if dev and channel and channel.lower() != 'dev':
            raise click.ClickException("--dev cannot be combined with a non-dev --channel value")

        resolved_channel = (channel or ('dev' if dev else '')).lower() or None
        manager = AppStoreSyncManager()
        if manager.is_sync_running():
            if skip_if_running:
                # Scheduled maintenance reports a skip instead of a failure when an operator
                # happens to be syncing: the job did not run, but nothing is wrong.
                click.echo("An App Store sync is already running; skipping this run.")
                sys.exit(SKIPPED_EXIT_CODE)
            raise click.ClickException("An App Store sync is already running")

        result = manager.sync(
            trigger='cli',
            channel=resolved_channel,
            package_types='media,library',
            force_refresh=force_refresh,
            background=no_wait,
        )

        if no_wait:
            click.echo("App Store sync started in the background.")
            return

        active_channel = str(result.get('channel') or resolved_channel or 'release').lower()
        dataset_version = result.get('datasetVersion')
        if dataset_version:
            click.echo(f"App Store resources ({active_channel}) synchronized successfully: {dataset_version}")
        else:
            click.echo(f"App Store resources ({active_channel}) synchronized successfully.")
    except click.ClickException:
        raise
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))


def _refresh_docker_mirror_list() -> None:
    """Refresh the accelerator defaults without ever failing the daily check.

    This runs from cron, so the exit code and the auto-download decision must not depend on
    an artifact endpoint that happens to be slow or dead: a failure is only a warning. The
    host-visible copy is written in the same pass, because a host-side upgrade reads that
    file when it pulls the platform image on its own.
    """
    try:
        from src.services.mirror_registry import MirrorRegistry

        registry = MirrorRegistry()
        registry.refresh_default_list(force=True)
        registry.export_host_visible_list()
    except Exception as exc:
        click.echo(f"Unable to refresh the Docker mirror list: {exc}", err=True)


@cli.command(name='check-update')
def check_update():
    """Check the artifact channel for a newer platform release"""
    try:
        channel = read_release_channel()
        version = ReleaseVersionChecker().ensure_latest_version(channel=channel, force=True)
        if not version:
            raise click.ClickException(f"Unable to determine the latest {channel} release")
        click.echo(f"Latest {channel} release: {version}")
        _refresh_docker_mirror_list()
        if _dispatch_auto_download():
            click.echo("Upgrade download started in the background")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(hidden=True)
def reconcile_scheduled_tasks():
    """Restore local scheduled-task runners and cron after an upgrade."""
    try:
        ScheduledTaskService().reconcile_local_schedule()
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(hidden=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='New password for the system user')
def resetpwd(password):
    """Reset the Websoft9 system user password"""
    try:
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"\d", password) or not re.search(r"[^A-Za-z0-9]", password):
            raise click.ClickException("Password must include uppercase, lowercase, number, and special character")

        auth = ProductAuthService()
        system_user = auth.find_system_user()
        if system_user is None:
            raise click.ClickException("System user not found")

        username = system_user['username']
        display_name = system_user.get('display_name', username)
        click.echo(f"\nSystem user: {username} ({display_name})")
        if not click.confirm("Reset password for this user?"):
            click.echo("Cancelled.")
            return

        auth.reset_system_user_password(system_user['id'], password)
        click.echo(f"Password reset for system user '{username}'")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))

if __name__ == "__main__":
    cli(prog_name=os.environ.get('WEBSOFT9_CLI_NAME') or None)
