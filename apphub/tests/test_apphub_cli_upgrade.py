import sys
import types
from pathlib import Path

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import forget_modules_imported_since as _forget_modules_imported_since
from support_module_stubs import snapshot_modules as _snapshot_modules

_stubbed_previous = {}
_stubbed_names = []


def _stub(name, module, override=False):
    if name not in _stubbed_previous:
        _stubbed_previous[name] = sys.modules.get(name)
        _stubbed_names.append(name)
    if override or name not in sys.modules:
        sys.modules[name] = module


def _restore_stubs():
    for name in _stubbed_names:
        previous = _stubbed_previous[name]
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    _stubbed_names.clear()
    _stubbed_previous.clear()


# The CLI pulls in services that need Docker, git and a live keyring. Stand-ins keep that import
# cheap, but they must not survive this module: a leftover fake `src.services.app_status` breaks
# every later test module that imports the real package, so the entries are restored as soon as the
# CLI has captured the names it needs.
_modules_before_stubs = _snapshot_modules()
_stub('aiodocker', types.ModuleType('aiodocker'))


git_module = types.ModuleType('git')
git_module.Repo = object
_stub('git', git_module)

apikey_manager_module = types.ModuleType('src.services.apikey_manager')


class _APIKeyManager:
    def generate_key(self):
        return 'dummy'

    def get_key(self):
        return 'dummy'


apikey_manager_module.APIKeyManager = _APIKeyManager
_stub('src.services.apikey_manager', apikey_manager_module)

settings_manager_module = types.ModuleType('src.services.settings_manager')


class _SettingsManager:
    def write_section(self, *args, **kwargs):
        return None


settings_manager_module.SettingsManager = _SettingsManager
_stub('src.services.settings_manager', settings_manager_module)

# `src.core.exception` is deliberately not stubbed: it only needs the standard library, and every
# service module binds `CustomException` from it at import time. A stand-in here would follow the
# CLI import chain into `src.services.scheduled_tasks` and friends, where the fake class then
# shadowed the real one for every later test module in the same pytest process.

config_module = types.ModuleType('src.core.config')
config_module.ConfigManager = object
_stub('src.core.config', config_module)

integration_credentials_module = types.ModuleType('src.services.integration_credentials')
integration_credentials_module.IntegrationCredentialProvider = object
_stub('src.services.integration_credentials', integration_credentials_module)

app_status_module = types.ModuleType('src.services.app_status')


class _InstallStateStore:
    def __init__(self, *args, **kwargs):
        pass


def _utc_now():
    return '2026-01-01T00:00:00Z'


app_status_module.InstallStateStore = _InstallStateStore
app_status_module._utc_now = _utc_now
_stub('src.services.app_status', app_status_module, override=True)

appstore_sync_manager_module = types.ModuleType('src.services.appstore_sync_manager')


class _AppStoreSyncManager:
    def sync(self, *args, **kwargs):
        return {'status': 'success', 'datasetVersion': '2026.06.08.120000'}

    def list_versions(self, *args, **kwargs):
        return {'activeDatasetVersion': '2026.06.08.120000', 'versions': []}

    def activate(self, *args, **kwargs):
        return {'status': 'success', 'datasetVersion': kwargs.get('dataset_version', '2026.06.08.120000')}


appstore_sync_manager_module.AppStoreSyncManager = _AppStoreSyncManager
_stub('src.services.appstore_sync_manager', appstore_sync_manager_module)

from src.cli import apphub_cli as cli_module

_restore_stubs()
# The CLI import chain bound the stand-ins into most of `src.cli` and `src.services`, so those
# modules have to be rebuilt for later test modules (they patch the real classes). `cli_module`
# itself stays as imported: these tests drive it through this reference.
_forget_modules_imported_since(_modules_before_stubs, protect=("src.core.",))


def test_upgrade_apps_is_a_deprecated_no_op(monkeypatch):
    class UnexpectedSyncManager:
        def sync(self, **kwargs):
            raise AssertionError('AppStoreSyncManager.sync must not be called by the deprecated upgrade command')

    monkeypatch.setattr(cli_module, 'AppStoreSyncManager', UnexpectedSyncManager)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ['upgrade', 'apps', '--channel', 'dev', '--force-refresh'])

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
    result = runner.invoke(cli_module.cli, ['appstore', 'sync', '--channel', 'dev'])

    assert result.exit_code == 0
    assert calls == [
        {
            'trigger': 'cli',
            'channel': 'dev',
            'package_types': 'media,library',
            'force_refresh': False,
            'background': False,
        }
    ]
    assert 'App Store resources (dev) synchronized successfully: 2026.06.08.120000' in result.output


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
    assert calls == [
        {
            'trigger': 'cli',
            'channel': None,
            'package_types': 'media,library',
            'force_refresh': False,
            'background': False,
        }
    ]
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
    assert calls == [
        {
            'trigger': 'cli',
            'channel': 'dev',
            'package_types': 'media,library',
            'force_refresh': False,
            'background': True,
        }
    ]
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
