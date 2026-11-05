"""`ProxyManager`: how Nginx Proxy Manager answers are translated into the API's error contract.

Every console action that touches a proxy host - creating, renaming domains, changing the forward
port, adding a certificate - funnels through these helpers. The tests pin the two things that keep
breaking: which status code an operator sees (`400` for a rejected request, `500` for an upstream
failure) and which fields are forwarded when a proxy host is updated.
"""

import json
import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import restore_module_stubs, stub_module

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='proxy-manager-tests-'))

git_module = types.ModuleType('git')
git_module.Repo = object
git_module.GitCommandError = RuntimeError
stub_module('git', git_module)
stub_module('jwt', types.ModuleType('jwt'))
keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
stub_module('keyring', keyring_module)

from src.core.exception import CustomException
from src.services import proxy_manager as proxy_manager_module
from src.services.proxy_manager import ProxyManager

restore_module_stubs()


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        if text is not None:
            self.text = text
        elif isinstance(payload, Exception) or payload is None:
            self.text = ''
        else:
            self.text = json.dumps(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeNginx:
    """Records every call so the tests can assert on the forwarded payload."""

    def __init__(self):
        self.proxy_hosts = []
        self.certificates = []
        self.update_calls = []
        self.created_certificates = []
        self.update_response = FakeResponse(200, {'id': 4})
        self.create_certificate_response = FakeResponse(201, {'id': 42})
        self.get_proxy_hosts_response = None

    def get_proxy_hosts(self):
        if self.get_proxy_hosts_response is not None:
            return self.get_proxy_hosts_response
        return FakeResponse(200, self.proxy_hosts)

    def get_certificates(self):
        return FakeResponse(200, self.certificates)

    def update_proxy_host(self, proxy_id, json):
        self.update_calls.append({'proxy_id': proxy_id, 'json': json})
        return self.update_response

    def create_custom_certificate(self, nice_name, certificate_pem, key_pem):
        self.created_certificates.append({'nice_name': nice_name, 'certificate_pem': certificate_pem, 'key_pem': key_pem})
        return self.create_certificate_response


@pytest.fixture
def proxy():
    manager = object.__new__(ProxyManager)
    manager.nginx = FakeNginx()
    return manager


EXISTING_PROXY_HOST = {
    'id': 4,
    'domain_names': ['wordpress.example.com'],
    'forward_host': 'wordpress_abc',
    'forward_port': 8080,
    'forward_scheme': 'http',
    'certificate_id': 0,
    'ssl_forced': False,
    'created_on': '2024-01-01',
    'modified_on': '2024-01-02',
    'owner_user_id': 1,
    'enabled': True,
    'certificate': {'id': 0},
    'owner': {'id': 1},
    'access_list': [],
    'use_default_location': True,
    'ipv6': False,
    'meta': {'keep': 'me'},
}


# ── _handler_nginx_error ──────────────────────────────────────────────────


def test_upstream_server_error_becomes_a_500(proxy):
    response = FakeResponse(502, text='{"error": {"message": "nginx is down"}}')

    with pytest.raises(CustomException) as error:
        proxy._handler_nginx_error(response)

    assert error.value.status_code == 500
    assert error.value.message == 'Internal Server Error'
    assert error.value.details == 'nginx is down'


def test_client_error_becomes_a_400(proxy):
    response = FakeResponse(400, text='{"error": {"message": "host already exists"}}')

    with pytest.raises(CustomException) as error:
        proxy._handler_nginx_error(response)

    assert error.value.status_code == 400
    assert error.value.message == 'Invalid Request'
    assert error.value.details == 'host already exists'


def test_top_level_message_wins_over_the_nested_one(proxy):
    response = FakeResponse(400, text='{"message": "chosen message", "error": {"message": "nested"}}')

    with pytest.raises(CustomException) as error:
        proxy._handler_nginx_error(response)

    assert error.value.details == 'chosen message'


def test_plain_text_body_is_used_as_the_detail(proxy):
    response = FakeResponse(500, text='  502 Bad Gateway  ')

    with pytest.raises(CustomException) as error:
        proxy._handler_nginx_error(response)

    assert error.value.details == '502 Bad Gateway'


def test_empty_body_falls_back_to_a_generic_detail(proxy):
    response = FakeResponse(500, text='')

    with pytest.raises(CustomException) as error:
        proxy._handler_nginx_error(response)

    assert error.value.details == 'Unknown Error'


# ── check_proxy_host_exists ───────────────────────────────────────────────


def test_domain_conflict_lists_the_offending_domains(proxy):
    proxy.nginx.proxy_hosts = [{'id': 9, 'domain_names': ['Wordpress.Example.com']}]

    with pytest.raises(CustomException) as error:
        proxy.check_proxy_host_exists(['wordpress.example.com', 'new.example.com'])

    assert error.value.status_code == 400
    assert error.value.details == "['wordpress.example.com'] already used"


def test_domain_conflict_is_detected_regardless_of_stray_spaces(proxy):
    proxy.nginx.proxy_hosts = [{'id': 9, 'domain_names': ['  wordpress.example.com ']}]

    with pytest.raises(CustomException):
        proxy.check_proxy_host_exists(['WORDPRESS.EXAMPLE.COM'])


def test_the_edited_proxy_host_is_excluded_from_the_conflict_check(proxy):
    proxy.nginx.proxy_hosts = [{'id': 4, 'domain_names': ['wordpress.example.com']}]

    proxy.check_proxy_host_exists(['wordpress.example.com'], exclude_proxy_id=4)


def test_free_domains_pass_the_conflict_check(proxy):
    proxy.nginx.proxy_hosts = [{'id': 9, 'domain_names': ['other.example.com']}]

    assert proxy.check_proxy_host_exists(['wordpress.example.com']) is None


def test_a_failing_listing_is_reported_as_a_request_error(proxy):
    proxy.nginx.get_proxy_hosts_response = FakeResponse(500, text='boom')

    with pytest.raises(CustomException) as error:
        proxy.check_proxy_host_exists(['wordpress.example.com'])

    assert error.value.status_code == 500
    assert error.value.details == 'boom'


def test_unreadable_proxy_hosts_are_wrapped(proxy):
    proxy.nginx.get_proxy_hosts_response = FakeResponse(200, ValueError('not json'))

    with pytest.raises(CustomException) as error:
        proxy.check_proxy_host_exists(['wordpress.example.com'])

    assert error.value.details == 'Internal Server Error'


# ── update_proxy_by_app / update_proxy_host_settings / update_proxy_port_by_app ──


def test_update_proxy_by_app_only_sends_the_writable_fields(proxy):
    proxy.nginx.proxy_hosts = [dict(EXISTING_PROXY_HOST)]

    proxy.update_proxy_by_app(4, ['new.example.com'], certificate_id=7, ssl_forced=True)

    payload = proxy.nginx.update_calls[0]['json']
    assert payload['domain_names'] == ['new.example.com']
    assert payload['certificate_id'] == 7
    assert payload['ssl_forced'] is True
    assert payload['meta'] == {'keep': 'me'}
    for dropped in ('id', 'created_on', 'owner', 'certificate', 'enabled'):
        assert dropped not in payload


def test_update_proxy_by_app_keeps_the_current_ssl_flag_when_not_given(proxy):
    proxy.nginx.proxy_hosts = [dict(EXISTING_PROXY_HOST, ssl_forced=True)]

    proxy.update_proxy_by_app(4, ['new.example.com'])

    payload = proxy.nginx.update_calls[0]['json']
    assert payload['ssl_forced'] is True
    assert payload['certificate_id'] == 0


def test_update_proxy_by_app_rejects_an_unknown_proxy_host(proxy):
    proxy.nginx.proxy_hosts = []

    with pytest.raises(CustomException) as error:
        proxy.update_proxy_by_app(4, ['new.example.com'])

    assert error.value.details == 'Proxy host:4 not found'
    assert proxy.nginx.update_calls == []


def test_update_proxy_by_app_reports_an_upstream_rejection(proxy):
    proxy.nginx.proxy_hosts = [dict(EXISTING_PROXY_HOST)]
    proxy.nginx.update_response = FakeResponse(400, text='{"error": {"message": "invalid domain"}}')

    with pytest.raises(CustomException) as error:
        proxy.update_proxy_by_app(4, ['bad domain'])

    assert error.value.status_code == 400
    assert error.value.details == 'invalid domain'


def test_update_proxy_host_settings_rewrites_the_routing_target(proxy):
    proxy.nginx.proxy_hosts = [dict(EXISTING_PROXY_HOST)]

    proxy.update_proxy_host_settings(
        4,
        ['wordpress.example.com'],
        forward_host='wordpress_new',
        forward_port=9090,
        forward_scheme='https',
        certificate_id=None,
        ssl_forced=True,
    )

    payload = proxy.nginx.update_calls[0]['json']
    assert payload['forward_host'] == 'wordpress_new'
    assert payload['forward_port'] == 9090
    assert payload['forward_scheme'] == 'https'
    assert payload['certificate_id'] == 0
    assert payload['ssl_forced'] is True
    assert 'id' not in payload


def test_update_proxy_host_settings_rejects_an_unknown_proxy_host(proxy):
    proxy.nginx.proxy_hosts = []

    with pytest.raises(CustomException) as error:
        proxy.update_proxy_host_settings(4, ['a.example.com'], forward_host='h', forward_port=80)

    assert error.value.details == 'Proxy host:4 not found'


def test_update_proxy_port_by_app_only_changes_the_port(proxy):
    proxy.nginx.proxy_hosts = [dict(EXISTING_PROXY_HOST)]

    proxy.update_proxy_port_by_app(4, 9090)

    payload = proxy.nginx.update_calls[0]['json']
    assert payload['forward_port'] == 9090
    assert payload['domain_names'] == ['wordpress.example.com']
    assert payload['forward_host'] == 'wordpress_abc'


def test_update_proxy_port_by_app_rejects_an_unknown_proxy_host(proxy):
    proxy.nginx.proxy_hosts = []

    with pytest.raises(CustomException) as error:
        proxy.update_proxy_port_by_app(4, 9090)

    assert error.value.details == 'Proxy host:4 not found'


# ── ensure_inner_certificate ──────────────────────────────────────────────


def test_existing_inner_certificate_is_reused(proxy):
    proxy.nginx.certificates = [{'id': 5, 'nice_name': 'websoft9-inner'}]

    assert proxy.ensure_inner_certificate() == {'id': 5, 'nice_name': 'websoft9-inner'}
    assert proxy.nginx.created_certificates == []


def test_missing_self_signed_files_are_generated_and_uploaded(proxy, monkeypatch, tmp_path):
    ssl_dir = tmp_path / 'custom_ssl'
    monkeypatch.setenv('WEBSOFT9_NPM_CERT_MARKER', str(ssl_dir / 'self.cert'))
    monkeypatch.setenv('WEBSOFT9_NPM_SSL_KEY_PATH', str(ssl_dir / 'self.key'))
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        # Emulate openssl writing both files.
        ssl_dir.mkdir(parents=True, exist_ok=True)
        (ssl_dir / 'self.cert').write_text('-----BEGIN CERTIFICATE-----\ncert\n')
        (ssl_dir / 'self.key').write_text('-----BEGIN PRIVATE KEY-----\nkey\n')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(proxy_manager_module.subprocess, 'run', fake_run)
    proxy.nginx.create_certificate_response = FakeResponse(201, {'id': 77, 'nice_name': 'websoft9-inner'})

    result = proxy.ensure_inner_certificate()

    assert result == {'id': 77, 'nice_name': 'websoft9-inner'}
    assert calls[0][:2] == ['openssl', 'req']
    assert proxy.nginx.created_certificates[0]['nice_name'] == 'websoft9-inner'
    assert proxy.nginx.created_certificates[0]['certificate_pem'].startswith('-----BEGIN CERTIFICATE-----')


def test_certificate_generation_failure_is_not_fatal(proxy, monkeypatch, tmp_path):
    monkeypatch.setenv('WEBSOFT9_NPM_CERT_MARKER', str(tmp_path / 'missing.cert'))
    monkeypatch.setenv('WEBSOFT9_NPM_SSL_KEY_PATH', str(tmp_path / 'missing.key'))

    def failing_run(command, **kwargs):
        raise OSError('openssl is not installed')

    monkeypatch.setattr(proxy_manager_module.subprocess, 'run', failing_run)

    assert proxy.ensure_inner_certificate() is None
    assert proxy.nginx.created_certificates == []


def test_upload_failure_is_not_fatal(proxy, monkeypatch, tmp_path):
    cert_file = tmp_path / 'self.cert'
    key_file = tmp_path / 'self.key'
    cert_file.write_text('-----BEGIN CERTIFICATE-----\ncert\n')
    key_file.write_text('-----BEGIN PRIVATE KEY-----\nkey\n')
    monkeypatch.setenv('WEBSOFT9_NPM_CERT_MARKER', str(cert_file))
    monkeypatch.setenv('WEBSOFT9_NPM_SSL_KEY_PATH', str(key_file))
    proxy.nginx.create_certificate_response = FakeResponse(500, text='upload failed')

    assert proxy.ensure_inner_certificate() is None


# ── _resolve_default_letsencrypt_email ────────────────────────────────────


class FakeSmtpService:
    def __init__(self, from_email):
        self._from_email = from_email

    def get_settings(self):
        return SimpleNamespace(from_email=self._from_email)


def _patch_email_sources(monkeypatch, smtp_email=None, npm_username=None):
    smtp_module = types.ModuleType('src.services.smtp_service')

    class SmtpService:
        def get_settings(self):
            if smtp_email is None:
                raise RuntimeError('smtp not configured')
            return SimpleNamespace(from_email=smtp_email)

    smtp_module.SmtpService = SmtpService
    monkeypatch.setitem(sys.modules, 'src.services.smtp_service', smtp_module)

    class Provider:
        def get_npm_credentials(self):
            if npm_username is None:
                raise RuntimeError('no npm credentials')
            return SimpleNamespace(username=npm_username)

    monkeypatch.setattr(proxy_manager_module, 'IntegrationCredentialProvider', Provider)


def test_a_valid_smtp_sender_is_the_preferred_certificate_email(monkeypatch):
    _patch_email_sources(monkeypatch, smtp_email=' ops@example.com ')

    assert ProxyManager._resolve_default_letsencrypt_email(['app.example.com']) == 'ops@example.com'


def test_an_incomplete_smtp_sender_is_skipped(monkeypatch):
    _patch_email_sources(monkeypatch, smtp_email='ops@localhost')

    assert ProxyManager._resolve_default_letsencrypt_email(['app.example.com']) == 'admin@app.example.com'


def test_npm_credentials_are_used_when_smtp_is_missing(monkeypatch):
    _patch_email_sources(monkeypatch, npm_username='admin@example.com')

    assert ProxyManager._resolve_default_letsencrypt_email([]) == 'admin@example.com'


def test_the_npm_placeholder_account_is_ignored(monkeypatch):
    _patch_email_sources(monkeypatch, npm_username='admin@mydomain.com')

    assert ProxyManager._resolve_default_letsencrypt_email(['app.example.com']) == 'admin@app.example.com'


@pytest.mark.parametrize('domain', ['*.example.com', '192.0.2.10', ''])
def test_wildcards_and_ip_addresses_are_not_used_as_the_email_domain(monkeypatch, domain):
    _patch_email_sources(monkeypatch)

    assert ProxyManager._resolve_default_letsencrypt_email([domain]) == 'admin@websoft9.com'


def test_the_product_domain_is_the_last_resort(monkeypatch):
    _patch_email_sources(monkeypatch)

    assert ProxyManager._resolve_default_letsencrypt_email(None) == 'admin@websoft9.com'


# ── to_proxy_host_response ────────────────────────────────────────────────


def test_missing_proxy_host_maps_to_none():
    assert ProxyManager.to_proxy_host_response(None) is None


def test_certificate_name_falls_back_to_its_domains():
    response = ProxyManager.to_proxy_host_response(
        {
            'id': 4,
            'domain_names': ['app.example.com'],
            'certificate': {'id': 6, 'domain_names': ['app.example.com', 'www.example.com']},
        }
    )

    assert response == {
        'proxy_id': 4,
        'domain_names': ['app.example.com'],
        'certificate_id': 6,
        'certificate_name': 'app.example.com, www.example.com',
        'ssl_forced': False,
    }


def test_a_named_certificate_wins_over_its_domains():
    response = ProxyManager.to_proxy_host_response(
        {
            'proxy_id': 4,
            'domain_names': ['app.example.com'],
            'certificate': {'id': 6, 'nice_name': 'letsencrypt-app', 'domain_names': ['app.example.com']},
            'ssl_forced': 1,
        }
    )

    assert response['certificate_name'] == 'letsencrypt-app'
    assert response['ssl_forced'] is True
