import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import click
from src.services.apikey_manager import APIKeyManager
from src.services.settings_manager import SettingsManager

@click.group()
def cli():
    pass

@cli.command()
def genkey():
    """Generate a new API key"""
    key = APIKeyManager().generate_key()
    click.echo(f"{key}")

@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', required=True, help='The key name')
@click.option('--value', required=True,help='The value of the key')
def setconfig(section, key, value):
    """Set a config value"""
    SettingsManager().write_section(section, key, value)

@cli.command()
@click.option('--section',required=True, help='The section name')
@click.option('--key', required=True, help='The key name')
def getconfig(section, key):
    """Get a config value"""
    value = SettingsManager().read_key(section, key)
    click.echo(f"{value}")

if __name__ == "__main__":
    cli()