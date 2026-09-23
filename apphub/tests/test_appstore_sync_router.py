"""Contract tests for the App Store sync endpoint.

The console treats `already_running` as a successful no-op, so the endpoint must report that
status instead of spawning a second sync process.
"""
import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router_module = importlib.import_module('src.api.v1.routers.appstore_sync')


def test_sync_endpoint_reports_already_running_without_starting_a_second_sync(monkeypatch):
    class RunningSyncManager:
        def is_sync_running(self):
            return True

        def sync(self, **_kwargs):
            raise AssertionError('a second App Store sync must not be started')

    monkeypatch.setattr(router_module, 'AppStoreSyncManager', RunningSyncManager)

    assert router_module.sync_appstore_assets(channel=None, package_types=None, force_refresh=False) == {
        'status': 'already_running',
        'message': 'An App Store sync is already running in the background.',
    }


def test_sync_endpoint_delegates_when_no_sync_is_running(monkeypatch):
    calls = []

    class IdleSyncManager:
        def is_sync_running(self):
            return False

        def sync(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'accepted', 'message': 'App Store sync started in background.'}

    monkeypatch.setattr(router_module, 'AppStoreSyncManager', IdleSyncManager)

    result = router_module.sync_appstore_assets(channel='rc', package_types='media,library', force_refresh=True)

    assert calls == [{
        'trigger': 'manual',
        'channel': 'rc',
        'package_types': 'media,library',
        'force_refresh': True,
    }]
    assert result['status'] == 'accepted'
