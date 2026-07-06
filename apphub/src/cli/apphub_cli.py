import configparser
import sys
import os
import json
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import click
from src.core.runtime_paths import resolve_apphub_config_path
from src.services.marketplace_bootstrap import MarketplaceBootstrapService
from src.services.product_metadata import write_product_edition
from src.services.settings_manager import SettingsManager
from src.services.product_auth import ProductAuthService
from src.core.exception import CustomException
from src.services.appstore_sync_manager import AppStoreSyncManager

@click.group()
def cli():
    pass


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
@click.option('--app-slug', required=True, help='Marketplace app slug')
@click.option('--default-locale', required=True, type=click.Choice(['en', 'zh-CN'], case_sensitive=True), help='Default setup locale')
def setmarketplace(app_slug, default_locale):
    """Set marketplace bootstrap metadata"""
    try:
        payload = MarketplaceBootstrapService().write(app_slug=app_slug, default_locale=default_locale)
        click.echo(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('target', required=True, type=click.Choice(['apps'], case_sensitive=False))
@click.option('--channel', type=click.Choice(['release', 'rc', 'dev'], case_sensitive=False), help='Upgrade using the specified artifact channel')
@click.option('--dev', is_flag=True, help='Upgrade using dev environment')
@click.option('--force-refresh', is_flag=True, help='Force a full App Store sync instead of using incremental update detection')
def upgrade(target, channel, dev, force_refresh):
    """Upgrade apps"""
    try:
        if target == 'apps':
            if dev and channel and channel.lower() != 'dev':
                raise click.ClickException("--dev cannot be combined with a non-dev --channel value")

            resolved_channel = (channel or ('dev' if dev else '')).lower() or None
            result = AppStoreSyncManager().sync(
                trigger='cli',
                channel=resolved_channel,
                package_types='media,library',
                force_refresh=force_refresh,
                background=False,
            )
            active_channel = str(result.get('channel') or resolved_channel or 'release').lower()
            dataset_version = result.get('datasetVersion')
            if dataset_version:
                click.echo(f"App Store resources ({active_channel}) synchronized successfully: {dataset_version}")
            else:
                click.echo(f"App Store resources ({active_channel}) synchronized successfully.")
        else:
            click.echo(f"Unknown upgrade target: {target}")
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
    cli()
