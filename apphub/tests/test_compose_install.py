"""Custom compose installs: validation of user-supplied YAML and the install pipeline.

Operators paste a compose file in the console, so validation is the first line of defence: a
document Docker or Portainer cannot parse must be rejected with a message that says which line or
which service field is wrong. The pipeline below it is a long sequence of side effects (Gitea repo,
image pull, stack creation, optional reverse proxy), and the tests pin both its order and what
happens when one of those steps fails.
"""

from types import SimpleNamespace

import pytest
import yaml

from src.core.exception import CustomException
from src.schemas.appComposeInstall import ComposeInstallRequest, ComposeValidationRequest
from src.services import compose_install as compose_module


def _payload(compose="services:\n  web:\n    image: nginx:1.27\n", **overrides):
    data = {"app_id": "myshop", "compose_content": compose}
    data.update(overrides)
    return ComposeInstallRequest(**data)


# ── platform network injection ────────────────────────────────────────────


def test_the_platform_network_is_added_as_default(monkeypatch):
    monkeypatch.setattr(compose_module, '_W9_NETWORK', 'websoft9')

    document = compose_module._inject_platform_network({'services': {'web': {}}})

    assert document['networks'] == {'default': {'name': 'websoft9', 'external': True}}


def test_a_user_declared_default_network_is_kept():
    document = {'services': {}, 'networks': {'default': {'driver': 'bridge'}}}

    compose_module._inject_platform_network(document)

    assert document['networks']['default'] == {'driver': 'bridge'}


def test_existing_networks_are_extended():
    document = {'services': {}, 'networks': {'backend': {'internal': True}}}

    compose_module._inject_platform_network(document)

    assert set(document['networks']) == {'backend', 'default'}


# ── service field validation ──────────────────────────────────────────────


def test_a_service_must_be_a_mapping():
    with pytest.raises(CustomException) as error:
        compose_module._validate_service_spec({'web': ['not', 'a', 'mapping']})

    assert error.value.details == "Service 'web' must be a mapping."


@pytest.mark.parametrize('field', ['environment', 'volumes', 'labels', 'extra_hosts', 'sysctls', 'ulimits', 'depends_on'])
def test_list_or_mapping_fields_reject_scalars(field):
    with pytest.raises(CustomException) as error:
        compose_module._validate_service_spec({'web': {field: 'oops'}})

    assert error.value.status_code == 400
    assert f"Service 'web': field '{field}' must be a list or mapping" in error.value.details
    # 提示要说清楚怎么改
    assert "leading '- '" in error.value.details


@pytest.mark.parametrize('field', ['ports', 'expose'])
def test_list_only_fields_reject_mappings(field):
    with pytest.raises(CustomException) as error:
        compose_module._validate_service_spec({'web': {field: {'target': 80}}})

    assert f"field '{field}' must be a list" in error.value.details


def test_null_and_valid_values_are_accepted():
    compose_module._validate_service_spec(
        {
            'web': {
                'environment': {'A': '1'},
                'volumes': [],
                'labels': None,
                'ports': ['8080:80'],
                'expose': [80],
            }
        }
    )


# ── variable interpolation ────────────────────────────────────────────────


def test_unclosed_substitutions_are_reported_with_the_line_number():
    with pytest.raises(CustomException) as error:
        compose_module._check_variable_interpolation("services:\n  web:\n    image: ${IMAGE\n")

    assert error.value.status_code == 400
    assert 'Line 3' in error.value.details
    assert '${IMAGE' in error.value.details


def test_closed_substitutions_pass():
    compose_module._check_variable_interpolation("image: ${IMAGE}\nother: ${A}${B}\n")


def test_a_second_unclosed_substitution_on_the_same_line_is_found():
    with pytest.raises(CustomException) as error:
        compose_module._check_variable_interpolation("image: ${OK}:${BROKEN\n")

    assert '${BROKEN' in error.value.details


# ── document loading ──────────────────────────────────────────────────────


def test_invalid_yaml_is_rejected():
    with pytest.raises(CustomException) as error:
        compose_module._load_compose_document('services: [unclosed\n')

    assert error.value.status_code == 400
    assert error.value.details.startswith('Compose syntax is invalid:')


@pytest.mark.parametrize('content', ['- a\n- b\n', 'just a string\n', ''])
def test_content_must_decode_to_an_object(content):
    with pytest.raises(CustomException):
        compose_module._load_compose_document(content)


@pytest.mark.parametrize('content', ['services: {}\n', 'version: "3"\n', 'networks: {}\n'])
def test_at_least_one_service_is_required(content):
    with pytest.raises(CustomException) as error:
        compose_module._load_compose_document(content)

    assert error.value.details == 'Compose content must define at least one service.'


def test_a_valid_document_is_returned():
    document = compose_module._load_compose_document('services:\n  web:\n    image: nginx\n')

    assert list(document['services']) == ['web']


def test_service_names_are_trimmed():
    assert compose_module._get_service_names({'services': {' web ': {}, 'db': {}}}) == ['web', 'db']


def test_empty_service_names_are_rejected():
    with pytest.raises(CustomException) as error:
        compose_module._get_service_names({'services': {'   ': {}}})

    assert error.value.details == 'Compose services must use non-empty names.'


# ── forward port detection ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('ports', 'expected'),
    [
        ([8080], 8080),
        (['8080:80'], 80),
        (['80/tcp'], 80),
        (['127.0.0.1:8080:80'], 80),
        ([{'target': 3000, 'published': 3000}], 3000),
        ([{'published': 3000}], None),
        ([{'target': 'not-a-number'}], None),
        (['not-a-port'], None),
        ([], None),
    ],
)
def test_the_forward_port_is_the_container_port(ports, expected):
    assert compose_module._extract_forward_port({'services': {'web': {'ports': ports}}}) == expected


def test_the_first_service_with_a_port_wins():
    document = {'services': {'db': {}, 'web': {'ports': ['8080:80']}}}

    assert compose_module._extract_forward_port(document) == 80


def test_no_services_means_no_forward_port():
    assert compose_module._extract_forward_port({'services': {'web': 'not-a-mapping'}}) is None


# ── validation response ───────────────────────────────────────────────────


def test_validation_lists_services_and_environment_keys():
    payload = ComposeValidationRequest(
        app_id="myshop",
        compose_content='services:\n  web:\n    image: nginx\n  db:\n    image: mysql\n',
        env=[{'key': 'A', 'value': '1'}, {'key': 'B', 'value': '2'}],
    )

    response = compose_module.validate_compose_installation(payload)

    assert response.valid is True
    assert response.services == ['web', 'db']
    assert response.environment_keys == ['A', 'B']
    assert response.details == 'Compose content is valid with 2 service(s).'


# ── required repository files ─────────────────────────────────────────────


def test_required_files_include_relative_bind_mounts(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "conf").mkdir(parents=True)
    (workspace / "conf" / "nginx.conf").write_text("server {}\n")
    (workspace / "docker-compose.yml").write_text(
        yaml.dump(
            {
                "services": {
                    "web": {
                        "volumes": [
                            "./conf/nginx.conf:/etc/nginx/nginx.conf:ro",
                            "./conf/missing.conf:/etc/missing.conf",
                            {"source": "./conf/nginx.conf", "target": "/dup"},
                            "/absolute/path:/x",
                            "named_volume:/data",
                        ]
                    }
                }
            }
        )
    )

    files = compose_module._collect_repository_required_files(str(workspace))

    # 只收集工作区里真实存在的相对挂载,并去重排序
    assert files == ['.env', 'conf/nginx.conf', 'docker-compose.yml']


def test_unreadable_workspace_still_lists_the_baseline_files(tmp_path):
    (tmp_path / "docker-compose.yml").write_text('services: [broken\n')

    # 解析失败时直接返回基线清单(未排序),安装流程只需要"这两个文件必须在"
    assert compose_module._collect_repository_required_files(str(tmp_path)) == [
        'docker-compose.yml',
        '.env',
    ]


# ── tracking preparation ──────────────────────────────────────────────────


def test_tracking_uses_a_generated_suffix_and_no_marketplace_name(monkeypatch):
    started = []
    monkeypatch.setattr(
        compose_module,
        'start_app_installation',
        lambda app_id, app_name: started.append((app_id, app_name)) or 'tracking-1',
    )
    monkeypatch.setattr(compose_module.PasswordGenerator, 'generate_random_string', lambda length: 'abcde')

    app_id, tracking_id = compose_module.prepare_compose_install_tracking(_payload())

    assert app_id == 'myshop_abcde'
    assert tracking_id == 'tracking-1'
    # compose 应用不是商店应用,app_name 传 None 才不会匹配到商店图标
    assert started == [('myshop_abcde', None)]


# ── install pipeline ──────────────────────────────────────────────────────


class FakeAppManager:
    _missing_stack_containers_error = 'No containers were created for this stack.'

    def __init__(self):
        self.pushed = []
        self.pulled = []
        self.compose_files = []
        self.snapshot = {}

    def _init_local_repo_and_push_to_remote(self, workspace_path, repo_url):
        self.pushed.append((workspace_path, repo_url))
        # 工作目录在 finally 里会被删掉,推送这一步才是观察写入结果的时机
        for path in sorted(__import__('pathlib').Path(workspace_path).rglob('*')):
            if path.is_file():
                self.snapshot[str(path.relative_to(workspace_path))] = path.read_text()
        with open(f'{workspace_path}/docker-compose.yml') as handle:
            self.compose_files.append(yaml.safe_load(handle))

    def pull_images_from_yml(self, workspace_path, tracking_id):
        self.pulled.append((workspace_path, tracking_id))


class FakePortainer:
    def __init__(self, containers=None):
        self.containers = containers if containers is not None else [{'Names': ['/myshop_web_1'], 'State': 'running'}]
        self.created = []
        self.waited = []
        self.local_endpoint_calls = 0

    def get_local_endpoint_id(self):
        self.local_endpoint_calls += 1
        return 42

    def create_stack_from_repository(self, *args):
        self.created.append(args)
        return {'Id': 1}

    def wait_for_stack_containers(self, app_id, endpoint_id):
        self.waited.append((app_id, endpoint_id))
        return self.containers


class FakeGitea:
    def __init__(self):
        self.repositories = []
        self.waited_for_files = []

    def create_repo(self, app_id):
        self.repositories.append(app_id)
        return f'http://gitea.local/git/{app_id}.git'

    def wait_for_repo_files(self, app_id, repo_url, username, password, required_files):
        self.waited_for_files.append((app_id, required_files))


class FakeProxy:
    calls = []

    def create_proxy_by_app(self, domain_names, app_id, forward_port, advanced_config=None, forward_scheme='http'):
        FakeProxy.calls.append(
            {
                'domain_names': domain_names,
                'app_id': app_id,
                'forward_port': forward_port,
                'advanced_config': advanced_config,
                'forward_scheme': forward_scheme,
            }
        )


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    app_manager = FakeAppManager()
    portainer = FakePortainer()
    gitea = FakeGitea()
    logs = []
    state = {'modified': [], 'removed_logs': [], 'completed': [], 'started': []}

    monkeypatch.setattr(compose_module, 'AppManger', lambda: app_manager)
    monkeypatch.setattr(compose_module, 'PortainerManager', lambda: portainer)
    monkeypatch.setattr(compose_module, 'GiteaManager', lambda: gitea)
    monkeypatch.setattr(compose_module, 'ProxyManager', lambda: FakeProxy())
    monkeypatch.setattr(
        compose_module,
        'IntegrationCredentialProvider',
        lambda: SimpleNamespace(get_gitea_credentials=lambda: SimpleNamespace(username='git', password='secret')),
    )
    monkeypatch.setattr(compose_module, 'add_installing_logs', lambda *args: logs.append(args))
    monkeypatch.setattr(
        compose_module, 'start_app_installation', lambda app_id, app_name: state['started'].append(app_id) or 'tracking-1'
    )
    monkeypatch.setattr(
        compose_module, 'modify_app_information', lambda tracking_id, error: state['modified'].append((tracking_id, error))
    )
    monkeypatch.setattr(
        compose_module, 'remove_installation_logs', lambda tracking_id: state['removed_logs'].append(tracking_id)
    )
    monkeypatch.setattr(compose_module, 'remove_app_installation', lambda tracking_id: state['completed'].append(tracking_id))
    monkeypatch.setattr(compose_module.tempfile, 'mkdtemp', lambda prefix=None: str(tmp_path / 'root'))
    FakeProxy.calls = []
    return SimpleNamespace(
        app_manager=app_manager,
        portainer=portainer,
        gitea=gitea,
        logs=logs,
        state=state,
        root=tmp_path / 'root',
    )


def _workspace(pipeline):
    return [path for path in pipeline.root.iterdir() if path.is_dir()][0]


def test_the_pipeline_writes_the_workspace_and_deploys_the_stack(pipeline):
    compose_module.install_compose_application(
        _payload(
            compose='services:\n  web:\n    image: nginx:1.27\n    ports:\n      - "8080:80"\n',
            env=[{'key': 'TZ', 'value': 'Asia/Shanghai'}],
            mounts=[{'path': 'conf/app.conf', 'content': 'debug=1\n'}],
        )
    )

    snapshot = pipeline.app_manager.snapshot
    # compose 文件里写入了平台网络
    written = yaml.safe_load(snapshot['docker-compose.yml'])
    assert written['networks']['default']['name'] == compose_module._W9_NETWORK
    assert snapshot['.env'] == 'TZ="Asia/Shanghai"\n'
    assert snapshot['conf/app.conf'] == 'debug=1\n'

    assert pipeline.gitea.repositories == ['myshop']
    assert pipeline.app_manager.pushed[0][1] == 'http://gitea.local/git/myshop.git'
    assert pipeline.app_manager.pulled[0][1] == 'tracking-1'
    assert pipeline.gitea.waited_for_files[0][0] == 'myshop'
    assert pipeline.portainer.created[0][:2] == ('myshop', 42)
    assert pipeline.portainer.waited == [('myshop', 42)]

    # 日志按阶段推进,最后清理安装记录
    stages = [entry[1] for entry in pipeline.logs]
    assert stages[0] == 'Initializing installation'
    assert 'Pulling docker image' in stages
    assert 'Starting the services' in stages
    assert stages[-1] == 'Installation complete'
    assert pipeline.state['completed'] == ['tracking-1']
    assert pipeline.state['modified'] == []
    # 工作目录在结束时被删除
    assert not pipeline.root.exists()


def test_container_states_are_reported(pipeline):
    pipeline.portainer.containers = [
        {'Names': ['/myshop_web_1'], 'State': 'running'},
        {'Names': [], 'State': 'exited'},
        'not-a-dict',
    ]

    compose_module.install_compose_application(_payload())

    messages = [entry[2] for entry in pipeline.logs if entry[1] == 'Starting the services']
    assert 'Container myshop_web_1 is running' in messages
    # 名称缺失时回落到 app_id,状态缺失时按 running 处理
    assert 'Container myshop is exited' in messages
    assert 'Container myshop is running' in messages


def test_a_domain_is_published_through_the_proxy(pipeline):
    compose_module.install_compose_application(
        _payload(
            compose='services:\n  web:\n    image: nginx\n    ports:\n      - "8080:80"\n',
            domain='shop.example.com',
        )
    )

    assert FakeProxy.calls == [
        {
            'domain_names': ['shop.example.com'],
            'app_id': 'myshop',
            'forward_port': 80,
            'advanced_config': None,
            'forward_scheme': 'http',
        }
    ]
    assert any(entry[1] == 'Configuring the domain' for entry in pipeline.logs)


def test_an_advanced_proxy_configuration_is_forwarded(pipeline):
    compose_module.install_compose_application(
        _payload(
            compose='services:\n  web:\n    image: nginx\n    ports:\n      - "8080:80"\n',
            domain='shop.example.com',
            mounts=[{'path': 'src/nginx-proxy.conf', 'content': 'proxy_set_header X-Test 1;\n'}],
        )
    )

    assert FakeProxy.calls[0]['advanced_config'] == 'proxy_set_header X-Test 1;\n'


def test_a_domain_without_a_published_port_is_rejected(pipeline):
    with pytest.raises(CustomException) as error:
        compose_module.install_compose_application(
            _payload(compose='services:\n  web:\n    image: nginx\n', domain='shop.example.com')
        )

    assert error.value.status_code == 400
    assert 'does not expose a target port' in error.value.details
    # 失败要落到安装记录里,并清掉临时日志
    assert pipeline.state['modified'] == [('tracking-1', error.value.details)]
    assert pipeline.state['removed_logs'] == ['tracking-1']
    assert pipeline.state['completed'] == []


def test_a_stack_that_starts_no_containers_fails_the_install(pipeline):
    pipeline.portainer.containers = []

    with pytest.raises(CustomException) as error:
        compose_module.install_compose_application(_payload())

    assert error.value.details == FakeAppManager._missing_stack_containers_error
    assert pipeline.state['modified'] == [('tracking-1', FakeAppManager._missing_stack_containers_error)]


def test_an_unexpected_failure_is_wrapped_and_recorded(pipeline, monkeypatch):
    def exploding(app_id):
        raise RuntimeError('gitea is down')

    monkeypatch.setattr(pipeline.gitea, 'create_repo', exploding)

    with pytest.raises(CustomException) as error:
        compose_module.install_compose_application(_payload())

    assert error.value.status_code == 500
    assert pipeline.state['modified'] == [('tracking-1', 'Compose installation failed')]
    assert pipeline.state['removed_logs'] == ['tracking-1']


def test_an_explicit_endpoint_and_tracking_are_used(pipeline):
    compose_module.install_compose_application(
        _payload(), endpoint_id=7, tracked_app_id='myshop_zzzzz', tracking_id='tracking-9'
    )

    # 传了 endpoint 就不再查询本地端点;传了 tracking 就不再新建安装记录
    assert pipeline.portainer.local_endpoint_calls == 0
    assert pipeline.state['started'] == []
    assert pipeline.portainer.created[0][:2] == ('myshop_zzzzz', 7)
    assert pipeline.state['completed'] == ['tracking-9']


def test_the_workspace_is_cleaned_up_even_when_the_install_fails(pipeline, monkeypatch):
    def exploding(app_id):
        raise RuntimeError('boom')

    monkeypatch.setattr(pipeline.gitea, 'create_repo', exploding)

    with pytest.raises(CustomException):
        compose_module.install_compose_application(_payload())

    assert not pipeline.root.exists()
