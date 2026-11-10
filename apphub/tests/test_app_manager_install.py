"""`AppManger.install_app`: the marketplace installation pipeline.

This is the longest sequence in the product: create a Gitea repository, materialise the template into
a workspace, write `.env`, push, pull images, create the Portainer stack, wait for containers and
optionally publish the app through the reverse proxy. Every step has its own rollback, and the
rollback is what keeps a failed install from leaving a half-created app behind - so each failure
point is asserted with the cleanup it must perform.

The real `EnvHelper` is used against a throwaway library directory (that is where `.env` handling
actually happens), while every outbound client is replaced.
"""

import glob
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.services import app_manager as app_module
from src.services.app_manager import AppManger

APP_NAME = 'wpplugin'
APP_ID = 'wpplugin_ab123'


@pytest.fixture
def install(monkeypatch, tmp_path):
    library = tmp_path / 'library'
    app_dir = library / APP_NAME
    app_dir.mkdir(parents=True)
    # 默认是一个 web 应用(.env 里有 W9_URL),默认代理关掉
    (app_dir / '.env').write_text(
        'W9_URL=\nW9_HTTP_PORT_SET=8080\nW9_HTTP_PORT=8080\nW9_HTTPS_PORT_SET=8443\nW9_HTTPS_PORT=8443\n'
    )

    state = SimpleNamespace(
        logs=[],
        modified=[],
        removed_logs=[],
        completed=[],
        cancelled=[],
        phases=[],
        pushed=[],
        pulled=[],
        secrets=[],
        templates=[],
        deploy_allowed=True,
        pull_error=None,
    )

    class FakePortainer:
        def __init__(self):
            self.created = []
            self.removed_stacks = []
            self.removed_volumes = []
            self.local_endpoint_calls = 0
            self.stack_by_name = None
            self.create_error = None
            self.containers = [{'Names': ['/wpplugin_web_1'], 'State': 'running'}]

        def get_local_endpoint_id(self):
            self.local_endpoint_calls += 1
            return 42

        def create_stack_from_repository(self, *args):
            self.created.append(args)
            if self.create_error:
                raise self.create_error
            return {'Id': 77}

        def wait_for_stack_containers(self, app_id, endpoint_id):
            return self.containers

        def get_stack_by_name(self, app_id, endpoint_id):
            return self.stack_by_name

        def remove_stack_and_volumes(self, stack_id, endpoint_id):
            self.removed_stacks.append((stack_id, endpoint_id))

        def remove_vloumes(self, app_id, endpoint_id):
            self.removed_volumes.append((app_id, endpoint_id))

    class FakeGitea:
        def __init__(self):
            self.repositories = []
            self.removed = []
            self.waited = []
            self.create_error = None

        def create_repo(self, app_id):
            if self.create_error:
                raise self.create_error
            self.repositories.append(app_id)
            return f'http://gitea.local/git/{app_id}.git'

        def remove_repo(self, app_id):
            self.removed.append(app_id)

        def wait_for_repo_files(self, app_id, repo_url, username, password, required_files):
            self.waited.append((app_id, required_files))

    class FakeProxy:
        def __init__(self):
            self.created = []
            self.provisioned = []
            self.create_error = None

        def create_proxy_by_app(self, domain_names, app_id, forward_port, advanced_config=None, forward_scheme='http'):
            if self.create_error:
                raise self.create_error
            self.created.append(
                {
                    'domain_names': domain_names,
                    'app_id': app_id,
                    'forward_port': forward_port,
                    'advanced_config': advanced_config,
                    'forward_scheme': forward_scheme,
                }
            )
            return {'id': 11, 'domain_names': domain_names}

        def provision_https_for_proxy_host(self, proxy_id, domain_names):
            self.provisioned.append((proxy_id, domain_names))

    portainer = FakePortainer()
    gitea = FakeGitea()
    proxy = FakeProxy()

    monkeypatch.setattr(app_module, 'PortainerManager', lambda *args, **kwargs: portainer)
    monkeypatch.setattr(app_module, 'GiteaManager', lambda *args, **kwargs: gitea)
    monkeypatch.setattr(app_module, 'ProxyManager', lambda *args, **kwargs: proxy)
    monkeypatch.setattr(
        app_module,
        'IntegrationCredentialProvider',
        lambda *args, **kwargs: SimpleNamespace(
            get_gitea_credentials=lambda: SimpleNamespace(username='git', password='secret')
        ),
    )
    monkeypatch.setattr(app_module, 'add_installing_logs', lambda *args: state.logs.append(args))
    monkeypatch.setattr(app_module, 'set_install_phase', lambda uuid, phase: state.phases.append(phase))
    monkeypatch.setattr(app_module, 'begin_install_deploy', lambda uuid: state.deploy_allowed)
    monkeypatch.setattr(app_module, 'mark_install_cancelled', lambda uuid: state.cancelled.append(uuid))
    monkeypatch.setattr(app_module, 'modify_app_information', lambda uuid, error: state.modified.append((uuid, error)))
    monkeypatch.setattr(app_module, 'remove_installation_logs', lambda uuid: state.removed_logs.append(uuid))
    monkeypatch.setattr(app_module, 'remove_app_installation', lambda uuid: state.completed.append(uuid))
    monkeypatch.setattr(app_module, 'remove_app_from_errors_by_app_id', lambda app_id: None)
    monkeypatch.setattr(app_module, 'start_app_installation', lambda app_id, app_name: 'tracking-1')
    monkeypatch.setattr(app_module, 'pull_error_detail', lambda exc: f'pull failed: {exc}')
    monkeypatch.setattr(
        app_module, 'initialize_install_secrets', lambda path, app_id, app_name, settings: state.secrets.append(app_id)
    )
    monkeypatch.setattr(app_module, 'materialize_profile_template', lambda path, profile: state.templates.append(profile))
    monkeypatch.setattr(
        app_module,
        'is_external_database_profile',
        lambda path, profile: profile == 'external-db',
    )
    monkeypatch.setattr(app_module, 'get_external_database_type', lambda path: 'mysql')
    monkeypatch.setattr(
        app_module,
        'validate_external_database_connection',
        lambda *args: SimpleNamespace(database_type=args[0]),
    )
    # 避免真的等 1 秒、也避免把 /tmp 里的工作目录留下
    monkeypatch.setattr(app_module.time, 'sleep', lambda seconds: None)

    manager = AppManger()
    manager._init_local_repo_and_push_to_remote = lambda path, url: state.pushed.append((path, url))
    manager.pull_images_from_yml = lambda path, uuid: state.pulled.append((path, uuid))
    if state.pull_error is not None:
        pass

    def pull(path, uuid):
        if state.pull_error:
            raise state.pull_error
        state.pulled.append((path, uuid))

    manager.pull_images_from_yml = pull
    manager._collect_repository_required_files = lambda path: ['docker-compose.yml', '.env']

    yield SimpleNamespace(
        manager=manager,
        library=library,
        app_dir=app_dir,
        portainer=portainer,
        gitea=gitea,
        proxy=proxy,
        state=state,
    )

    # 清理 /tmp 下的工作目录
    for leftover in glob.glob(f'/tmp/{APP_NAME}_*'):
        shutil.rmtree(leftover, ignore_errors=True)


def _payload(app_name=APP_NAME, **overrides):
    data = {
        'app_name': app_name,
        'edition': {'dist': 'community', 'version': '6.5.0'},
        'app_id': 'wppluginab123',
        'proxy_enabled': False,
        'domain_names': ['wp.example.com'],
        'settings': {},
    }
    data.update(overrides)
    return appInstall(**data)


def _install(install, payload=None, **kwargs):
    kwargs.setdefault('library_path', str(install.library))
    return install.manager._install_app(payload or _payload(), **kwargs)


def _external_settings():
    return {
        'W9_DB_HOST_SET': 'db.example.com',
        'W9_DB_PORT_SET': '3306',
        'W9_DB_NAME_SET': 'shop',
        'W9_DB_USER_SET': 'wp',
        'W9_DB_PASSWORD_SET': 'secret',
    }


def _capture_env_at_push(install, monkeypatch):
    """The workspace is removed after the push, so read ``.env`` on the way out."""
    captured = {}

    def push(path, url):
        install.state.pushed.append((path, url))
        captured['env'] = (Path(path) / '.env').read_text(encoding='utf-8')

    monkeypatch.setattr(install.manager, '_init_local_repo_and_push_to_remote', push)
    return captured


def _stages(install):
    return [entry[1] for entry in install.state.logs]


# ── happy paths ───────────────────────────────────────────────────────────


def test_a_complete_install_runs_every_step_in_order(install):
    _install(install, tracked_app_id=APP_ID, tracking_id='tracking-1', endpointId=42)

    assert _stages(install) == [
        'Initializing installation',
        'Initializing installation',
        'Initializing installation',
        'Initializing installation',
        'Pulling docker image',
        'Starting the services',
        'Starting the services',
        'Starting the services',
        'Starting the services',
        'Installation complete',
    ]
    assert install.gitea.repositories == [APP_ID]
    assert install.state.pushed[0][1] == f'http://gitea.local/git/{APP_ID}.git'
    assert install.state.pulled[0] == (install.state.pushed[0][0], 'tracking-1')
    assert install.state.phases == ['pulling']
    assert install.gitea.waited[0][0] == APP_ID
    assert install.portainer.created[0][:3] == (APP_ID, 42, f'http://gitea.local/git/{APP_ID}.git')
    # 容器状态被写入安装日志
    assert 'Container wpplugin_web_1 is running' in [entry[2] for entry in install.state.logs]
    assert install.state.completed == ['tracking-1']
    assert install.state.modified == []
    # 代理关闭时不创建反向代理
    assert install.proxy.created == []


def test_the_environment_file_records_the_application_identity(install):
    captured = {}
    original_push = install.manager._init_local_repo_and_push_to_remote

    def push(path, url):
        captured['env'] = (install.state.pushed.append((path, url)), (app_module.Path(path) / '.env').read_text())[1]

    install.manager._init_local_repo_and_push_to_remote = push

    _install(install, payload=_payload(settings={'W9_DB_NAME_SET': 'shop'}), tracked_app_id=APP_ID, endpointId=42)

    env = captured['env']
    assert f"W9_ID='{APP_ID}'" in env
    assert 'W9_APP_NAME' in env and APP_NAME in env
    assert 'W9_VERSION' in env and '6.5.0' in env
    # 用户设置的键值也写进 .env
    assert 'W9_DB_NAME_SET' in env and 'shop' in env
    assert install.state.secrets == [APP_ID]
    assert original_push is not None


def test_a_proxied_web_app_publishes_the_http_port(install):
    _install(
        install,
        payload=_payload(proxy_enabled=True, domain_names=['wp.example.com', 'www.example.com']),
        tracked_app_id=APP_ID,
        endpointId=42,
    )

    assert install.proxy.created == [
        {
            'domain_names': ['wp.example.com', 'www.example.com'],
            'app_id': APP_ID,
            'forward_port': '8080',
            'advanced_config': None,
            'forward_scheme': 'http',
        }
    ]
    assert "Configuring reverse proxy for wp.example.com, www.example.com -> wpplugin_ab123:8080 (http)" in [
        entry[2] for entry in install.state.logs
    ]


def test_a_tls_only_app_is_published_over_https_and_gets_a_certificate(install):
    (install.app_dir / '.env').write_text('W9_URL=\nW9_HTTPS_PORT=8443\n')
    (install.app_dir / 'variables.json').write_text(json.dumps({'access': {'defaultScheme': 'https'}}))

    _install(install, payload=_payload(proxy_enabled=True), tracked_app_id=APP_ID, endpointId=42)

    assert install.proxy.created[0]['forward_scheme'] == 'https'
    assert install.proxy.created[0]['forward_port'] == '8443'
    # defaultScheme=https 时自动签发证书
    assert install.proxy.provisioned == [(11, ['wp.example.com'])]


def test_an_advanced_proxy_configuration_is_used_when_present(install):
    (install.app_dir / 'src').mkdir()
    (install.app_dir / 'src' / 'nginx-proxy.conf').write_text('proxy_set_header X-Test 1;\n')

    _install(install, payload=_payload(proxy_enabled=True), tracked_app_id=APP_ID, endpointId=42)

    assert install.proxy.created[0]['advanced_config'] == 'proxy_set_header X-Test 1;\n'


def test_the_local_endpoint_is_used_when_none_is_given(install):
    _install(install, tracked_app_id=APP_ID)

    assert install.portainer.local_endpoint_calls == 1
    assert install.portainer.created[0][1] == 42


# ── URL rewriting ─────────────────────────────────────────────────────────


def test_an_ip_gets_the_published_port_appended(install):
    (install.app_dir / '.env').write_text('W9_URL=\nW9_URL_REPLACE=\nW9_HTTP_PORT_SET=8080\nW9_HTTP_PORT=8080\n')
    captured = {}
    install.manager._init_local_repo_and_push_to_remote = lambda path, url: captured.update(
        env=(app_module.Path(path) / '.env').read_text()
    )

    _install(install, payload=_payload(domain_names=['192.0.2.10']), tracked_app_id=APP_ID, endpointId=42)

    assert '192.0.2.10:8080' in captured['env']


def test_a_hostname_is_used_as_is_for_the_root_url(install):
    (install.app_dir / '.env').write_text('W9_URL=\nW9_URL_REPLACE=\nW9_HTTP_PORT_SET=8080\nW9_HTTP_PORT=8080\n')
    captured = {}
    install.manager._init_local_repo_and_push_to_remote = lambda path, url: captured.update(
        env=(app_module.Path(path) / '.env').read_text()
    )

    _install(install, payload=_payload(domain_names=['wp.example.com']), tracked_app_id=APP_ID, endpointId=42)

    assert "W9_URL='wp.example.com'" in captured['env']


def test_the_schema_rejects_a_web_app_without_domains_before_installing():
    # appInstall 的校验会先拒绝空 domain_names,安装流程里的同名检查是第二道防线
    with pytest.raises(CustomException) as error:
        _payload(domain_names=[])

    assert "cannot be empty" in error.value.details


# ── failure and rollback per step ─────────────────────────────────────────


def test_a_repository_failure_is_recorded(install):
    install.gitea.create_error = CustomException(400, 'Invalid Request', 'repo exists')

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.details == 'repo exists'
    assert install.state.modified == [('tracking-1', 'repo exists')]
    assert install.state.removed_logs == ['tracking-1']
    # 后续步骤都没有执行
    assert install.state.pushed == []


def test_an_unexpected_repository_failure_is_wrapped(install):
    install.gitea.create_error = RuntimeError('gitea is down')

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.status_code == 500
    assert install.state.modified == [('tracking-1', 'gitea is down')]


def test_a_preparation_failure_removes_the_created_repository(install, monkeypatch):
    def exploding(path, profile):
        raise RuntimeError('template is missing')

    monkeypatch.setattr(app_module, 'materialize_profile_template', exploding)

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.status_code == 500
    assert install.gitea.removed == [APP_ID]
    assert install.state.modified == [('tracking-1', 'template is missing')]


def test_an_external_database_without_a_type_is_rejected(install, monkeypatch):
    monkeypatch.setattr(app_module, 'get_external_database_type', lambda path: None)

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(profile='external-db'), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.details == 'The external database type could not be resolved'
    assert install.gitea.removed == [APP_ID]


def test_an_external_database_is_validated_from_the_form_values(install, monkeypatch):
    validated = []

    def validate(database_type, host, port, name, user, password):
        validated.append((database_type, host, port, name, user, password))
        return SimpleNamespace(database_type=database_type)

    monkeypatch.setattr(app_module, 'validate_external_database_connection', validate)

    _install(
        install,
        payload=_payload(profile='external-db', settings=_external_settings()),
        tracked_app_id=APP_ID,
        endpointId=42,
    )

    assert validated == [('mysql', 'db.example.com', '3306', 'shop', 'wp', 'secret')]
    assert install.state.completed == ['tracking-1']


def test_form_only_connection_keys_are_not_written_to_the_instance(install, monkeypatch):
    """The declaration owns the runtime variables; form keys stay inputs."""
    captured = _capture_env_at_push(install, monkeypatch)

    _install(
        install,
        payload=_payload(profile='external-db', settings=_external_settings()),
        tracked_app_id=APP_ID,
        endpointId=42,
    )

    for key in ('W9_DB_HOST_SET', 'W9_DB_PORT_SET', 'W9_DB_NAME_SET', 'W9_DB_USER_SET', 'W9_DB_PASSWORD_SET'):
        assert f'{key}=' not in captured['env']
    assert 'W9_DB_EXPOSE' in captured['env']
    assert 'W9_DATABASE_MODE' in captured['env']


def test_connection_keys_the_template_declares_are_kept(install, monkeypatch):
    """Instances installed through the retired profile keep their keys."""
    env_path = install.app_dir / '.env'
    env_path.write_text(env_path.read_text(encoding='utf-8') + 'W9_DB_HOST_SET=\n', encoding='utf-8')
    captured = _capture_env_at_push(install, monkeypatch)

    _install(
        install,
        payload=_payload(profile='external-db', settings=_external_settings()),
        tracked_app_id=APP_ID,
        endpointId=42,
    )

    assert 'W9_DB_HOST_SET' in captured['env']


def test_an_image_pull_failure_reports_the_reason_and_rolls_back(install):
    install.state.pull_error = RuntimeError('manifest unknown')

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.status_code == 500
    assert error.value.message == 'Image Pull Error'
    assert error.value.details == 'pull failed: manifest unknown'
    assert install.gitea.removed == [APP_ID]
    assert install.portainer.created == []


def test_a_cancelled_pull_stops_the_install_quietly(install):
    install.state.pull_error = app_module.InstallCancelled()

    assert _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42) is None

    assert install.state.cancelled == ['tracking-1']
    assert 'Installation cancelled' in _stages(install)
    assert install.state.completed == []
    assert install.state.modified == []


def test_a_cancel_between_pull_and_deploy_stops_the_install(install):
    install.state.deploy_allowed = False

    _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert install.state.cancelled == ['tracking-1']
    assert install.portainer.created == []
    assert install.state.completed == []


def test_a_stack_without_containers_fails_and_removes_the_stack(install):
    install.portainer.containers = []

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.details == AppManger._missing_stack_containers_error
    assert install.portainer.removed_stacks == [(77, 42)]
    assert install.gitea.removed == [APP_ID]


def test_a_stack_creation_failure_cleans_up_the_stack_portainer_already_made(install):
    install.portainer.create_error = RuntimeError('compose up failed')
    install.portainer.stack_by_name = {'Id': 88}

    with pytest.raises(CustomException):
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert install.portainer.removed_stacks == [(88, 42)]


def test_a_stack_creation_failure_without_a_stack_only_clears_volumes(install):
    install.portainer.create_error = RuntimeError('compose up failed')
    install.portainer.stack_by_name = None

    with pytest.raises(CustomException):
        _install(install, payload=_payload(), tracked_app_id=APP_ID, endpointId=42)

    assert install.portainer.removed_volumes == [(APP_ID, 42)]
    assert install.portainer.removed_stacks == []


def test_a_proxy_failure_rolls_back_the_stack_and_the_repository(install):
    install.proxy.create_error = CustomException(400, 'Invalid Request', 'domain already used')

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(proxy_enabled=True), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.details == 'domain already used'
    assert install.portainer.removed_stacks == [(77, 42)]
    assert install.gitea.removed == [APP_ID]
    assert install.state.completed == []


# ── install_app wrapper ───────────────────────────────────────────────────


class _Contains:
    def __init__(self, present):
        self.present = present

    def __contains__(self, item):
        return self.present


def test_install_app_records_the_failure_on_the_install_record(monkeypatch):
    from src.services import app_status

    manager = AppManger()

    def exploding(*args, **kwargs):
        raise CustomException(400, 'Invalid Request', 'boom')

    monkeypatch.setattr(manager, '_install_app', exploding)
    monkeypatch.setattr(app_module, 'start_app_installation', lambda app_id, app_name: 'tracking-2')
    # 只有"仍在安装中"的记录才需要写错误信息
    monkeypatch.setattr(app_module, 'appInstalling', _Contains(True))
    modified = []
    monkeypatch.setattr(app_module, 'modify_app_information', lambda uuid, error: modified.append((uuid, error)))

    with pytest.raises(CustomException):
        manager.install_app(_payload())

    assert modified == [('tracking-2', 'boom')]
    assert app_status is not None


def test_install_app_does_not_touch_finished_records(monkeypatch):
    manager = AppManger()

    def exploding(*args, **kwargs):
        raise RuntimeError('late failure')

    monkeypatch.setattr(manager, '_install_app', exploding)
    monkeypatch.setattr(app_module, 'start_app_installation', lambda app_id, app_name: 'tracking-3')
    monkeypatch.setattr(app_module, 'appInstalling', _Contains(False))
    modified = []
    monkeypatch.setattr(app_module, 'modify_app_information', lambda uuid, error: modified.append((uuid, error)))

    with pytest.raises(RuntimeError):
        manager.install_app(_payload())

    assert modified == []


# ── 已知缺陷(待确认)────────────────────────────────────────────────────


def test_a_proxied_app_without_a_published_port_is_reported_clearly(install):
    (install.app_dir / '.env').write_text('W9_URL=\n')

    with pytest.raises(CustomException) as error:
        _install(install, payload=_payload(proxy_enabled=True), tracked_app_id=APP_ID, endpointId=42)

    assert error.value.status_code == 400
