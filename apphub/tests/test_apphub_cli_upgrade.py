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

app_status_module = types.ModuleType('src.services.app_status')


class _InstallStateStore:
    def __init__(self, *args, **kwargs):
        pass


def _utc_now():
    return '2026-01-01T00:00:00Z'


app_status_module.InstallStateStore = _InstallStateStore
app_status_module._utc_now = _utc_now
sys.modules['src.services.app_status'] = app_status_module

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


def test_upgrade_apps_is_a_deprecated_no_op(monkeypatch):
    class UnexpectedSyncManager:
        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync must not be called by the deprecated upgrade command')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', UnexpectedSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'apps', '--channel', 'rc', '--force-refresh'])

    assert result.exit_code == 0
    assert "'upgrade apps' no longer synchronizes App Store resources" in result.output
    assert 'websoft9 appstore sync' in result.output


def test_upgrade_apps_ignores_dev_flag_and_still_succeeds(monkeypatch):
    class UnexpectedSyncManager:
        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync must not be called by the deprecated upgrade command')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', UnexpectedSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'apps', '--dev'])

    assert result.exit_code == 0
    assert "'upgrade apps' no longer synchronizes App Store resources" in result.output


def test_upgrade_apps_rejects_unknown_target():
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'unknown'])

    assert result.exit_code != 0


def test_appstore_sync_runs_inline_by_default(monkeypatch):
    calls = []

    class FakeSyncManager:
        def is_sync_running(self):
            return False

        def sync(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'success', 'datasetVersion': '2026.06.08.120000'}

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore', 'sync', '--channel', 'rc'])

    assert result.exit_code == 0
    assert calls == [{
        'trigger': 'cli',
        'channel': 'rc',
        'package_types': 'media,library',
        'force_refresh': False,
        'background': False,
    }]
    assert 'App Store resources (rc) synchronized successfully: 2026.06.08.120000' in result.output


def test_appstore_sync_without_channel_uses_metadata_default(monkeypatch):
    calls = []

    class FakeSyncManager:
        def is_sync_running(self):
            return False

        def sync(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'success', 'datasetVersion': '2026.06.08.120000', 'channel': 'release'}

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore', 'sync'])

    assert result.exit_code == 0
    assert calls == [{
        'trigger': 'cli',
        'channel': None,
        'package_types': 'media,library',
        'force_refresh': False,
        'background': False,
    }]
    assert 'App Store resources (release) synchronized successfully: 2026.06.08.120000' in result.output


def test_appstore_sync_dev_flag_resolves_dev_channel_in_no_wait_mode(monkeypatch):
    calls = []

    class FakeSyncManager:
        def is_sync_running(self):
            return False

        def sync(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'accepted', 'message': 'App Store sync started in background.'}

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', FakeSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore', 'sync', '--dev', '--no-wait'])

    assert result.exit_code == 0
    assert calls == [{
        'trigger': 'cli',
        'channel': 'dev',
        'package_types': 'media,library',
        'force_refresh': False,
        'background': True,
    }]
    assert 'started in the background' in result.output


def test_appstore_sync_rejects_conflicting_dev_and_release_channel(monkeypatch):
    class UnexpectedSyncManager:
        def is_sync_running(self):
            return False

        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync should not be called for invalid arguments')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', UnexpectedSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore', 'sync', '--dev', '--channel', 'release'])

    assert result.exit_code != 0
    assert '--dev cannot be combined with a non-dev --channel value' in result.output


def test_appstore_sync_rejects_when_sync_is_already_running(monkeypatch):
    class RunningSyncManager:
        def is_sync_running(self):
            return True

        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync must not be called while a sync is running')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', RunningSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['appstore', 'sync'])

    assert result.exit_code != 0
    assert 'already running' in result.output
