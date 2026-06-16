import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))

git_module = types.ModuleType('git')
git_module.Repo = object
sys.modules.setdefault('git', git_module)

common_check_module = types.ModuleType('src.services.common_check')
common_check_module.check_apps_number = lambda *args, **kwargs: None
common_check_module.check_endpointId = lambda *args, **kwargs: None
sys.modules.setdefault('src.services.common_check', common_check_module)

for module_name, attribute_name in [
    ('src.services.git_manager', 'GitManager'),
    ('src.services.gitea_manager', 'GiteaManager'),
    ('src.services.portainer_manager', 'PortainerManager'),
    ('src.services.integration_credentials', 'IntegrationCredentialProvider'),
    ('src.services.proxy_manager', 'ProxyManager'),
    ('src.utils.file_manager', 'FileHelper'),
    ('src.utils.password_generator', 'PasswordGenerator'),
]:
    module = types.ModuleType(module_name)
    setattr(module, attribute_name, object)
    sys.modules.setdefault(module_name, module)

async_utils_module = types.ModuleType('src.utils.async_utils')
async_utils_module.AsyncWrapper = object
sys.modules.setdefault('src.utils.async_utils', async_utils_module)

app_status_module = types.ModuleType('src.services.app_status')
app_status_module.appInstalling = {}
app_status_module.appInstallingError = {}
app_status_module.start_app_installation = lambda *args, **kwargs: None
app_status_module.remove_app_installation = lambda *args, **kwargs: None
app_status_module.modify_app_information = lambda *args, **kwargs: None
app_status_module.remove_app_from_errors_by_app_id = lambda *args, **kwargs: None
app_status_module.add_installing_logs = lambda *args, **kwargs: None
app_status_module.remove_installation_logs = lambda *args, **kwargs: None
sys.modules.setdefault('src.services.app_status', app_status_module)

if sys.version_info < (3, 10):
    pytestmark = pytest.mark.skip(reason='app_manager media sync tests require Python 3.10+ type syntax support')
    app_manager_module = None
    AppManger = None
else:
    from src.services import app_manager as app_manager_module
    from src.services.app_manager import AppManger


class _UrlopenResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _build_media_archive_bytes() -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive:
        archive.writestr('media/json/product_en.json', json.dumps({'ok': True}))
    return payload.getvalue()


def _patch_path_factory(monkeypatch, metadata_path: Path):
    real_path = Path

    def fake_path(value):
        if str(value) == '/websoft9/version.json':
            return metadata_path
        return real_path(value)

    monkeypatch.setattr(app_manager_module, 'Path', fake_path)


def test_sync_media_assets_uses_rc_channel_for_rc_versions(monkeypatch, tmp_path):
    metadata_path = tmp_path / 'version.json'
    metadata_path.write_text(json.dumps({'version': '2.1.0', 'channel': 'rc'}), encoding='utf-8')
    _patch_path_factory(monkeypatch, metadata_path)

    requested_urls = []
    archive_bytes = _build_media_archive_bytes()

    def fake_urlopen(request):
        requested_urls.append(request.full_url)
        return _UrlopenResponse(archive_bytes)

    monkeypatch.setattr(app_manager_module.urllib.request, 'urlopen', fake_urlopen)

    manager = AppManger()
    base_path = tmp_path / 'media' / 'json'
    manager._sync_media_assets_from_artifact(str(base_path))

    assert requested_urls == ['https://artifact.websoft9.com/rc/websoft9/plugin/media/media-latest.zip']
    assert (tmp_path / 'media' / 'json' / 'product_en.json').exists()


def test_sync_media_assets_uses_dev_channel_for_dev_versions(monkeypatch, tmp_path):
    metadata_path = tmp_path / 'version.json'
    metadata_path.write_text(json.dumps({'version': '2.1.0', 'channel': 'dev'}), encoding='utf-8')
    _patch_path_factory(monkeypatch, metadata_path)

    requested_urls = []
    archive_bytes = _build_media_archive_bytes()

    def fake_urlopen(request):
        requested_urls.append(request.full_url)
        return _UrlopenResponse(archive_bytes)

    monkeypatch.setattr(app_manager_module.urllib.request, 'urlopen', fake_urlopen)

    manager = AppManger()
    base_path = tmp_path / 'media' / 'json'
    manager._sync_media_assets_from_artifact(str(base_path))

    assert requested_urls == ['https://artifact.websoft9.com/dev/websoft9/plugin/media/media-dev.zip']
    assert (tmp_path / 'media' / 'json' / 'product_en.json').exists()