"""`AppSftpAccountService`: orchestrating the privileged helper that provisions the host account.

The service is a thin but security-relevant shell around the helper container: it decides when the
account is usable, what credentials it hands to the console, and how a helper failure is classified
(a naming conflict is a 409 the operator has to resolve, an unusable account is a 409 retry, an
invalid helper response is a 500).
"""

import json
import os
import stat
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import app_sftp_account as account_module
from src.services.app_sftp_account import ACCOUNT_NAME, APP_ACCOUNT_PREFIX, STATE_VERSION, AppSftpAccountService


class FakeContainer:
    def __init__(self, status_code=0, stdout='{"version": 3}', stderr=''):
        self.status_code = status_code
        self.stdout = stdout
        self.stderr = stderr
        self.removed = []

    def wait(self, timeout=None):
        return {'StatusCode': self.status_code}

    def logs(self, stdout=True, stderr=False):
        return (self.stdout if stdout else self.stderr).encode()

    def remove(self, force=False):
        self.removed.append(force)


class FakeContainers:
    def __init__(self, container):
        self.container = container
        self.run_calls = []
        self.lookup = []

    def get(self, name):
        self.lookup.append(name)
        return SimpleNamespace(image=SimpleNamespace(id='sha256:image'))

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        if isinstance(self.container, Exception):
            raise self.container
        return self.container


class FakeDockerClient:
    def __init__(self, container):
        self.containers = FakeContainers(container)
        self.closed = 0

    def close(self):
        self.closed += 1


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('HOSTNAME', 'websoft9-dev')
    container = FakeContainer()
    client = FakeDockerClient(container)
    instance = AppSftpAccountService(data_dir=str(tmp_path), docker_client=client)
    instance.state = tmp_path
    instance.container = container
    instance.client = client
    return instance


def _write_ready_state(service, *, version=STATE_VERSION, username=f'{APP_ACCOUNT_PREFIX}sftp', port=None):
    payload = {'version': version, 'username': username, 'uid': 2001, 'sshd_mode': 'dropin'}
    if port is not None:
        payload['port'] = port
    service.state_file.write_text(json.dumps(payload))
    service.state_file.chmod(0o600)
    service.key_file.write_text('-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n')
    service.key_file.chmod(0o600)


# ── status ────────────────────────────────────────────────────────────────


def test_status_reports_a_missing_account(service):
    assert service.status() == {
        'state': 'missing',
        'account': ACCOUNT_NAME,
        'uid': None,
        'sshd_mode': None,
        'version': None,
        'key_present': False,
    }


def test_status_reports_a_ready_account(service):
    _write_ready_state(service)

    status = service.status()

    assert status['state'] == 'ready'
    assert status['account'] == f'{APP_ACCOUNT_PREFIX}sftp'
    assert status['uid'] == 2001
    assert status['sshd_mode'] == 'dropin'
    assert status['version'] == STATE_VERSION
    assert status['key_present'] is True


@pytest.mark.parametrize(
    ("version", "username"),
    [
        (STATE_VERSION - 1, f'{APP_ACCOUNT_PREFIX}sftp'),
        (STATE_VERSION, 'ubuntu'),
        (STATE_VERSION, 'root'),
    ],
)
def test_status_rejects_unsupported_or_foreign_state(service, version, username):
    _write_ready_state(service, version=version, username=username)

    assert service.status()['state'] == 'missing'


def test_status_requires_the_private_key(service):
    _write_ready_state(service)
    service.key_file.unlink()

    status = service.status()

    assert status['state'] == 'missing'
    assert status['key_present'] is False


def test_state_with_unsafe_permissions_is_ignored(service):
    _write_ready_state(service)
    service.state_file.chmod(0o644)

    # 组/其他用户可读的状态文件一律当作"未准备"
    assert service._read_state() == {}
    assert service.status()['state'] == 'missing'


def test_a_corrupted_state_file_is_ignored(service):
    service.state_file.write_text('not json')
    service.state_file.chmod(0o600)

    assert service._read_state() == {}


def test_a_state_file_that_is_not_an_object_is_ignored(service):
    service.state_file.write_text('[1, 2, 3]')
    service.state_file.chmod(0o600)

    assert service._read_state() == {}


# ── credentials ───────────────────────────────────────────────────────────


def test_credentials_require_a_prepared_account(service):
    with pytest.raises(CustomException) as error:
        service.credentials()

    assert error.value.status_code == 409
    assert error.value.message == 'SFTP Account Unavailable'


def test_credentials_return_a_key_based_profile(service, monkeypatch):
    _write_ready_state(service, port=2222)
    monkeypatch.setattr(account_module, 'HOST_ACCESS_HOST', '192.0.2.10')

    profile = service.credentials()

    assert profile['profile_id'] == 'platform-sftp'
    assert profile['username'] == f'{APP_ACCOUNT_PREFIX}sftp'
    assert profile['host'] == '192.0.2.10'
    assert profile['port'] == 2222
    assert profile['auth_method'] == 'key'
    assert profile['private_key'].startswith('-----BEGIN')
    assert profile['passphrase'] == ''
    assert profile['remember'] is True


def test_credentials_fall_back_to_the_default_port(service):
    _write_ready_state(service)

    assert service.credentials()['port'] == account_module.HOST_ACCESS_PORT


def test_a_world_readable_private_key_is_refused(service):
    _write_ready_state(service)
    service.key_file.chmod(0o644)

    with pytest.raises(CustomException) as error:
        service.credentials()

    assert error.value.status_code == 500
    assert 'unsafe permissions' in error.value.details


def test_a_key_owned_by_another_user_is_refused(service, monkeypatch):
    _write_ready_state(service)
    monkeypatch.setattr(
        account_module,
        'os',
        SimpleNamespace(geteuid=lambda: 4242, **{name: getattr(os, name) for name in dir(os) if name not in {'geteuid'}}),
    )

    with pytest.raises(CustomException) as error:
        service._read_private_key()

    assert 'unsafe permissions' in error.value.details


# ── ensure ────────────────────────────────────────────────────────────────


def test_ensure_is_idempotent_for_a_ready_account(service):
    _write_ready_state(service)

    status = service.ensure()

    assert status['state'] == 'ready'
    assert service.client.containers.run_calls == []


def test_ensure_can_force_a_rerun(service, monkeypatch):
    _write_ready_state(service)
    monkeypatch.setattr(service, '_verify', lambda: None)
    service.container.stdout = json.dumps({'version': STATE_VERSION, 'username': f'{APP_ACCOUNT_PREFIX}sftp'})

    status = service.ensure(force=True)

    assert status['state'] == 'ready'
    assert len(service.client.containers.run_calls) == 1


def test_ensure_rejects_an_unsupported_helper_state(service):
    service.container.stdout = json.dumps({'version': STATE_VERSION - 1})

    with pytest.raises(CustomException) as error:
        service.ensure()

    assert error.value.status_code == 500
    assert error.value.details == 'The host SFTP account state is not supported'


def test_ensure_verifies_the_prepared_account_can_log_in(service, monkeypatch):
    verified = []
    monkeypatch.setattr(service, '_verify', lambda: verified.append(True))
    service.container.stdout = json.dumps({'version': STATE_VERSION, 'username': f'{APP_ACCOUNT_PREFIX}sftp'})

    service.ensure()

    assert verified == [True]


def test_ensure_creates_the_state_directory_with_restrictive_mode(service):
    service.client.containers.list = None  # 不需要
    service.data_dir.rmdir()
    service.state_file = service.data_dir / 'app-sftp-account.json'
    service.key_file = service.data_dir / 'sftp.key'
    service.lock_file = service.data_dir / '.app-sftp.lock'
    service.container.stdout = json.dumps({'version': STATE_VERSION})
    service._verify = lambda: None

    service.ensure()

    assert service.data_dir.is_dir()
    assert stat.S_IMODE(service.data_dir.stat().st_mode) == 0o700


# ── helper execution ──────────────────────────────────────────────────────


def test_helper_runs_in_the_host_namespaces_as_root(service):
    service._run_helper('prepare')

    call = service.client.containers.run_calls[0]
    assert call['entrypoint'][:2] == ['nsenter', '--target']
    assert call['pid_mode'] == 'host'
    assert call['privileged'] is True
    assert call['user'] == '0'
    assert call['labels']['websoft9.operation'] == 'prepare-app-sftp'
    assert call['command'][1:3] == ['-c', Path(account_module.__file__).with_name('app_sftp_prepare.py').read_text()]
    assert call['command'][3] == 'prepare'


def test_helper_returns_the_last_json_line(service):
    service.container.stdout = 'preparing account\n{"version": 3, "username": "websoft9-sftp"}\n'

    assert service._run_helper('prepare') == {'version': 3, 'username': 'websoft9-sftp'}


@pytest.mark.parametrize(
    "message",
    [
        "the existing 'websoft9-sftp' account has a login shell; refusing to use it",
        "the existing 'websoft9-sftp' account has an unexpected home directory",
        "the existing 'websoft9-sftp' account belongs to privileged groups: docker",
        "SFTP account directory has an unexpected owner",
    ],
)
def test_a_foreign_account_is_reported_as_a_conflict(service, message):
    service.container.status_code = 1
    service.container.stderr = message

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.status_code == 409
    assert error.value.message == 'SFTP Account Conflict'
    assert 'not created by the platform' in error.value.details


def test_other_helper_failures_keep_the_helper_message(service):
    service.container.status_code = 1
    service.container.stderr = 'useradd: cannot create directory'

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.status_code == 409
    assert error.value.details == 'useradd: cannot create directory'


def test_helper_failures_fall_back_to_stdout_when_stderr_is_empty(service):
    service.container.status_code = 1
    service.container.stdout = 'boom on stdout'

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.details == 'boom on stdout'


def test_helper_failures_have_a_default_message(service):
    service.container.status_code = 1
    service.container.stdout = ''
    service.container.stderr = ''

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.details == 'Host SFTP account preparation failed'


@pytest.mark.parametrize('stdout', ['', 'prepare started', '{"truncated": '])
def test_an_unparsable_helper_response_is_a_server_error(service, stdout):
    service.container.stdout = stdout

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.status_code == 500
    assert error.value.details == 'The host SFTP helper returned an invalid response'


def test_a_non_object_helper_response_is_a_server_error(service):
    service.container.stdout = '[1, 2, 3]'

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.details == 'The host SFTP helper returned an invalid response'


def test_the_helper_container_is_always_removed_and_the_client_closed(service):
    service.container.status_code = 1
    service.container.stderr = 'failed'

    with pytest.raises(CustomException):
        service._run_helper('prepare')

    assert service.container.removed == [True]
    assert service.client.closed == 1


def test_an_unexpected_docker_error_is_reported_as_unavailable(service):
    service.client.containers.container = RuntimeError('docker socket is gone')

    with pytest.raises(CustomException) as error:
        service._run_helper('prepare')

    assert error.value.status_code == 409
    assert 'docker socket is gone' in error.value.details


def test_the_client_is_closed_even_when_the_container_never_started(service):
    service.client.containers.container = RuntimeError('no such image')

    with pytest.raises(CustomException):
        service._run_helper('prepare')

    assert service.client.closed == 1


# ── login verification ────────────────────────────────────────────────────


class FakeSftp:
    def __init__(self, error=None):
        self.error = error
        self.closed = 0

    def stat(self, path):
        if self.error:
            raise self.error
        return SimpleNamespace(st_mode=0o700)

    def close(self):
        self.closed += 1


class FakeSshClient:
    def __init__(self, sftp):
        self.sftp = sftp
        self.connect_kwargs = None
        self.closed = 0

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        self.connect_kwargs = kwargs

    def open_sftp(self):
        return self.sftp

    def close(self):
        self.closed += 1


def _install_paramiko(monkeypatch, client):
    module = types.ModuleType('paramiko')
    module.SSHClient = lambda: client
    module.AutoAddPolicy = lambda: 'auto-add'
    module.RSAKey = SimpleNamespace(from_private_key_file=lambda path: f'key:{path}')
    monkeypatch.setitem(sys.modules, 'paramiko', module)
    return module


def test_verify_logs_in_with_the_prepared_key(service, monkeypatch):
    _write_ready_state(service)
    sftp = FakeSftp()
    client = FakeSshClient(sftp)
    _install_paramiko(monkeypatch, client)

    service._verify()

    assert client.connect_kwargs['username'] == f'{APP_ACCOUNT_PREFIX}sftp'
    assert client.connect_kwargs['pkey'] == f'key:{service.key_file}'
    assert client.connect_kwargs['look_for_keys'] is False
    assert client.connect_kwargs['allow_agent'] is False
    assert client.policy == 'auto-add'
    assert sftp.closed == 1
    assert client.closed == 1


def test_verify_reports_an_unusable_account(service, monkeypatch):
    _write_ready_state(service)
    client = FakeSshClient(FakeSftp(error=PermissionError('auth failed')))
    _install_paramiko(monkeypatch, client)

    with pytest.raises(CustomException) as error:
        service._verify()

    assert error.value.status_code == 500
    assert 'cannot log in' in error.value.details
    assert client.closed == 1


def test_verify_closes_the_sftp_channel_when_stat_fails(service, monkeypatch):
    _write_ready_state(service)
    sftp = FakeSftp(error=OSError('permission denied'))
    client = FakeSshClient(sftp)
    _install_paramiko(monkeypatch, client)

    with pytest.raises(CustomException):
        service._verify()

    assert sftp.closed == 1


# ── client plumbing and locking ───────────────────────────────────────────


def test_the_client_factory_takes_precedence(tmp_path):
    client = FakeDockerClient(FakeContainer())
    service = AppSftpAccountService(
        data_dir=str(tmp_path),
        docker_client=None,
        docker_client_factory=lambda: client,
    )

    assert service._client() is client


def test_an_injected_client_is_reused(tmp_path):
    client = FakeDockerClient(FakeContainer())
    service = AppSftpAccountService(data_dir=str(tmp_path), docker_client=client)

    assert service._client() is client
    assert service._client() is client


def test_the_client_defaults_to_the_local_docker_daemon(tmp_path, monkeypatch):
    client = FakeDockerClient(FakeContainer())
    monkeypatch.setattr(account_module.docker, 'from_env', lambda: client)
    service = AppSftpAccountService(data_dir=str(tmp_path))

    assert service._client() is client


def test_the_lock_file_is_private(service):
    with service._file_lock():
        attributes = service.lock_file.stat()

    assert stat.S_IMODE(attributes.st_mode) == 0o600
    # flock 已经释放,可以再次加锁
    with service._file_lock():
        pass


def test_revoke_runs_the_helper_and_returns_the_new_status(tmp_path, monkeypatch):
    service = AppSftpAccountService(data_dir=str(tmp_path), docker_client=FakeDockerClient(FakeContainer()))
    called = []
    monkeypatch.setattr(service, '_run_helper', lambda operation: called.append(operation) or {'version': 3})

    result = service.revoke()

    assert called == ['revoke']
    assert result['state'] == 'missing'
