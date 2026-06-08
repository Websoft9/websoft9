import sys
import types
from pathlib import Path

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))

git_module = types.ModuleType('git')
git_module.Repo = object
sys.modules.setdefault('git', git_module)

apikey_manager_module = types.ModuleType('src.services.apikey_manager')


class _APIKeyManager:
    def generate_key(self):
        return 'dummy'

    def get_key(self):
        return 'dummy'


apikey_manager_module.APIKeyManager = _APIKeyManager
sys.modules.setdefault('src.services.apikey_manager', apikey_manager_module)

settings_manager_module = types.ModuleType('src.services.settings_manager')


class _SettingsManager:
    def write_section(self, *args, **kwargs):
        return None


settings_manager_module.SettingsManager = _SettingsManager
sys.modules.setdefault('src.services.settings_manager', settings_manager_module)

exception_module = types.ModuleType('src.core.exception')


class _CustomException(Exception):
    def __init__(self, details=''):
        super().__init__(details)
        self.details = details


exception_module.CustomException = _CustomException
sys.modules.setdefault('src.core.exception', exception_module)

config_module = types.ModuleType('src.core.config')
config_module.ConfigManager = object
sys.modules.setdefault('src.core.config', config_module)

integration_credentials_module = types.ModuleType('src.services.integration_credentials')
integration_credentials_module.IntegrationCredentialProvider = object
sys.modules.setdefault('src.services.integration_credentials', integration_credentials_module)

appstore_sync_manager_module = types.ModuleType('src.services.appstore_sync_manager')


class _AppStoreSyncManager:
    def sync(self, *args, **kwargs):
        return {'status': 'success', 'datasetVersion': '2026.06.08.120000'}

    def list_versions(self, *args, **kwargs):
        return {'activeDatasetVersion': '2026.06.08.120000', 'versions': []}

    def activate(self, *args, **kwargs):
        return {'status': 'success', 'datasetVersion': kwargs.get('dataset_version', '2026.06.08.120000')}


appstore_sync_manager_module.AppStoreSyncManager = _AppStoreSyncManager
sys.modules.setdefault('src.services.appstore_sync_manager', appstore_sync_manager_module)

from src.cli import apphub_cli as cli_module


def test_upgrade_apps_accepts_rc_channel_and_uses_unified_sync_manager(monkeypatch):
    calls = []

    class FakeSyncManager:
        def sync(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'success', 'datasetVersion': '2026.06.08.120000'}

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'apps', '--channel', 'rc'])

    assert result.exit_code == 0
    assert calls == [{
        'trigger': 'cli',
        'channel': 'rc',
        'package_types': 'media,library',
        'force_refresh': True,
    }]
    assert 'App Store resources (rc) synchronized successfully: 2026.06.08.120000' in result.output


def test_upgrade_apps_rejects_conflicting_dev_and_release_channel(monkeypatch):
    class UnexpectedSyncManager:
        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync should not be called for invalid arguments')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', UnexpectedSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'apps', '--dev', '--channel', 'release'])

    assert result.exit_code != 0
    assert '--dev cannot be combined with a non-dev --channel value' in result.output


def test_appstore_versions_outputs_local_release_inventory(monkeypatch):
    class FakeSyncManager:
        def list_versions(self):
            return {
                'activeDatasetVersion': '2026.06.08.120000',
                'versions': [
                    {'datasetVersion': '2026.06.08.120000', 'active': True, 'packages': ['media', 'library']},
                ],
            }

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore-versions'])

    assert result.exit_code == 0
    assert '2026.06.08.120000' in result.output


def test_activate_appstore_invokes_sync_manager_with_dataset_version(monkeypatch):
    calls = []

    class FakeSyncManager:
        def activate(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'success', 'datasetVersion': kwargs['dataset_version']}

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['activate-appstore', '--dataset-version', '2026.06.08.110000'])

    assert result.exit_code == 0
    assert calls == [{
        'dataset_version': '2026.06.08.110000',
        'trigger': 'cli',
    }]
    assert 'Activated App Store dataset version: 2026.06.08.110000' in result.output