import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import click
from src.services.apikey_manager import APIKeyManager
from src.services.settings_manager import SettingsManager
from src.core.exception import CustomException

@click.group()
def cli():
    pass

@cli.command()
def genkey():
    """Generate a new API key"""
    try:
        key = APIKeyManager().generate_key()
        click.echo(f"{key}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
def getkey():
    """Get the API key"""
    try:
        key = APIKeyManager().get_key()
        click.echo(f"{key}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

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

@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', help='The key name')
def getconfig(section, key):
    """Get a config value"""
    try:          
        if key is None: 
            value = SettingsManager().read_section(section)
            value = json.dumps(value)
            click.echo(f"{value}")
        else:
            value = SettingsManager().read_key(section, key)
            click.echo(f"{value}")
    except CustomException as e:
        raise click.ClickException(e.details)
    except Exception as e:
        raise click.ClickException(str(e))

if __name__ == "__main__":
    cli()