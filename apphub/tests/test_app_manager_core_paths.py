"""Core-path coverage for `AppManger`: the state machine behind uninstall, proxy creation, PHP info
and PHP migration.

These paths talk to Portainer, Gitea, the proxy and the host Docker daemon. The tests below keep the
real orchestration code (branching, error mapping, side-effect ordering) and replace only the
outbound clients, so a regression in "which status code does an inactive stack produce" or "is the
proxy removed before the stack" is caught here instead of on an operator's machine.
"""

import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import docker
import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import restore_module_stubs, stub_module

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='app-manager-core-'))

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


class FakePortainer:
    """Portainer stand-in whose answers each test configures explicitly."""

    def __init__(self):
        self.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 2}
        self.stack_exists = True
        self.containers = []
        self.removed_stacks = []
        self.local_endpoint_id = 21

    def get_local_endpoint_id(self):
        return self.local_endpoint_id

    def check_stack_exists(self, app_id, endpoint_id):
        return self.stack_exists

    def get_stack_by_name(self, app_id, endpoint_id):
        return self.stack

    def get_containers_by_stack_name(self, app_id, endpoint_id):
        return self.containers

    def remove_stack_and_volumes(self, stack_id, endpoint_id):
        self.removed_stacks.append((stack_id, endpoint_id))


class FakeProxy:
    def __init__(self):
        self.proxy_hosts = []
        self.removed = []
        self.created = []
        self.checked_domains = []
        self.provisioned = []
        self.provision_error = None
        self.create_result = {'id': 11, 'domain_names': ['wordpress.example.com']}

    def get_proxy_host_by_app(self, app_id):
        return self.proxy_hosts

    def remove_proxy_host_by_app(self, app_id):
        self.removed.append(app_id)

    def check_proxy_host_exists(self, domain_names):
        self.checked_domains.append(list(domain_names))

    def create_proxy_by_app(self, domain_names, app_id, forward_port, *args, **kwargs):
        self.created.append(
            {
                'domain_names': list(domain_names),
                'app_id': app_id,
                'forward_port': forward_port,
                'advanced_config': args[0] if args else None,
                'kwargs': kwargs,
            }
        )
        return dict(self.create_result)

    def provision_https_for_proxy_host(self, proxy_id, domain_names):
        if self.provision_error:
            raise self.provision_error
        self.provisioned.append((proxy_id, list(domain_names)))
        return {'id': proxy_id, 'domain_names': list(domain_names), 'certificate_id': 3}


class FakeGitea:
    def __init__(self):
        self.repo_exists = False
        self.removed = []
        self.advanced_config = None

    def check_repo_exists(self, repo_name):
        return self.repo_exists

    def remove_repo(self, repo_name):
        self.removed.append(repo_name)

    def get_file_raw_from_repo(self, app_id, path):
        return self.advanced_config


@pytest.fixture
def wiring(monkeypatch):
    """Installs the fakes and returns the handles each test asserts on."""
    portainer = FakePortainer()
    proxy = FakeProxy()
    gitea = FakeGitea()
    monkeypatch.setattr(app_manager_module, 'PortainerManager', lambda *args, **kwargs: portainer)
    monkeypatch.setattr(app_manager_module, 'ProxyManager', lambda *args, **kwargs: proxy)
    monkeypatch.setattr(app_manager_module, 'GiteaManager', lambda *args, **kwargs: gitea)
    monkeypatch.setattr(app_manager_module, 'check_endpointId', lambda endpoint_id, manager: None)

    forgotten = []
    monkeypatch.setattr(app_manager_module, 'forget_install_secrets', forgotten.append)
    revoked = []
    monkeypatch.setattr(AppManger, '_revoke_sftp_grants', staticmethod(revoked.append))

    return SimpleNamespace(
        manager=AppManger(),
        portainer=portainer,
        proxy=proxy,
        gitea=gitea,
        forgotten=forgotten,
        revoked=revoked,
        monkeypatch=monkeypatch,
    )


# ── remove_app ─────────────────────────────────────────────────────────────


def test_remove_app_rejects_unknown_stack(wiring):
    wiring.portainer.stack_exists = False

    with pytest.raises(CustomException) as error:
        wiring.manager.remove_app('wordpress_abc', endpointId=21)

    assert error.value.status_code == 400
    assert error.value.details == 'wordpress_abc Not Found'
    assert wiring.portainer.removed_stacks == []


def test_remove_app_rejects_stack_without_id(wiring):
    wiring.portainer.stack = {'Name': 'wordpress_abc', 'Status': 2}

    with pytest.raises(CustomException) as error:
        wiring.manager.remove_app('wordpress_abc', endpointId=21)

    assert error.value.details == 'wordpress_abc Not Found'
    assert wiring.portainer.removed_stacks == []


def test_remove_app_refuses_a_running_stack(wiring):
    wiring.portainer.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 1}
    wiring.portainer.containers = [
        {'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']},
    ]

    with pytest.raises(CustomException) as error:
        wiring.manager.remove_app('wordpress_abc', endpointId=21)

    assert 'is not inactive' in error.value.details
    assert wiring.portainer.removed_stacks == []
    assert wiring.forgotten == []


def test_remove_app_cleans_proxy_repo_stack_and_secrets_in_order(wiring):
    wiring.portainer.containers = [{'Id': 'c1', 'State': 'exited', 'Names': ['/wordpress_abc-1']}]
    wiring.proxy.proxy_hosts = [{'id': 4, 'domain_names': ['wordpress.example.com']}]
    wiring.gitea.repo_exists = True

    wiring.manager.remove_app('wordpress_abc', endpointId=21)

    assert wiring.proxy.removed == ['wordpress_abc']
    assert wiring.gitea.removed == ['wordpress_abc']
    assert wiring.portainer.removed_stacks == [(8, 21)]
    assert wiring.forgotten == ['wordpress_abc']
    assert wiring.revoked == ['wordpress_abc']


def test_remove_app_skips_proxy_and_repo_when_absent(wiring):
    wiring.portainer.containers = []

    wiring.manager.remove_app('wordpress_abc', endpointId=21)

    assert wiring.proxy.removed == []
    assert wiring.gitea.removed == []
    assert wiring.portainer.removed_stacks == [(8, 21)]


# ── get_php_info ───────────────────────────────────────────────────────────


class FakeExecResult:
    def __init__(self, exit_code, output):
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    def __init__(self, results):
        self.results = list(results)
        self.commands = []

    def exec_run(self, command):
        self.commands.append(command)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeDockerClient:
    def __init__(self, containers):
        self._containers = containers
        self.containers = self

    def get(self, container_id):
        value = self._containers[container_id]
        if isinstance(value, Exception):
            raise value
        return value


def _patch_docker(monkeypatch, containers):
    client = FakeDockerClient(containers)
    monkeypatch.setattr(app_manager_module.docker, 'from_env', lambda *args, **kwargs: client)
    return client


def test_get_php_info_rejects_unknown_stack(wiring):
    wiring.portainer.stack_exists = False

    with pytest.raises(CustomException) as error:
        wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert error.value.details == 'wordpress_abc Not Found'


def test_get_php_info_rejects_stack_without_containers(wiring):
    wiring.portainer.containers = []

    with pytest.raises(CustomException) as error:
        wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert error.value.details == 'No containers found for this app'


def test_get_php_info_parses_version_and_module_sections(wiring):
    wiring.portainer.containers = [{'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']}]
    container = FakeContainer(
        [
            FakeExecResult(0, b'PHP 8.3.6 (cli) (built: Sep 12 2024)'),
            FakeExecResult(0, b'[PHP Modules]\ncore\ncurl\n\n[Zend Modules]\nZend OPcache\n'),
        ]
    )
    _patch_docker(wiring.monkeypatch, {'c1': container})

    info = wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert info == {
        'version': 'PHP 8.3.6',
        'modules': {
            'PHP Modules': ['core', 'curl'],
            'Zend Modules': ['Zend OPcache'],
        },
    }
    assert container.commands == ['php -v', 'php -m']


def test_get_php_info_skips_a_container_that_cannot_run_php(wiring):
    wiring.portainer.containers = [
        {'Id': 'c-running', 'State': 'running', 'Names': ['/wordpress_abc-1']},
        {'Id': 'c-sidecar', 'State': 'running', 'Names': ['/wordpress_abc-db']},
    ]
    broken = FakeContainer([FakeExecResult(1, b'php: not found'), FakeExecResult(1, b'')])
    working = FakeContainer(
        [
            FakeExecResult(0, b'PHP 8.2.20 (cli)'),
            FakeExecResult(0, b'[PHP Modules]\ncore\n'),
        ]
    )
    _patch_docker(wiring.monkeypatch, {'c-running': broken, 'c-sidecar': working})

    info = wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert info['version'] == 'PHP 8.2.20'
    assert info['modules'] == {'PHP Modules': ['core']}


def test_get_php_info_reports_when_no_container_runs_php(wiring):
    wiring.portainer.containers = [{'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']}]
    _patch_docker(
        wiring.monkeypatch,
        {'c1': FakeContainer([FakeExecResult(127, b'php: not found'), FakeExecResult(127, b'')])},
    )

    with pytest.raises(CustomException) as error:
        wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert error.value.details == 'PHP runtime is not available for any running container in this app'


def test_get_php_info_skips_a_container_the_docker_api_cannot_reach(wiring):
    wiring.portainer.containers = [
        {'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']},
        {'Id': 'c2', 'State': 'running', 'Names': ['/wordpress_abc-2']},
    ]
    unreachable = FakeContainer([docker.errors.APIError('unreachable')])
    working = FakeContainer([FakeExecResult(0, b'PHP 8.3.6 (cli)'), FakeExecResult(0, b'[PHP Modules]\ncore\n')])
    _patch_docker(wiring.monkeypatch, {'c1': unreachable, 'c2': working})

    assert wiring.manager.get_php_info('wordpress_abc', endpointId=21)['version'] == 'PHP 8.3.6'


def test_get_php_info_maps_a_missing_container_to_a_readable_error(wiring):
    wiring.portainer.containers = [{'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']}]
    wiring.monkeypatch.setattr(
        app_manager_module.docker,
        'from_env',
        lambda *args, **kwargs: (_ for _ in ()).throw(docker.errors.NotFound('gone')),
    )

    with pytest.raises(CustomException) as error:
        wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert error.value.status_code == 400
    assert error.value.details == 'Main PHP container not found'


def test_get_php_info_wraps_an_unexpected_docker_failure(wiring):
    wiring.portainer.containers = [{'Id': 'c1', 'State': 'running', 'Names': ['/wordpress_abc-1']}]
    wiring.monkeypatch.setattr(
        app_manager_module.docker,
        'from_env',
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('daemon exploded')),
    )

    with pytest.raises(CustomException) as error:
        wiring.manager.get_php_info('wordpress_abc', endpointId=21)

    assert error.value.details == 'Internal Server Error'


# ── request_php_migration ─────────────────────────────────────────────────


class FakeConfigManager:
    def __init__(self, value):
        self.value = value

    def get_value(self, section, key):
        return self.value


def _patch_migration(monkeypatch, webhook_url, response=None, error=None):
    monkeypatch.setattr(app_manager_module, 'ConfigManager', lambda *args, **kwargs: FakeConfigManager(webhook_url))
    calls = []

    def fake_post(url, **kwargs):
        calls.append({'url': url, **kwargs})
        if error:
            raise error
        return response

    monkeypatch.setattr(app_manager_module.requests, 'post', fake_post)
    return calls


class FakeWebhookResponse:
    def __init__(self, payload, content=b'{}'):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture
def migration(wiring):
    wiring.manager.get_php_info = lambda app_id, endpoint_id=None: {'version': 'PHP 8.2.20'}
    wiring.manager.get_app_by_id = lambda app_id, endpoint_id=None: SimpleNamespace(app_id=app_id, app_name='WordPress')
    return wiring


def test_php_migration_requires_a_target_version(migration):
    _patch_migration(migration.monkeypatch, 'https://hook.example.com')

    with pytest.raises(CustomException) as error:
        migration.manager.request_php_migration('wordpress_abc', '   ', 'please upgrade')

    assert error.value.details == 'Target PHP version is required'


def test_php_migration_requires_remarks(migration):
    _patch_migration(migration.monkeypatch, 'https://hook.example.com')

    with pytest.raises(CustomException) as error:
        migration.manager.request_php_migration('wordpress_abc', '8.3', '  ')

    assert error.value.details == 'Migration remarks are required'


def test_php_migration_requires_a_configured_webhook(migration):
    _patch_migration(migration.monkeypatch, '')

    with pytest.raises(CustomException) as error:
        migration.manager.request_php_migration('wordpress_abc', '8.3', 'please upgrade')

    assert error.value.status_code == 500
    assert error.value.details == 'Webhook URL is not configured'


def test_php_migration_posts_the_application_details(migration):
    calls = _patch_migration(migration.monkeypatch, 'https://hook.example.com', FakeWebhookResponse({'errcode': 0}))

    result = migration.manager.request_php_migration('wordpress_abc', ' 8.3 ', ' please upgrade ')

    assert result == {'message': 'Success', 'details': 'PHP migration request submitted successfully'}
    assert calls[0]['url'] == 'https://hook.example.com'
    content = calls[0]['json']['markdown']['content']
    assert 'WordPress' in content
    assert 'PHP 8.2.20' in content
    assert 'PHP 8.3' in content
    assert 'please upgrade' in content


def test_php_migration_surfaces_a_webhook_rejection(migration):
    _patch_migration(
        migration.monkeypatch,
        'https://hook.example.com',
        FakeWebhookResponse({'errcode': 93000, 'errmsg': 'invalid webhook url'}),
    )

    with pytest.raises(CustomException) as error:
        migration.manager.request_php_migration('wordpress_abc', '8.3', 'please upgrade')

    assert error.value.status_code == 502
    assert error.value.details == 'invalid webhook url'


def test_php_migration_maps_a_transport_failure_to_a_bad_gateway(migration):
    _patch_migration(
        migration.monkeypatch,
        'https://hook.example.com',
        error=requests.RequestException('connection reset'),
    )

    with pytest.raises(CustomException) as error:
        migration.manager.request_php_migration('wordpress_abc', '8.3', 'please upgrade')

    assert error.value.status_code == 502
    assert error.value.details == 'Failed to submit the PHP migration request'


# ── create_proxy_by_app ───────────────────────────────────────────────────


def _proxy_app(env, wiring=None):
    if wiring is not None:
        # create_proxy_by_app 只接受运行中的 stack(Status 1)；默认 fake 是停机栈。
        wiring.portainer.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 1}
    return lambda app_id, endpoint_id=None: SimpleNamespace(app_id=app_id, app_name='wordpress', env=env)


def test_create_proxy_rejects_unknown_stack(wiring):
    wiring.portainer.stack = None

    with pytest.raises(CustomException) as error:
        wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert error.value.details == 'wordpress_abc Not Found'


def test_create_proxy_rejects_an_inactive_stack(wiring):
    wiring.portainer.stack = {'Id': 8, 'Name': 'wordpress_abc', 'Status': 2}

    with pytest.raises(CustomException) as error:
        wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert 'is inactive, can not create proxy' in error.value.details
    assert wiring.proxy.created == []


def test_create_proxy_rejects_an_app_without_environment(wiring):
    wiring.manager.get_app_by_id = _proxy_app(None, wiring)

    with pytest.raises(CustomException):
        wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert wiring.proxy.created == []


def test_create_proxy_rejects_an_app_without_a_forward_port(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_URL': 'http://1.2.3.4'}, wiring)

    with pytest.raises(CustomException):
        wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert wiring.proxy.created == []


def test_create_proxy_uses_the_http_port_and_advanced_config(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTP_PORT': '8080'}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'http'
    wiring.gitea.advanced_config = 'proxy_set_header X-Test 1;'

    result = wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21, ssl_forced=True)

    assert result == {'id': 11, 'domain_names': ['wordpress.example.com']}
    assert wiring.proxy.checked_domains == [['wordpress.example.com']]
    created = wiring.proxy.created[0]
    assert created['forward_port'] == '8080'
    assert created['advanced_config'] == 'proxy_set_header X-Test 1;'
    assert created['kwargs']['forward_scheme'] == 'http'
    assert created['kwargs']['ssl_forced'] is True
    assert wiring.proxy.provisioned == []


def test_create_proxy_falls_back_to_the_https_port(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTPS_PORT': '8443'}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'https'

    wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    created = wiring.proxy.created[0]
    assert created['forward_port'] == '8443'
    assert created['kwargs']['forward_scheme'] == 'https'


def test_create_proxy_provisions_https_for_a_tls_app_without_a_certificate(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTP_PORT': '8080'}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'https'

    result = wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert wiring.proxy.provisioned == [(11, ['wordpress.example.com'])]
    assert result['certificate_id'] == 3


def test_create_proxy_keeps_the_proxy_when_https_provisioning_fails(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTP_PORT': '8080'}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'https'
    wiring.proxy.provision_error = RuntimeError('acme unreachable')

    result = wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    # A failed certificate must not lose the proxy host that was already created.
    assert result == {'id': 11, 'domain_names': ['wordpress.example.com']}


def test_create_proxy_forces_ssl_when_a_certificate_is_supplied_for_a_tls_app(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTP_PORT': '8080'}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'https'

    wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21, certificate_id=9)

    assert wiring.proxy.created[0]['kwargs']['ssl_forced'] is True
    assert wiring.proxy.provisioned == []


def test_create_proxy_rejects_without_a_forward_port(wiring):
    wiring.manager.get_app_by_id = _proxy_app({'W9_HTTP_PORT': ''}, wiring)
    wiring.manager._read_default_scheme_from_repo = lambda app_id, http_port=None, https_port=None: 'http'

    with pytest.raises(CustomException):
        wiring.manager.create_proxy_by_app('wordpress_abc', ['wordpress.example.com'], endpointId=21)

    assert wiring.proxy.created == []
