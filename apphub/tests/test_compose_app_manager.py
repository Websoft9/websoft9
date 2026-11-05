"""`ComposeAppManager`: the lifecycle of custom compose apps.

Custom compose apps are ordinary Portainer stacks plus a metadata repository, so almost every rule
here is about *which* stacks may be managed and *what* happens when one of the two backends fails.
The tests keep the orchestration real and replace Portainer, Gitea and the Docker daemon.
"""

import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import docker
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import restore_module_stubs, stub_module

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='compose-app-tests-'))

git_module = types.ModuleType('git')
git_module.Repo = object
git_module.Actor = object
git_module.GitCommandError = RuntimeError
stub_module('git', git_module)
stub_module('jwt', types.ModuleType('jwt'))
keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
stub_module('keyring', keyring_module)

from src.core.exception import CustomException
from src.services import app_manager as app_manager_module
from src.services import compose_app_manager as compose_module
from src.services.compose_app_manager import ComposeAppManager
from src.services.image_pull import ImagePullError

restore_module_stubs()


class FakePortainer:
    def __init__(self):
        self.stacks = {
            'shop': {'Id': 12, 'Name': 'shop', 'Status': 1, 'GitConfig': {'URL': 'http://gitea/shop.git'}},
        }
        self.calls = []
        self.removal_error = None

    def get_local_endpoint_id(self):
        return 21

    def get_stacks(self, endpoint_id):
        return list(self.stacks.values())

    def get_stack_by_name(self, app_id, endpoint_id):
        return self.stacks.get(app_id)

    def start_stack(self, app_id, endpoint_id):
        self.calls.append(('start', app_id, endpoint_id))

    def stop_stack(self, app_id, endpoint_id):
        self.calls.append(('stop', app_id, endpoint_id))

    def restart_stack(self, app_id, endpoint_id):
        self.calls.append(('restart', app_id, endpoint_id))

    def up_stack(self, stack_id, endpoint_id):
        self.calls.append(('up', stack_id, endpoint_id))

    def redeploy_stack(self, *args):
        self.calls.append(('redeploy', *args))

    def remove_stack_and_volumes(self, stack_id, endpoint_id):
        if self.removal_error:
            raise self.removal_error
        self.calls.append(('remove_stack', stack_id, endpoint_id))

    def remove_vloumes(self, app_id, endpoint_id):
        self.calls.append(('remove_volumes', app_id, endpoint_id))


class FakeGitea:
    def __init__(self):
        self.files = {
            'docker-compose.yml': 'services:\n  web:\n    image: websoft9dev/shop:1.0\n',
            '.env': 'DB_PASSWORD=secret\nW9_HTTP_PORT=8080\nEMPTY=\n',
        }
        self.listings = {
            'shop': {
                'all_entries': [
                    {'type': 'file', 'path': 'config/nginx.conf'},
                    {'type': 'file', 'path': 'src/web.conf'},
                    {'type': 'file', 'path': 'src/.websoft9/compose-metadata.json'},
                    {'type': 'file', 'path': 'src/broken.conf'},
                    {'type': 'dir', 'path': 'src/dir'},
                ]
            }
        }
        self.repo_exists = True
        self.removed = []
        self.remove_error = None

    def get_file_raw_from_repo(self, app_id, path):
        return self.files.get(path)

    def list_repo_files(self, app_id):
        return self.listings.get(app_id, {})

    def read_repo_text_file(self, app_id, path):
        if path == 'src/broken.conf':
            raise RuntimeError('unreadable')
        return {'content': f'# {path}'}

    def check_repo_exists(self, app_id):
        return self.repo_exists

    def remove_repo(self, app_id):
        if self.remove_error:
            raise self.remove_error
        self.removed.append(app_id)


class FakeDockerClient:
    def __init__(self, locally_available):
        self.locally_available = set(locally_available)
        self.images = self

    def get(self, image):
        if image in self.locally_available:
            return {'image': image}
        raise docker.errors.ImageNotFound('not local')


@pytest.fixture
def compose(monkeypatch):
    portainer = FakePortainer()
    gitea = FakeGitea()
    monkeypatch.setattr(compose_module, 'PortainerManager', lambda *args, **kwargs: portainer)
    monkeypatch.setattr(compose_module, 'GiteaManager', lambda *args, **kwargs: gitea)
    monkeypatch.setattr(
        compose_module,
        'IntegrationCredentialProvider',
        lambda *args, **kwargs: SimpleNamespace(
            get_gitea_credentials=lambda: SimpleNamespace(username='git', password='secret')
        ),
    )

    state = SimpleNamespace(is_compose_app=True, app_id='shop')
    monkeypatch.setattr(
        app_manager_module.AppManger,
        'get_app_by_id',
        lambda self, app_id, *args, **kwargs: SimpleNamespace(app_id=app_id, is_compose_app=state.is_compose_app),
    )

    pulled = []
    monkeypatch.setattr(compose_module, 'collect_compose_images', lambda content, env: ['websoft9dev/shop:1.0'])
    monkeypatch.setattr(
        compose_module,
        'pull_with_fallback',
        lambda client, image: pulled.append(image),
    )
    docker_client = FakeDockerClient(locally_available=set())
    monkeypatch.setattr(compose_module.docker, 'DockerClient', lambda **kwargs: docker_client)

    return SimpleNamespace(
        manager=ComposeAppManager(),
        portainer=portainer,
        gitea=gitea,
        docker=docker_client,
        pulled=pulled,
        state=state,
        monkeypatch=monkeypatch,
    )


# ── Content ────────────────────────────────────────────────────────────────


def test_compose_content_hides_platform_variables_and_lists_mounts(compose):
    content = compose.manager.get_compose_content('shop')

    assert content['compose_content'].startswith('services:')
    # W9_* 是平台内部变量,不暴露给用户;空值变量保持原样(用户自己写的占位符)
    assert content['env'] == [
        {'key': 'DB_PASSWORD', 'value': 'secret'},
        {'key': 'EMPTY', 'value': ''},
    ]
    # 只收集 src/ 下的普通文件,并跳过内部元数据目录和读不到的文件
    assert content['mounts'] == [{'path': 'src/web.conf', 'content': '# src/web.conf'}]


def test_compose_content_requires_a_compose_file(compose):
    compose.gitea.files.pop('docker-compose.yml')

    with pytest.raises(CustomException) as error:
        compose.manager.get_compose_content('shop')

    assert error.value.status_code == 404
    assert error.value.details == "docker-compose.yml not found in Gitea repo 'shop'"


def test_compose_content_survives_an_unreadable_repo_listing(compose):
    def failing_listing(app_id):
        raise RuntimeError('gitea down')

    compose.gitea.list_repo_files = failing_listing

    assert compose.manager.get_compose_content('shop')['mounts'] == []


# ── Listing and detail ─────────────────────────────────────────────────────


def test_listing_only_returns_compose_apps(compose):
    compose.portainer.stacks['plain'] = {'Id': 13, 'Name': 'plain', 'Status': 1}

    original = app_manager_module.AppManger.get_app_by_id
    compose.monkeypatch.setattr(
        app_manager_module.AppManger,
        'get_app_by_id',
        lambda self, app_id, *args, **kwargs: SimpleNamespace(
            app_id=app_id, is_compose_app=original.__get__(self)(app_id).is_compose_app and app_id == 'shop'
        ),
    )

    apps = compose.manager.list_compose_apps(endpoint_id=21)

    assert [app.app_id for app in apps] == ['shop']


def test_listing_skips_an_app_whose_inspection_fails(compose):
    compose.portainer.stacks['broken'] = {
        'Id': 14,
        'Name': 'broken',
        'Status': 1,
        'GitConfig': {'URL': 'http://gitea/broken.git'},
    }
    original = app_manager_module.AppManger.get_app_by_id

    def get_app(self, app_id, *args, **kwargs):
        if app_id == 'broken':
            raise CustomException(500, 'Internal Server Error', 'portainer hiccup')
        return SimpleNamespace(app_id=app_id, is_compose_app=True)

    compose.monkeypatch.setattr(app_manager_module.AppManger, 'get_app_by_id', get_app)

    apps = compose.manager.list_compose_apps(endpoint_id=21)

    # 一个应用探测失败不能把整个列表变成 500
    assert [app.app_id for app in apps] == ['shop']
    assert original is not None


def test_listing_skips_apps_that_fail_to_load(compose):
    compose.portainer.stacks['broken'] = {'Id': 14, 'Name': 'broken', 'Status': 1}
    original = app_manager_module.AppManger.get_app_by_id

    def get_app(self, app_id, *args, **kwargs):
        if app_id == 'shop':
            return SimpleNamespace(app_id=app_id, is_compose_app=True)
        if app_id == 'broken':
            raise CustomException(500, 'Internal Server Error', 'boom')
        return original.__get__(self)(app_id, *args, **kwargs)

    compose.monkeypatch.setattr(app_manager_module.AppManger, 'get_app_by_id', get_app)

    apps = compose.manager.list_compose_apps(endpoint_id=21)

    assert [app.app_id for app in apps] == ['shop']


def test_detail_rejects_an_unknown_stack(compose):
    with pytest.raises(CustomException) as error:
        compose.manager.get_compose_app('missing', endpoint_id=21)

    assert error.value.status_code == 404
    assert error.value.details == "Compose app 'missing' not found"


def test_detail_rejects_a_non_compose_app(compose):
    compose.state.is_compose_app = False

    with pytest.raises(CustomException) as error:
        compose.manager.get_compose_app('shop', endpoint_id=21)

    assert error.value.status_code == 400
    assert error.value.details == "'shop' is not a custom compose application"


def test_detail_returns_the_app(compose):
    assert compose.manager.get_compose_app('shop', endpoint_id=21).app_id == 'shop'


# ── Start / stop / restart ─────────────────────────────────────────────────


@pytest.mark.parametrize('method', ['start_compose_app', 'stop_compose_app', 'restart_compose_app'])
def test_lifecycle_actions_reach_portainer(compose, method):
    getattr(compose.manager, method)('shop', endpoint_id=21)

    assert compose.portainer.calls == [(method.replace('_compose_app', ''), 'shop', 21)]


def test_lifecycle_actions_refuse_a_non_compose_app(compose):
    compose.state.is_compose_app = False

    with pytest.raises(CustomException) as error:
        compose.manager.start_compose_app('shop', endpoint_id=21)

    assert error.value.status_code == 400
    assert compose.portainer.calls == []


# ── Image pre-pull ─────────────────────────────────────────────────────────


def test_pre_pull_skips_a_repository_without_compose_file(compose):
    compose.gitea.files.pop('docker-compose.yml')

    assert compose.manager._pull_stack_images('shop', compose.gitea) == []
    assert compose.pulled == []


def test_pre_pull_skips_images_that_are_already_local(compose):
    compose.docker.locally_available.add('websoft9dev/shop:1.0')

    assert compose.manager._pull_stack_images('shop', compose.gitea) == []
    assert compose.pulled == []


def test_pre_pull_pulls_a_missing_image_through_the_accelerator_chain(compose):
    assert compose.manager._pull_stack_images('shop', compose.gitea) == ['websoft9dev/shop:1.0']
    assert compose.pulled == ['websoft9dev/shop:1.0']


def test_pre_pull_rejects_an_invalid_image_reference(compose):
    compose.monkeypatch.setattr(compose_module, 'collect_compose_images', lambda content, env: ['Not A Reference'])

    with pytest.raises(ImagePullError):
        compose.manager._pull_stack_images('shop', compose.gitea)
    assert compose.pulled == []


def test_redeploy_reports_an_interpolated_image_as_a_pull_error(compose):
    compose.monkeypatch.setattr(compose_module, 'collect_compose_images', lambda content, env: [''])

    with pytest.raises(CustomException) as error:
        compose.manager.redeploy_compose_app('shop', endpoint_id=21)

    assert error.value.status_code == 502
    assert 'Invalid image reference' in error.value.details


# ── Redeploy ───────────────────────────────────────────────────────────────


def test_redeploy_of_an_active_stack_asks_portainer_not_to_pull(compose):
    compose.manager.redeploy_compose_app('shop', endpoint_id=21)

    assert ('redeploy', 12, 21, False, 'git', 'secret') in compose.portainer.calls
    assert compose.pulled == ['websoft9dev/shop:1.0']


def test_redeploy_of_an_inactive_stack_restores_it(compose):
    compose.portainer.stacks['shop']['Status'] = 2

    compose.manager.redeploy_compose_app('shop', endpoint_id=21)

    assert ('up', 12, 21) in compose.portainer.calls
    assert not any(call[0] == 'redeploy' for call in compose.portainer.calls)


def test_redeploy_without_pull_skips_the_pre_pull(compose):
    compose.manager.redeploy_compose_app('shop', endpoint_id=21, pull_image=False)

    assert compose.pulled == []


def test_redeploy_maps_an_image_pull_failure_to_a_502(compose):
    def failing_pull(client, image):
        raise ImagePullError('manifest unknown')

    compose.monkeypatch.setattr(compose_module, 'pull_with_fallback', failing_pull)

    with pytest.raises(CustomException) as error:
        compose.manager.redeploy_compose_app('shop', endpoint_id=21)

    assert error.value.status_code == 502
    assert error.value.message == 'Image Pull Error'
    assert error.value.details == 'manifest unknown'
    assert not any(call[0] in {'redeploy', 'up'} for call in compose.portainer.calls)


def test_redeploy_rejects_a_stack_without_an_id(compose):
    compose.portainer.stacks['shop']['Id'] = None

    with pytest.raises(CustomException) as error:
        compose.manager.redeploy_compose_app('shop', endpoint_id=21, pull_image=False)

    assert error.value.status_code == 404
    assert error.value.details == "Portainer stack for 'shop' has no Id"


# ── Remove ─────────────────────────────────────────────────────────────────


def test_remove_drops_the_stack_volumes_and_the_repository(compose):
    compose.manager.remove_compose_app('shop', endpoint_id=21)

    assert ('remove_stack', 12, 21) in compose.portainer.calls
    assert compose.gitea.removed == ['shop']


def test_remove_falls_back_to_volume_cleanup_when_the_stack_removal_fails(compose):
    compose.portainer.removal_error = RuntimeError('portainer refused')

    compose.manager.remove_compose_app('shop', endpoint_id=21)

    # 栈删不掉时至少把卷清掉,否则下一次同名安装会被残留数据污染
    assert ('remove_volumes', 'shop', 21) in compose.portainer.calls
    assert compose.gitea.removed == ['shop']


def test_remove_keeps_going_when_the_repository_deletion_fails(compose):
    compose.gitea.remove_error = RuntimeError('gitea refused')

    compose.manager.remove_compose_app('shop', endpoint_id=21)

    assert ('remove_stack', 12, 21) in compose.portainer.calls


def test_remove_skips_a_missing_repository(compose):
    compose.gitea.repo_exists = False

    compose.manager.remove_compose_app('shop', endpoint_id=21)

    assert compose.gitea.removed == []


def test_remove_refuses_a_non_compose_app(compose):
    compose.state.is_compose_app = False

    with pytest.raises(CustomException) as error:
        compose.manager.remove_compose_app('shop', endpoint_id=21)

    assert error.value.status_code == 400
    assert compose.portainer.calls == []
    assert compose.gitea.removed == []
