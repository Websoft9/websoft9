"""`AppManger.redeploy_app`: restoring an inactive stack versus re-pulling and recreating an active
one.

Redeploy is the recovery path operators reach for when an app is broken, so its three outcomes have
to stay distinct: an inactive stack is brought back with `up_stack`, an active stack goes through the
git clone / image pull / `redeploy_stack` sequence, and a repository without a compose file fails
with a readable 404 instead of an opaque 500.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import types
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import restore_module_stubs, stub_module

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='app-manager-redeploy-'))

git_module = types.ModuleType('git')
git_module.Repo = object
git_module.GitCommandError = RuntimeError
stub_module('git', git_module)

jwt_module = types.ModuleType('jwt')
stub_module('jwt', jwt_module)

keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
stub_module('keyring', keyring_module)

from src.core.exception import CustomException
from src.services import app_manager as app_manager_module
from src.services.app_manager import AppManger

restore_module_stubs()


class FakeDockerError(Exception):
    """Mirrors `aiodocker.exceptions.DockerError` for the local-image lookup."""


class FakeAsyncDocker:
    def __init__(self):
        self.pulled = []
        self.closed = False
        self.existing = set()
        self.images = self

    async def get(self, image):
        if image in self.existing:
            return {'image': image}
        raise FakeDockerError('no such image')

    async def close(self):
        self.closed = True


class FakeAsyncWrapper:
    calls = []

    @staticmethod
    async def run_sync(func, *args, **kwargs):
        FakeAsyncWrapper.calls.append((getattr(func, '__name__', str(func)), args, kwargs))
        # 调用真正的目标函数(这里是假 Portainer 的方法),否则测不到它是否被触发、参数是否正确。
        return func(*args, **kwargs)


class FakeCredentials:
    username = 'git'
    password = 'secret'


class FakeCredentialProvider:
    def get_gitea_credentials(self):
        return FakeCredentials()


class FakeGitManager:
    """Replaces the clone with whatever compose file the test asked for."""

    cloned = []
    compose_content = None

    def __init__(self, local_path):
        self.local_path = local_path

    def clone_remote_repo_to_local(self, url, username, password):
        FakeGitManager.cloned.append((self.local_path, url))
        os.makedirs(self.local_path, exist_ok=True)
        if FakeGitManager.compose_content is not None:
            with open(os.path.join(self.local_path, 'docker-compose.yml'), 'w') as handle:
                handle.write(FakeGitManager.compose_content)


class FakeEnvHelper:
    def __init__(self, path):
        self.path = path


class FakePortainer:
    def __init__(self):
        self.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 1}
        self.stack_exists = True
        self.up_calls = []
        self.redeploy_calls = []
        self.up_error = None

    def get_local_endpoint_id(self):
        return 21

    def check_stack_exists(self, app_id, endpoint_id):
        return self.stack_exists

    def get_stack_by_name(self, app_id, endpoint_id):
        return self.stack

    def up_stack(self, stack_id, endpoint_id, **kwargs):
        self.up_calls.append((stack_id, endpoint_id))
        if self.up_error:
            raise self.up_error

    def redeploy_stack(self, *args, **kwargs):
        self.redeploy_calls.append(args)


@pytest.fixture
def redeploy(monkeypatch, tmp_path):
    portainer = FakePortainer()
    docker_client = FakeAsyncDocker()
    proxy = SimpleNamespace(updated=[], update_proxy_port_by_app=lambda pid, port: proxy.updated.append((pid, port)))

    monkeypatch.setattr(app_manager_module, 'PortainerManager', lambda *args, **kwargs: portainer)
    monkeypatch.setattr(app_manager_module, 'ProxyManager', lambda *args, **kwargs: proxy)
    monkeypatch.setattr(app_manager_module, 'IntegrationCredentialProvider', FakeCredentialProvider)
    monkeypatch.setattr(app_manager_module, 'GitManager', FakeGitManager)
    monkeypatch.setattr(app_manager_module, 'EnvHelper', FakeEnvHelper)
    monkeypatch.setattr(app_manager_module, 'AsyncWrapper', FakeAsyncWrapper)
    monkeypatch.setattr(app_manager_module, 'check_endpointId', lambda endpoint_id, manager: None)
    monkeypatch.setattr(AppManger, '_replace_env_variables', lambda self, text, helper: text)
    monkeypatch.setattr(app_manager_module.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(
        app_manager_module,
        'aiodocker',
        SimpleNamespace(
            Docker=lambda *args, **kwargs: docker_client,
            exceptions=SimpleNamespace(DockerError=FakeDockerError),
        ),
    )

    pulls = []

    async def fake_pull(client, image, log=None):
        pulls.append(image)
        return image

    monkeypatch.setattr(app_manager_module, 'pull_with_fallback_async', fake_pull)
    FakeAsyncWrapper.calls = []
    FakeGitManager.cloned = []

    # `redeploy_app` builds its own `AppManger()`, so the inventory has to be patched on the class.
    # The inventory has to mention the app being redeployed, hence the mutable holder.
    state = SimpleNamespace(app_id='wordpress_abc')
    monkeypatch.setattr(
        AppManger,
        'get_apps',
        lambda self, *args, **kwargs: [
            SimpleNamespace(
                app_id=state.app_id,
                app_official=True,
                status=1,
                gitConfig={'URL': f'http://gitea.local/git/{state.app_id}.git'},
            )
        ],
    )
    monkeypatch.setattr(
        AppManger,
        'get_app_by_id',
        lambda self, app_id, *args, **kwargs: SimpleNamespace(domain_names=[], env={}, app_id=app_id),
    )
    manager = AppManger()

    return SimpleNamespace(
        state=state,
        manager=manager,
        portainer=portainer,
        docker=docker_client,
        proxy=proxy,
        pulls=pulls,
        monkeypatch=monkeypatch,
        app_id='wordpress_abc',
    )


def _workspace(app_id):
    path = Path(f'/tmp/{app_id}')
    return path


@pytest.fixture
def compose_workspace(redeploy):
    """Runs one redeploy against a fresh `/tmp/<app_id>` workspace.

    The compose file is written by the fake clone, because `redeploy_app` deletes any pre-existing
    `/tmp/<app_id>` before cloning.
    """
    app_id = f'redeploy-test-{uuid.uuid4().hex[:8]}'
    redeploy.state.app_id = app_id
    path = _workspace(app_id)
    FakeGitManager.compose_content = None

    def prepare(compose_content):
        FakeGitManager.compose_content = compose_content

    yield app_id, prepare

    FakeGitManager.compose_content = None
    if path.exists():
        shutil.rmtree(path)


def test_redeploy_rejects_an_unknown_stack(redeploy):
    redeploy.portainer.stack_exists = False

    with pytest.raises(CustomException) as error:
        asyncio.run(redeploy.manager.redeploy_app('wordpress_abc', False, 21))

    assert error.value.status_code == 400
    assert error.value.details == 'wordpress_abc Not Found'


def test_redeploy_restores_an_inactive_stack_without_recloning(redeploy):
    redeploy.portainer.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 2}
    logs = []

    class Queue:
        async def put(self, message):
            logs.append(message)

    asyncio.run(redeploy.manager.redeploy_app('wordpress_abc', False, 21, Queue()))

    assert redeploy.portainer.up_calls == [(8, 21)]
    assert redeploy.portainer.redeploy_calls == []
    assert FakeGitManager.cloned == []
    assert logs == [
        'Initializing Redeployment',
        'Verify Application Status',
        'Restoring inactive stack',
        'Redeployment complete',
    ]


def test_redeploy_propagates_a_failed_restore(redeploy):
    redeploy.portainer.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 2}

    async def failing_run_sync(func, *args, **kwargs):
        raise CustomException(500, 'Portainer Error', 'up_stack timed out')

    redeploy.monkeypatch.setattr(app_manager_module.AsyncWrapper, 'run_sync', staticmethod(failing_run_sync))
    logs = []

    class Queue:
        async def put(self, message):
            logs.append(message)

    with pytest.raises(CustomException) as error:
        asyncio.run(redeploy.manager.redeploy_app('wordpress_abc', False, 21, Queue()))

    assert error.value.details == 'up_stack timed out'
    assert any('Restore stack error' in message for message in logs)


def test_redeploy_reports_a_repository_without_compose_file(redeploy, compose_workspace):
    app_id, prepare = compose_workspace
    prepare(None)

    with pytest.raises(CustomException) as error:
        asyncio.run(redeploy.manager.redeploy_app(app_id, False, 21))

    assert error.value.status_code == 404
    assert error.value.details == 'docker-compose.yml not found in the application directory'


def test_redeploy_pulls_a_missing_image_and_recreates_the_stack(redeploy, compose_workspace):
    app_id, prepare = compose_workspace
    prepare('services:\n  web:\n    image: websoft9dev/wordpress:6.5\n  builder:\n    build: .\n')

    asyncio.run(redeploy.manager.redeploy_app(app_id, False, 21))

    # The missing image is pulled, the `build:` service is skipped, and Portainer is told not to pull.
    assert redeploy.pulls == ['websoft9dev/wordpress:6.5']
    assert redeploy.docker.closed is True
    assert len(redeploy.portainer.redeploy_calls) == 1
    assert redeploy.portainer.redeploy_calls[0][2] is False
    assert FakeGitManager.cloned[0][0] == f'/tmp/{app_id}'
    assert not _workspace(app_id).exists()


def test_redeploy_skips_the_pull_when_the_image_is_already_local(redeploy, compose_workspace):
    app_id, prepare = compose_workspace
    prepare('services:\n  web:\n    image: websoft9dev/wordpress:6.5\n')
    redeploy.docker.existing.add('websoft9dev/wordpress:6.5')

    asyncio.run(redeploy.manager.redeploy_app(app_id, False, 21))

    assert redeploy.pulls == []
    assert len(redeploy.portainer.redeploy_calls) == 1


def test_redeploy_forces_a_pull_when_requested(redeploy, compose_workspace):
    app_id, prepare = compose_workspace
    prepare('services:\n  web:\n    image: websoft9dev/wordpress:6.5\n')
    redeploy.docker.existing.add('websoft9dev/wordpress:6.5')

    asyncio.run(redeploy.manager.redeploy_app(app_id, True, 21))

    assert redeploy.pulls == ['websoft9dev/wordpress:6.5']


def test_redeploy_aligns_proxy_ports_after_a_port_change(redeploy, compose_workspace):
    app_id, prepare = compose_workspace
    prepare('services:\n  web:\n    image: websoft9dev/wordpress:6.5\n')
    redeploy.monkeypatch.setattr(
        AppManger,
        'get_app_by_id',
        lambda self, app_id, *args, **kwargs: SimpleNamespace(
            domain_names=[{'id': 4, 'forward_port': '8080'}],
            env={'W9_HTTP_PORT': '9090'},
        ),
    )

    asyncio.run(redeploy.manager.redeploy_app(app_id, False, 21))

    assert redeploy.proxy.updated == [(4, '9090')]
