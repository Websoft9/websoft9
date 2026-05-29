import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
sys.modules.setdefault('jwt', types.ModuleType('jwt'))
sys.modules.setdefault('keyring', types.ModuleType('keyring'))

git_module = types.ModuleType('git')
git_module.Repo = object
sys.modules.setdefault('git', git_module)

from src.services import apps_stream_cache as apps_stream_cache_module
from src.services.apps_stream_cache import AppsStreamCache


def test_apps_stream_cache_reuses_snapshot_before_refresh_deadline(monkeypatch):
    calls: list[tuple[int | None, str]] = []

    class FakeAppManager:
        def get_apps(self, endpoint_id, locale):
            calls.append((endpoint_id, locale))
            return [{'app_id': 'wordpress', 'status': 1}]

    cache = AppsStreamCache()
    monkeypatch.setattr(apps_stream_cache_module, '_build_app_manager', FakeAppManager)

    first = cache.get_snapshot(None, 'zh', force_refresh=True)
    second = cache.get_snapshot(None, 'zh')

    assert first.apps == [{'app_id': 'wordpress', 'status': 1}]
    assert second.digest == first.digest
    assert calls == [(None, 'zh')]
    assert first.refresh_interval_seconds == 5.0


def test_apps_stream_cache_uses_fast_refresh_while_installing(monkeypatch):
    class FakeAppManager:
        def get_apps(self, endpoint_id, locale):
            return [{'app_id': 'wordpress', 'status': 3}]

    cache = AppsStreamCache()
    monkeypatch.setattr(apps_stream_cache_module, '_build_app_manager', FakeAppManager)

    snapshot = cache.get_snapshot(None, 'en', force_refresh=True)

    assert snapshot.refresh_interval_seconds == 3.0
    assert 'refresh_hint_ms' in snapshot.event_json


def test_apps_stream_cache_serves_stale_snapshot_on_refresh_failure(monkeypatch):
    responses = [
        [{'app_id': 'wordpress', 'status': 1}],
        RuntimeError('boom'),
    ]

    class FakeAppManager:
        def get_apps(self, endpoint_id, locale):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    monotonic_values = iter([10.0, 40.0])
    cache = AppsStreamCache()
    monkeypatch.setattr(apps_stream_cache_module, '_build_app_manager', FakeAppManager)
    monkeypatch.setattr(apps_stream_cache_module.time, 'monotonic', lambda: next(monotonic_values))

    first = cache.get_snapshot(None, 'en', force_refresh=True)
    second = cache.get_snapshot(None, 'en')

    assert second.apps == first.apps
    assert second.digest == first.digest