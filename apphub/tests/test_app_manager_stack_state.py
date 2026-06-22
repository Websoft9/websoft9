import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))

git_module = types.ModuleType('git')
git_module.Repo = object
sys.modules.setdefault('git', git_module)

jwt_module = types.ModuleType('jwt')
sys.modules.setdefault('jwt', jwt_module)

keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
sys.modules.setdefault('keyring', keyring_module)

from src.services import app_manager as app_manager_module
from src.services.app_manager import AppManger
from src.services.app_status import appInstalling, appInstallingError


class FakePortainerManager:
    def get_stacks(self, endpoint_id: int):
        return [{"Name": "php_t87jd", "Status": 1, "GitConfig": {}, "CreationDate": 123}]

    def get_containers(self, endpoint_id: int):
        return []

    def get_volumes_by_stack_name(self, stack_name: str, endpoint_id: int, dangling: bool):
        return []

    def get_stack_by_name(self, stack_name: str, endpoint_id: int):
        return {"Id": 8, "Name": stack_name, "Status": 1, "GitConfig": {}, "CreationDate": 123}

    def get_containers_by_stack_name(self, stack_name: str, endpoint_id: int):
        return []


class FakeProxyManager:
    def get_proxy_hosts(self):
        return []

    def get_proxy_host_by_app(self, app_id: str):
        return []


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr(app_manager_module, 'PortainerManager', FakePortainerManager)
    monkeypatch.setattr(app_manager_module, 'ProxyManager', FakeProxyManager)
    monkeypatch.setattr(app_manager_module, 'check_endpointId', lambda endpoint_id, manager: None)
    appInstalling.clear()
    appInstallingError.clear()


def test_get_apps_marks_active_stack_without_containers_as_error(monkeypatch):
    _patch_dependencies(monkeypatch)

    apps = AppManger().get_apps(endpointId=21)

    assert len(apps) == 1
    assert apps[0].app_id == 'php_t87jd'
    assert apps[0].status == 4
    assert apps[0].error == 'No containers were created for this stack.'


def test_get_app_by_id_marks_active_stack_without_containers_as_error(monkeypatch):
    _patch_dependencies(monkeypatch)

    app = AppManger().get_app_by_id('php_t87jd', endpointId=21)

    assert app.app_id == 'php_t87jd'
    assert app.status == 4
    assert app.error == 'No containers were created for this stack.'
    assert app.containers == []


def test_get_apps_preserves_original_install_error(monkeypatch):
    _patch_dependencies(monkeypatch)
    appInstallingError['tracking-1'] = {
        'app_id': 'php_t87jd',
        'app_name': 'wordpress',
        'status': 4,
        'error': 'Failed to deploy a stack: compose up operation failed: network websoft9 declared as external, but could not be found',
    }

    apps = AppManger().get_apps(endpointId=21)

    assert len(apps) == 1
    assert apps[0].app_id == 'php_t87jd'
    assert apps[0].status == 4
    assert apps[0].error == 'Failed to deploy a stack: compose up operation failed: network websoft9 declared as external, but could not be found'