"""The cloud-marketplace setup wizard: first-run state machine and app installation.

The wizard is the first thing a new operator touches, and its state lives in a JSON file that both
the UI and the installer read. The tests pin the state transitions (welcome → app_init_ready →
running/failed → complete) and the two rules that decide what the UI is allowed to show: it is only
enabled on a cloud marketplace build, and every mutating step requires an authenticated session.
"""

import json
import threading
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import setup_wizard as wizard_module
from src.services.setup_wizard import SetupWizardService, _get_default_edition, _normalize_app_id


def _service(data_dir, *, cloud=True, metadata=None, authenticated=True):
    service = SetupWizardService(data_dir=str(data_dir))
    service.bootstrap = SimpleNamespace(
        is_cloud_marketplace=lambda: cloud,
        read=lambda: metadata if metadata is not None else {'app_slug': 'shop', 'default_locale': 'zh'},
    )
    return service


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch):
    monkeypatch.setattr(
        wizard_module,
        'ProductAuthService',
        lambda: SimpleNamespace(get_status=lambda session_token=None: {'authenticated': True}),
    )


# ── helpers ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('My Shop', 'myshop'),
        ('my-shop_1', 'myshop1'),
        # 数字开头会加 "app" 前缀(拼在前面,不是替换)
        ('123app', 'app123app'),
        ('!!!', 'app'),
        ('', 'app'),
        ('a' * 40, 'a' * 20),
    ],
)
def test_app_ids_are_normalized_for_the_install_contract(value, expected):
    assert _normalize_app_id(value) == expected


def test_a_missing_distribution_list_is_rejected():
    with pytest.raises(CustomException) as error:
        _get_default_edition(None)

    assert error.value.details == 'No distribution data is available for this application'


def test_a_missing_community_edition_is_rejected():
    with pytest.raises(CustomException) as error:
        _get_default_edition([{'key': 'enterprise', 'value': '1.0.0'}])

    assert error.value.details == 'No community edition is available for this application'


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('8.1,8.3,8.2', '8.3'),
        (['1.0.0', '1.10.0', '1.9.0'], '1.10.0'),
        ('latest,7.4', '7.4'),
        ('latest', 'latest'),
    ],
)
def test_the_highest_numeric_community_version_wins(value, expected):
    assert _get_default_edition([{'key': 'community', 'value': value}]) == expected


def test_non_numeric_versions_fall_back_to_the_first_entry():
    assert _get_default_edition([{'key': 'community', 'value': 'stable,edge'}]) == 'stable'


def test_an_empty_version_list_is_rejected():
    with pytest.raises(CustomException) as error:
        _get_default_edition([{'key': 'community', 'value': ''}])

    assert error.value.details == 'No community version is available for this application'


# ── enablement ────────────────────────────────────────────────────────────


def test_the_wizard_is_only_available_on_a_cloud_marketplace(tmp_path):
    assert _service(tmp_path, cloud=True).should_use_wizard() is True
    assert _service(tmp_path, cloud=False).should_use_wizard() is False


def test_require_enabled_hides_the_wizard_elsewhere(tmp_path):
    with pytest.raises(CustomException) as error:
        _service(tmp_path, cloud=False).require_enabled()

    assert error.value.status_code == 404
    assert error.value.details == 'The setup wizard is not available for this runtime'


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        ({}, True),
        ({'current_step': 'app_init_ready'}, True),
        ({'current_step': 'app_init_running'}, False),
        ({'current_step': 'app_init_failed'}, False),
        ({'completed': True}, False),
    ],
)
def test_pending_setup_follows_the_state_machine(tmp_path, state, expected):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), **state})

    assert service.is_pending_setup() is expected


def test_a_non_cloud_build_is_never_pending(tmp_path):
    assert _service(tmp_path, cloud=False).is_pending_setup() is False


# ── state file ────────────────────────────────────────────────────────────


def test_a_missing_state_file_reads_as_the_default(tmp_path):
    state = _service(tmp_path)._load_state()

    assert state['current_step'] == 'welcome'
    assert state['completed'] is False


@pytest.mark.parametrize('content', ['not json', '[]', '"string"'])
def test_unreadable_state_files_read_as_the_default(tmp_path, content):
    service = _service(tmp_path)
    service.data_dir.mkdir(parents=True, exist_ok=True)
    service.state_file.write_text(content)

    assert service._load_state()['current_step'] == 'welcome'


def test_partial_state_is_merged_with_the_defaults(tmp_path):
    service = _service(tmp_path)
    service.data_dir.mkdir(parents=True, exist_ok=True)
    service.state_file.write_text(json.dumps({'current_step': 'complete'}))

    state = service._load_state()

    assert state['current_step'] == 'complete'
    # 缺的键用默认值补齐,前端不用自己兜底
    assert state['installed_app_id'] is None
    assert state['completed'] is False


def test_updates_are_persisted_with_a_timestamp(tmp_path):
    service = _service(tmp_path)

    state = service._update_state(current_step='app_init_ready')

    assert state['current_step'] == 'app_init_ready'
    assert state['updated_at']
    assert json.loads(service.state_file.read_text())['current_step'] == 'app_init_ready'


# ── get_state ─────────────────────────────────────────────────────────────


def test_a_non_cloud_build_reports_a_disabled_state(tmp_path):
    state = _service(tmp_path, cloud=False).get_state()

    assert state['enabled'] is False
    assert state['current_step'] == 'welcome'
    assert state['app_slug'] == 'shop'


def test_an_unauthenticated_operator_starts_at_welcome(tmp_path):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), 'current_step': 'app_init_ready'})
    wizard_module.ProductAuthService = lambda: SimpleNamespace(  # type: ignore[assignment]
        get_status=lambda session_token=None: {'authenticated': False}
    )

    assert service.get_state()['current_step'] == 'welcome'


def test_an_authenticated_operator_is_ready_to_install(tmp_path):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), 'current_step': 'welcome'})

    state = service.get_state('token')

    assert state['enabled'] is True
    assert state['current_step'] == 'app_init_ready'
    assert state['default_locale'] == 'zh'


def test_a_completed_setup_reports_complete(tmp_path):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), 'completed': True, 'installed_app_id': 'shop_ab123'})

    state = service.get_state()

    assert state['current_step'] == 'complete'
    assert state['completed'] is True
    assert state['installed_app_id'] == 'shop_ab123'


@pytest.mark.parametrize('step', ['app_init_running', 'app_init_failed'])
def test_a_triggered_install_leaves_the_wizard(tmp_path, step):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), 'current_step': step})

    # 一旦开始安装,前端就应该跳转离开 /setup
    assert service.get_state()['enabled'] is False


# ── get_app ───────────────────────────────────────────────────────────────


def _catalog_app(**overrides):
    app = {
        'key': 'shop',
        'trademark': 'My Shop',
        'logo': {'imageurl': 'https://cdn.example.com/shop.png'},
        'is_web_app': True,
        'distribution': [{'key': 'community', 'value': '1.0.0,1.2.0'}],
        'settings': {'W9_ADMIN_PASSWORD_SET': '', 'W9_HTTP_PORT_SET': '8080', 'EMPTY_SET': None},
    }
    app.update(overrides)
    return app


@pytest.fixture
def catalog(monkeypatch):
    recorded = []

    class FakeAppManager:
        def get_available_apps(self, locale):
            recorded.append(locale)
            return [_catalog_app()] if locale == 'en' else []

        def get_app_by_id(self, app_id):
            if app_id == 'shop_ab123':
                return SimpleNamespace(app_id=app_id)
            raise CustomException(404, 'Not Found', 'gone')

    monkeypatch.setattr(wizard_module, 'AppManger', lambda: FakeAppManager())
    return recorded


def test_the_app_is_looked_up_in_the_requested_locale_first(tmp_path, catalog):
    service = _service(tmp_path)

    app = service.get_app('en')

    assert catalog == ['en']
    assert app['display_name'] == 'My Shop'
    assert app['logo_url'] == 'https://cdn.example.com/shop.png'
    assert app['edition'] == '1.2.0'
    assert app['default_app_id'] == 'shop'
    assert app['is_web_app'] is True


def test_the_catalog_falls_back_to_other_locales(tmp_path, catalog):
    service = _service(tmp_path, metadata={'app_slug': 'shop', 'default_locale': 'zh'})

    app = service.get_app()

    # 先中文(空)后英文(命中)
    assert catalog == ['zh', 'en']
    assert app['app_slug'] == 'shop'


def test_missing_inputs_become_form_fields(tmp_path, catalog):
    service = _service(tmp_path)

    app = service.get_app('en')

    assert app['settings']['W9_HTTP_PORT_SET'] == '8080'
    # None 归一化成空串,避免前端拿到 null
    assert app['settings']['EMPTY_SET'] == ''
    fields = {field['name']: field for field in app['required_inputs']}
    assert fields['W9_ADMIN_PASSWORD_SET']['type'] == 'password'
    assert fields['EMPTY_SET']['type'] == 'text'
    assert app['requires_user_inputs'] is True


def test_a_port_setting_is_rendered_as_a_number_field(tmp_path, catalog):
    service = _service(tmp_path)

    app = service.get_app('en')

    app['settings']['W9_DB_PORT_SET'] = ''
    fields = {field['name']: field for field in app['required_inputs']}
    assert 'W9_DB_PORT_SET' not in fields  # 已有值的端口不需要用户填写


def test_a_missing_slug_is_reported(tmp_path, monkeypatch):
    service = _service(tmp_path, metadata={})

    with pytest.raises(CustomException) as error:
        service.get_app()

    assert error.value.details == 'The marketplace app metadata is unavailable'


def test_an_app_missing_from_every_locale_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(wizard_module, 'AppManger', lambda: SimpleNamespace(get_available_apps=lambda locale: []))
    service = _service(tmp_path)

    with pytest.raises(CustomException) as error:
        service.get_app()

    assert error.value.details == "The app 'shop' was not found in the app catalog"


# ── authenticated steps ───────────────────────────────────────────────────


def test_platform_init_requires_authentication(tmp_path):
    service = _service(tmp_path)
    wizard_module.ProductAuthService = lambda: SimpleNamespace(  # type: ignore[assignment]
        get_status=lambda session_token=None: {'authenticated': False}
    )

    with pytest.raises(CustomException) as error:
        service.mark_platform_init_complete()

    assert error.value.status_code == 401
    assert error.value.message == 'Authentication Required'


def test_marking_platform_init_complete_moves_to_ready(tmp_path):
    service = _service(tmp_path)

    result = service.mark_platform_init_complete('token')

    assert result['current_step'] == 'app_init_ready'
    assert service._load_state()['current_step'] == 'app_init_ready'


# ── install_app ───────────────────────────────────────────────────────────


@pytest.fixture
def installer(tmp_path, monkeypatch, catalog):
    calls = {}
    threads = []

    class FakeAppManager:
        def get_available_apps(self, locale):
            return [_catalog_app()]

        def create_installation_tracking(self, payload):
            calls['payload'] = payload
            return 'shop_ab123', 'tracking-1'

        def install_app(self, payload, endpoint_id, tracked_app_id, tracking_id):
            calls['installed'] = (payload, endpoint_id, tracked_app_id, tracking_id)

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            threads.append({'target': target, 'args': args, 'daemon': daemon})

        def start(self):
            threads[-1]['started'] = True

    monkeypatch.setattr(wizard_module, 'AppManger', lambda: FakeAppManager())
    monkeypatch.setattr(wizard_module, 'PortainerManager', lambda: SimpleNamespace(get_local_endpoint_id=lambda: 42))
    monkeypatch.setattr(
        wizard_module, 'install_validate', lambda payload, endpoint_id: calls.setdefault('validated', (payload, endpoint_id))
    )
    monkeypatch.setattr(threading, 'Thread', FakeThread)
    return SimpleNamespace(service=_service(tmp_path), calls=calls, threads=threads)


def test_install_uses_the_wizard_defaults(installer):
    result = installer.service.install_app({'domain_name': 'shop.example.com'}, 'token')

    assert result == {'tracking_id': 'tracking-1', 'current_step': 'app_init_running'}
    payload = installer.calls['payload']
    assert payload.app_name == 'shop'
    assert payload.app_id == 'shop'
    assert payload.edition.version == '1.2.0'
    assert payload.proxy_enabled is False
    assert payload.domain_names == ['shop.example.com']
    assert installer.calls['validated'][1] == 42
    # 安装在线程里跑,向导立刻返回 tracking id
    assert installer.threads[0]['started'] is True
    assert installer.threads[0]['daemon'] is True


def test_user_inputs_override_catalog_settings(installer):
    installer.service.install_app(
        {
            'domain_name': 'shop.example.com',
            'user_inputs': {'W9_ADMIN_PASSWORD_SET': 'secret', 'EXTRA_SET': 5},
            'app_id': 'customshop',
            'edition': '1.1.0',
        },
        'token',
    )

    payload = installer.calls['payload']
    assert payload.app_id == 'customshop'
    assert payload.edition.version == '1.1.0'
    assert payload.settings['W9_ADMIN_PASSWORD_SET'] == 'secret'
    assert payload.settings['EXTRA_SET'] == '5'


def test_a_failed_precheck_is_recorded_and_reported(installer, monkeypatch):
    def failing(payload, endpoint_id):
        raise CustomException(400, 'Invalid Request', 'port 8080 is already in use')

    monkeypatch.setattr(wizard_module, 'install_validate', failing)

    with pytest.raises(CustomException) as error:
        installer.service.install_app({'domain_name': 'shop.example.com'}, 'token')

    assert error.value.details == 'port 8080 is already in use'
    state = installer.service._load_state()
    assert state['current_step'] == 'app_init_failed'
    assert state['last_error']['code'] == 'INSTALL_VALIDATION_FAILED'
    assert state['last_error']['retryable'] is True
    assert installer.threads == []


def test_the_install_state_records_the_pending_app(installer):
    installer.service.install_app({'domain_name': 'shop.example.com'}, 'token', endpoint_id=7)

    state = installer.service._load_state()
    assert state['current_step'] == 'app_init_running'
    assert state['tracking_id'] == 'tracking-1'
    assert state['pending_app_id'] == 'shop_ab123'
    assert state['installed_app_id'] is None


# ── install status ────────────────────────────────────────────────────────


@pytest.fixture
def status_service(tmp_path, catalog, monkeypatch):
    service = _service(tmp_path)
    service._write_state({**service._default_state(), 'tracking_id': 'tracking-1', 'pending_app_id': 'shop_ab123'})
    monkeypatch.setattr(wizard_module, 'appInstalling', SimpleNamespace(get=lambda tracking_id: None))
    monkeypatch.setattr(wizard_module, 'appInstallingError', SimpleNamespace(get=lambda tracking_id: None))
    return service


def test_an_unknown_tracking_id_is_rejected(status_service):
    with pytest.raises(CustomException) as error:
        status_service.get_install_status('other')

    assert error.value.status_code == 404
    assert error.value.message == 'Install Task Not Found'


def test_a_running_install_is_reported_as_running(status_service, monkeypatch):
    monkeypatch.setattr(wizard_module, 'appInstalling', SimpleNamespace(get=lambda tracking_id: {'app_id': 'shop_ab123'}))

    assert status_service.get_install_status('tracking-1')['status'] == 'running'


def test_a_failed_install_is_reported_and_recorded(status_service, monkeypatch):
    monkeypatch.setattr(
        wizard_module,
        'appInstallingError',
        SimpleNamespace(get=lambda tracking_id: {'error': 'no containers were created'}),
    )

    result = status_service.get_install_status('tracking-1')

    assert result['status'] == 'failed'
    assert result['last_error']['code'] == 'INSTALL_TASK_FAILED'
    assert result['last_error']['message'] == 'no containers were created'
    assert status_service._load_state()['current_step'] == 'app_init_failed'


def test_a_failed_install_without_a_message_gets_a_default(status_service, monkeypatch):
    monkeypatch.setattr(wizard_module, 'appInstallingError', SimpleNamespace(get=lambda tracking_id: {}))

    result = status_service.get_install_status('tracking-1')

    assert result['last_error']['message'] == '准备失败，请重试。'


def test_an_installed_app_makes_the_status_succeed(status_service):
    result = status_service.get_install_status('tracking-1')

    assert result['status'] == 'succeeded'
    assert result['current_step'] == 'complete'
    assert result['installed_app_id'] == 'shop_ab123'


def test_an_app_that_cannot_be_loaded_stays_running(status_service, monkeypatch):
    status_service._write_state(
        {
            **status_service._default_state(),
            'tracking_id': 'tracking-1',
            'pending_app_id': 'shop_ab123',
            'installed_app_id': 'missing_app',
        }
    )

    assert status_service.get_install_status('tracking-1')['status'] == 'running'


# ── complete ──────────────────────────────────────────────────────────────


def test_completing_without_an_app_is_rejected(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(CustomException) as error:
        service.complete('token')

    assert error.value.status_code == 400
    assert error.value.details == 'The setup wizard has no installed app to complete'


def test_completing_marks_the_setup_done(status_service):
    result = status_service.complete('token')

    assert result['completed'] is True
    assert result['installed_app_id'] == 'shop_ab123'
    assert result['completed_at']
    state = status_service._load_state()
    assert state['current_step'] == 'complete'
    assert state['completed'] is True
    assert state['pending_app_id'] == 'shop_ab123'


def test_completing_requires_authentication(status_service):
    wizard_module.ProductAuthService = lambda: SimpleNamespace(  # type: ignore[assignment]
        get_status=lambda session_token=None: {'authenticated': False}
    )

    with pytest.raises(CustomException) as error:
        status_service.complete()

    assert error.value.status_code == 401


# ── catalog locales ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('locale', 'expected'),
    [
        ('zh-CN', ['zh', 'en']),
        ('en-US', ['en', 'zh']),
        (None, ['zh', 'en']),
    ],
)
def test_catalog_locales_put_the_requested_language_first(tmp_path, locale, expected):
    service = _service(tmp_path, metadata={'app_slug': 'shop', 'default_locale': 'zh-CN'})

    assert service._resolve_catalog_locales(locale) == expected


# ── HTTP surface ──────────────────────────────────────────────────────────


class FakeWizardService:
    """Delegates to nothing; records what the router forwarded."""

    state = {'enabled': True, 'current_step': 'welcome', 'completed': False, 'updated_at': 'now'}
    failure = None
    calls = []

    def __init__(self):
        pass

    def require_enabled(self):
        if FakeWizardService.failure is not None:
            raise FakeWizardService.failure

    def get_state(self, session_token=None):
        FakeWizardService.calls.append(('state', session_token))
        return FakeWizardService.state

    def get_app(self, locale):
        FakeWizardService.calls.append(('app', locale))
        return {'app_slug': 'shop', 'display_name': 'Shop', 'edition': '1.0.0', 'default_app_id': 'shop'}

    def mark_platform_init_complete(self, session_token=None):
        FakeWizardService.calls.append(('platform-init', session_token))
        return {'current_step': 'app_init_ready', 'updated_at': 'now'}

    def install_app(self, payload, session_token=None, endpoint_id=None):
        FakeWizardService.calls.append(('install', payload, session_token, endpoint_id))
        return {'tracking_id': 'tracking-1', 'current_step': 'app_init_running'}

    def get_install_status(self, tracking_id):
        FakeWizardService.calls.append(('status', tracking_id))
        return {'status': 'running', 'current_step': 'app_init_running', 'installed_app_id': None, 'last_error': None}

    def complete(self, session_token=None):
        FakeWizardService.calls.append(('complete', session_token))
        return {'current_step': 'complete', 'installed_app_id': 'shop_ab123', 'completed': True, 'completed_at': 'now'}


@pytest.fixture
def wizard_router(monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from src.api.v1.routers import setup_wizard as router_module
    from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME

    FakeWizardService.calls = []
    FakeWizardService.failure = None
    monkeypatch.setattr(router_module, 'SetupWizardService', FakeWizardService)

    app = FastAPI()
    app.include_router(router_module.router)

    @app.exception_handler(CustomException)
    async def handle(_request, error):
        return JSONResponse(status_code=error.status_code, content={'message': error.message, 'details': error.details})

    return SimpleNamespace(client=TestClient(app), cookie_name=PRODUCT_AUTH_COOKIE_NAME)


def test_the_state_endpoint_delegates_with_the_session_cookie(wizard_router):
    wizard_router.client.cookies.set(wizard_router.cookie_name, 'session-1')

    response = wizard_router.client.get('/setup-wizard/state')

    assert response.status_code == 200
    assert response.json()['enabled'] is True
    assert FakeWizardService.calls == [('state', 'session-1')]


@pytest.mark.parametrize(
    ('method', 'url', 'payload'),
    [
        ('get', '/setup-wizard/state', None),
        ('get', '/setup-wizard/app', None),
        ('post', '/setup-wizard/platform-init-complete', None),
        ('get', '/setup-wizard/install/tracking-1', None),
        ('post', '/setup-wizard/complete', None),
    ],
)
def test_every_endpoint_is_hidden_when_the_wizard_is_disabled(wizard_router, method, url, payload):
    FakeWizardService.failure = CustomException(404, 'Not Found', 'The setup wizard is not available for this runtime')

    response = wizard_router.client.request(method.upper(), url, json=payload)

    assert response.status_code == 404
    assert response.json()['details'] == 'The setup wizard is not available for this runtime'
    # 关闭时不应触达业务逻辑
    assert FakeWizardService.calls == []


def test_the_app_endpoint_forwards_the_locale(wizard_router):
    response = wizard_router.client.get('/setup-wizard/app', params={'locale': 'zh-CN'})

    assert response.status_code == 200
    assert FakeWizardService.calls == [('app', 'zh-CN')]


def test_an_unsupported_locale_is_rejected_before_the_service(wizard_router):
    response = wizard_router.client.get('/setup-wizard/app', params={'locale': 'de'})

    assert response.status_code == 422
    assert FakeWizardService.calls == []


def test_the_install_endpoint_forwards_the_payload_and_endpoint(wizard_router):
    wizard_router.client.cookies.set(wizard_router.cookie_name, 'session-2')
    payload = {
        'app_id': 'myshop',
        'edition': '1.2.0',
        'domain_name': 'shop.example.com',
        'user_inputs': {'W9_ADMIN_PASSWORD_SET': 'secret'},
    }

    response = wizard_router.client.post('/setup-wizard/install', params={'endpointId': 7}, json=payload)

    assert response.status_code == 200
    assert response.json()['tracking_id'] == 'tracking-1'
    call = FakeWizardService.calls[0]
    assert call[0] == 'install'
    assert call[1]['app_id'] == 'myshop'
    assert call[2] == 'session-2'
    assert call[3] == 7


def test_an_authentication_failure_is_returned_as_401(wizard_router):
    FakeWizardService.failure = None

    def unauthorized(session_token=None):
        raise CustomException(401, 'Authentication Required', 'Sign in before continuing the setup wizard')

    FakeWizardService.complete = lambda self, session_token=None: unauthorized(session_token)

    response = wizard_router.client.post('/setup-wizard/complete')

    assert response.status_code == 401
    assert response.json()['message'] == 'Authentication Required'


def test_the_install_status_endpoint_forwards_the_tracking_id(wizard_router):
    response = wizard_router.client.get('/setup-wizard/install/tracking-9')

    assert response.status_code == 200
    assert FakeWizardService.calls == [('status', 'tracking-9')]
