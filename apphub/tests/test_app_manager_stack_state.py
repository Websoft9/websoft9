import sys
import types
import os
import tempfile
from types import SimpleNamespace
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='app-manager-tests-'))

git_module = types.ModuleType('git')
git_module.Repo = object
git_module.GitCommandError = RuntimeError
sys.modules.setdefault('git', git_module)

jwt_module = types.ModuleType('jwt')
sys.modules.setdefault('jwt', jwt_module)

keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
sys.modules.setdefault('keyring', keyring_module)

from src.services import app_manager as app_manager_module
from src.services.app_manager import AppManger
from src.core.exception import CustomException
from src.services.app_status import appInstalling, appInstallingCancelled, appInstallingError, configure_install_state_store, start_app_installation


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


class FakeGiteaManager:
    def check_repo_exists(self, repo_name: str):
        return False


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr(app_manager_module, 'PortainerManager', FakePortainerManager)
    monkeypatch.setattr(app_manager_module, 'ProxyManager', FakeProxyManager)
    monkeypatch.setattr(app_manager_module, 'GiteaManager', FakeGiteaManager)
    monkeypatch.setattr(app_manager_module, 'check_endpointId', lambda endpoint_id, manager: None)


def _clear_install_state():
    for tracking_id, _ in list(appInstalling.items()):
        appInstalling.pop(tracking_id, None)
    for tracking_id, _ in list(appInstallingError.items()):
        appInstallingError.pop(tracking_id, None)


def test_get_apps_marks_active_stack_without_containers_as_error(monkeypatch):
    _patch_dependencies(monkeypatch)
    _clear_install_state()

    apps = AppManger().get_apps(endpointId=21)

    assert len(apps) == 1
    assert apps[0].app_id == 'php_t87jd'
    assert apps[0].status == 4
    assert apps[0].error == 'No containers were created for this stack.'


def test_get_app_by_id_marks_active_stack_without_containers_as_error(monkeypatch):
    _patch_dependencies(monkeypatch)
    _clear_install_state()

    app = AppManger().get_app_by_id('php_t87jd', endpointId=21)

    assert app.app_id == 'php_t87jd'
    assert app.status == 4
    assert app.error == 'No containers were created for this stack.'
    assert app.containers == []


def test_get_apps_preserves_original_install_error(monkeypatch):
    _patch_dependencies(monkeypatch)
    _clear_install_state()
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


def test_get_apps_turns_stale_install_into_visible_error(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    _clear_install_state()

    tracking_id = start_app_installation('wordpress_kaoq9', 'wordpress')
    stale_task = appInstalling[tracking_id]
    stale_task['updated_at'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    appInstalling[tracking_id] = stale_task

    apps = AppManger().get_apps(endpointId=21)

    assert tracking_id not in appInstalling
    errored = dict(appInstallingError.items())[tracking_id]
    assert 'expired before the app stack or repository became available' in errored['error']
    assert any(app.app_id == 'wordpress_kaoq9' and app.status == 4 for app in apps)


def test_failure_survives_running_residue_and_resource_cleanup(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    monkeypatch.setattr(FakePortainerManager, 'get_containers', lambda self, endpoint_id: [
        {'Labels': {'com.docker.compose.project': 'php_t87jd'}, 'State': 'running', 'Names': ['/php_t87jd-worker']},
    ])
    appInstallingError['failed-install'] = {
        'app_id': 'php_t87jd', 'app_name': 'wordpress', 'status': 4,
        'error': 'Proxy configuration failed',
        'logs': [{'title': 'Configuring the domain', 'sub_logs': ['Connection refused']}],
    }
    manager = AppManger()
    monkeypatch.setattr(manager, '_get_available_app_logo_map', lambda locale: {})

    apps = manager.get_apps(endpointId=21)
    assert len(apps) == 1
    assert apps[0].status == 4
    assert apps[0].error == 'Proxy configuration failed'
    assert 'failed-install' in appInstallingError

    monkeypatch.setattr(FakePortainerManager, 'get_stacks', lambda self, endpoint_id: [])
    monkeypatch.setattr(FakePortainerManager, 'get_containers', lambda self, endpoint_id: [])
    configure_install_state_store(str(tmp_path))
    apps = manager.get_apps(endpointId=21)
    assert len(apps) == 1
    assert apps[0].status == 4
    assert apps[0].tracking_id == 'failed-install'
    assert apps[0].logs[0]['sub_logs'][0]['message'] == 'Connection refused'


def test_cancelled_install_survives_running_residue(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    monkeypatch.setattr(FakePortainerManager, 'get_containers', lambda self, endpoint_id: [
        {'Labels': {'com.docker.compose.project': 'php_t87jd'}, 'State': 'running'},
    ])
    appInstallingCancelled['cancelled-install'] = {'app_id': 'php_t87jd', 'app_name': 'wordpress', 'status': 6}
    manager = AppManger()
    monkeypatch.setattr(manager, '_get_available_app_logo_map', lambda locale: {})
    apps = manager.get_apps(endpointId=21)
    assert len(apps) == 1
    assert apps[0].status == 6
    assert 'cancelled-install' in appInstallingCancelled


def test_detail_query_cannot_delete_failure_record(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    monkeypatch.setattr(FakePortainerManager, 'get_containers_by_stack_name', lambda self, app_id, endpoint_id: [
        {'State': 'running', 'Names': ['/php_t87jd-worker']},
    ])
    appInstallingError['failed-install'] = {'app_id': 'php_t87jd', 'app_name': 'wordpress', 'status': 4, 'error': 'Proxy configuration failed'}
    manager = AppManger()
    monkeypatch.setattr(manager, '_read_compose_metadata_safe', lambda app_id: {})
    detail = manager.get_app_by_id('php_t87jd', endpointId=21)
    assert detail.error == 'Proxy configuration failed'
    assert 'failed-install' in appInstallingError


def test_retry_hides_but_does_not_delete_previous_failure(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    appInstallingError['previous-failure'] = {'app_id': 'php_t87jd', 'app_name': 'wordpress', 'status': 4, 'error': 'Previous failure'}
    start_app_installation('php_t87jd', 'wordpress')
    manager = AppManger()
    monkeypatch.setattr(manager, '_get_available_app_logo_map', lambda locale: {})
    apps = manager.get_apps(endpointId=21)
    assert len(apps) == 1
    assert apps[0].status == 3
    assert 'previous-failure' in appInstallingError


def test_install_entrypoint_persists_unexpected_initialization_failure(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    def fail_portainer():
        raise RuntimeError('Portainer unavailable')
    monkeypatch.setattr(app_manager_module, 'PortainerManager', fail_portainer)
    payload = SimpleNamespace(app_id='php_t87jd', app_name='wordpress')
    tracking_id = start_app_installation(payload.app_id, payload.app_name)
    with pytest.raises(RuntimeError, match='Portainer unavailable'):
        AppManger().install_app(payload, endpointId=21, tracking_id=tracking_id)
    assert tracking_id not in appInstalling
    assert appInstallingError[tracking_id]['error'] == 'Portainer unavailable'


def test_rollback_failure_cannot_replace_original_install_error(monkeypatch, tmp_path):
    configure_install_state_store(str(tmp_path))
    _patch_dependencies(monkeypatch)
    monkeypatch.setattr(FakeGiteaManager, 'create_repo', lambda self, app_id: 'http://repository.git', raising=False)
    def fail_cleanup(self, app_id):
        raise RuntimeError('Repository cleanup failed')
    def fail_configuration(*args):
        raise CustomException(400, 'Invalid configuration', 'yaml: invalid application configuration')
    monkeypatch.setattr(FakeGiteaManager, 'remove_repo', fail_cleanup, raising=False)
    monkeypatch.setattr(app_manager_module, 'is_external_database_profile', fail_configuration)
    payload = SimpleNamespace(app_id='php_t87jd', app_name='wordpress', edition=SimpleNamespace(version='1'), proxy_enabled=False, domain_names=[], settings={}, profile=None)
    tracking_id = start_app_installation(payload.app_id, payload.app_name)
    with pytest.raises(RuntimeError, match='Repository cleanup failed'):
        AppManger().install_app(payload, endpointId=21, tracking_id=tracking_id, library_path=str(tmp_path))
    assert appInstallingError[tracking_id]['error'] == 'yaml: invalid application configuration'
    assert appInstallingError[tracking_id]['logs'][0]['title'] == 'Initializing installation'