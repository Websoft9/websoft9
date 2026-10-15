import stat
import sqlite3
import json
import os
import pwd
import shlex
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "paramiko" not in sys.modules:
    sys.modules["paramiko"] = SimpleNamespace(
        SSHClient=object,
        SFTPClient=object,
        PKey=object,
        Transport=object,
        AutoAddPolicy=object,
        AuthenticationException=Exception,
        RSAKey=object,
        Ed25519Key=object,
        ECDSAKey=object,
        DSSKey=object,
    )

from src.core.exception import CustomException
from src.services.host_access import HostAccessService
from src.services.app_sftp import AppSftpService, ScopedHostAccess, ScopedSftp


@pytest.fixture
def automatic_local_host(tmp_path, monkeypatch):
    service = HostAccessService(data_dir=str(tmp_path / 'profiles'), auth_service=FakeAuthService())
    monkeypatch.setattr(service, '_runtime_profiles', {})
    monkeypatch.setattr(service, '_verify_profile', lambda profile: dict(profile, working_directory='/'))
    return service


def test_automatic_local_host_requires_authentication(automatic_local_host):
    service = automatic_local_host
    with pytest.raises(CustomException) as error:
        service.create_local_profile(None)
    assert error.value.status_code == 401
    assert not service.database_file.exists()


@pytest.mark.parametrize('username', ['root', 'ubuntu', 'ec2-user', 'azureuser'])
def test_automatic_local_host_reuses_an_existing_connection(automatic_local_host, username):
    service = automatic_local_host
    first = service.save_profile('valid-session', {'username': username, 'auth_method': 'key', 'private_key': 'TEST-PRIVATE-KEY'})
    service._runtime_profiles.clear()
    response = service.create_local_profile('valid-session')
    profile = service.get_connection_profile('valid-session', response['active_profile_id'])
    assert response['configured'] is True
    assert response['active_profile_id'] == first['active_profile_id']
    assert len(response['saved_profiles']) == 1
    assert profile['username'] == username
    assert profile['auth_method'] == 'key'
    assert profile['private_key'] == 'TEST-PRIVATE-KEY'
    assert 'TEST-PRIVATE-KEY' not in str(response)


def test_automatic_local_host_reuses_runtime_credentials(automatic_local_host):
    service = automatic_local_host
    first = service.save_profile('valid-session', {'username': 'ubuntu', 'auth_method': 'password', 'password': 'temporary-secret', 'remember': False})
    response = service.create_local_profile('valid-session')
    profile = service.get_connection_profile('valid-session', response['active_profile_id'])
    assert response['active_profile_id'] == first['active_profile_id']
    assert profile['password'] == 'temporary-secret'
    assert service._load_saved_profile('operator-1', response['active_profile_id'])['password'] == ''
    assert 'temporary-secret' not in str(response)


def test_automatic_local_host_reports_missing_authorization(automatic_local_host):
    service = automatic_local_host
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert error.value.status_code == 400
    assert error.value.message == 'Local SSH Setup Unavailable'
    assert 'Privileged mode alone' in error.value.details
    assert 'Terminal' in error.value.details
    assert 'non-root' in error.value.details
    assert service.get_profile('valid-session')['saved_profiles'] == []


def prepare_local_credentials(service, username='ubuntu'):
    service.data_dir.mkdir(parents=True, exist_ok=True)
    service.data_dir.chmod(0o700)
    metadata = service.data_dir / 'local-ssh.json'
    metadata.write_text('{"username": "' + username + '"}')
    metadata.chmod(0o600)
    private_key = service.data_dir / 'local-ssh.key'
    private_key.write_text('TEST-PRIVATE-KEY')
    private_key.chmod(0o600)
    return metadata, private_key


@pytest.mark.parametrize('username', ['root', 'ubuntu', 'ec2-user', 'azureuser'])
def test_automatic_local_host_creates_first_connection(automatic_local_host, username):
    service = automatic_local_host
    prepare_local_credentials(service, username)
    response = service.create_local_profile('valid-session')
    profile = service.get_connection_profile('valid-session')
    assert response['configured'] is True
    assert profile['username'] == username
    assert profile['private_key'] == 'TEST-PRIVATE-KEY'
    assert profile['remember'] is True
    assert 'TEST-PRIVATE-KEY' not in str(response)
    assert stat.S_IMODE(service.database_file.stat().st_mode) == 0o600
    assert service.create_local_profile('valid-session')['active_profile_id'] == response['active_profile_id']
    assert len(response['saved_profiles']) == 1


def test_deleting_local_connection_ends_sessions_and_blocks_automatic_recreation(automatic_local_host, monkeypatch):
    service = automatic_local_host
    prepare_local_credentials(service)
    connection = service.create_local_profile('valid-session')
    revoked = []
    monkeypatch.setattr(service, '_revoke_local_ssh_credentials', lambda profile: revoked.append(profile['profile_id']))
    channel_closed = []
    client_closed = []
    monkeypatch.setattr(service, '_terminal_sessions', {
        'terminal-session': {
            'operator_id': 'operator-1',
            'profile': {'profile_id': connection['active_profile_id']},
            'channel': SimpleNamespace(close=lambda: channel_closed.append(True)),
            'client': SimpleNamespace(close=lambda: client_closed.append(True)),
            'resources_closed': False,
        },
    })

    service.delete_saved_profile('valid-session', connection['active_profile_id'])

    assert revoked == [connection['active_profile_id']]
    assert 'terminal-session' not in service._terminal_sessions
    assert channel_closed == [True]
    assert client_closed == [True]
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert error.value.message == 'Local SSH Setup Revoked'

    replacement = service.save_profile('valid-session', {
        'profile_id': 'manual-local', 'host': '127.0.0.1', 'username': 'ubuntu',
        'auth_method': 'key', 'private_key': 'MANUAL-PRIVATE-KEY',
    })
    assert service.create_local_profile('valid-session')['active_profile_id'] == replacement['active_profile_id']


def test_confirmed_automatic_connection_recreates_deleted_manual_profile(automatic_local_host, monkeypatch):
    from src.api.v1.routers import host_access

    service = automatic_local_host
    prepare_local_credentials(service)
    previous = service.save_profile('valid-session', {'profile_id': 'manual-local', 'username': 'ubuntu', 'auth_method': 'key', 'private_key': 'MANUAL-KEY'})
    service.delete_saved_profile('valid-session', previous['active_profile_id'])
    assert service._is_local_setup_revoked('operator-1')
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert error.value.message == 'Local SSH Setup Revoked'

    monkeypatch.setattr(host_access, '_host_access_service', service)
    response = host_access.create_local_host_access_profile(session_token='valid-session')
    assert response['configured']
    assert response['active_profile_id'] != previous['active_profile_id']
    assert response['active_profile_id'].startswith('auto-local-')
    assert not service._is_local_setup_revoked('operator-1')
    assert 'TEST-PRIVATE-KEY' not in str(response)


def test_confirmed_automatic_connection_requires_valid_reprepared_credentials(automatic_local_host, monkeypatch):
    service = automatic_local_host
    credentials = prepare_local_credentials(service)
    previous = service.create_local_profile('valid-session')
    monkeypatch.setattr(service, '_revoke_local_ssh_credentials', lambda profile: [path.unlink() for path in credentials])
    service.delete_saved_profile('valid-session', previous['active_profile_id'])
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session', allow_recreate=True)
    assert error.value.message == 'Local SSH Setup Unavailable'
    assert service._is_local_setup_revoked('operator-1')
    assert service.get_profile('valid-session')['saved_profiles'] == []

    prepare_local_credentials(service)
    verify = service._verify_profile
    def reject(profile):
        raise CustomException(400, 'SSH Authentication Failed', 'Rejected key')
    monkeypatch.setattr(service, '_verify_profile', reject)
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session', allow_recreate=True)
    assert error.value.message == 'SSH Authentication Failed'
    assert service._is_local_setup_revoked('operator-1')
    assert service.get_profile('valid-session')['saved_profiles'] == []

    monkeypatch.setattr(service, '_verify_profile', verify)
    response = service.create_local_profile('valid-session', allow_recreate=True)
    assert response['configured']
    assert response['active_profile_id'] != previous['active_profile_id']
    assert not service._is_local_setup_revoked('operator-1')


@pytest.mark.parametrize('exit_code', [0, 1])
def test_explicit_automatic_connection_prepares_missing_authorization(tmp_path, monkeypatch, exit_code):
    import docker

    data_root = tmp_path / 'data'
    monkeypatch.setenv('WEBSOFT9_DATA_ROOT', str(data_root))
    monkeypatch.setenv('HOSTNAME', 'product-container')
    service = HostAccessService(data_dir=str(data_root / 'config/host-access'), auth_service=FakeAuthService())
    monkeypatch.setattr(service, '_runtime_profiles', {})
    monkeypatch.setattr(service, '_verify_profile', lambda profile: dict(profile, working_directory='/'))
    service._ensure_storage()
    calls = []
    removed = []
    closed = []
    container = SimpleNamespace(wait=lambda **kwargs: {'StatusCode': exit_code}, remove=lambda **kwargs: removed.append(kwargs))
    def run(**kwargs):
        calls.append(kwargs)
        if exit_code == 0:
            prepare_local_credentials(service)
        return container
    client = SimpleNamespace(containers=SimpleNamespace(get=lambda identifier: SimpleNamespace(image=SimpleNamespace(id='installed-image')), run=run), close=lambda: closed.append(True))
    monkeypatch.setattr(docker, 'from_env', lambda: client)
    if exit_code:
        with pytest.raises(CustomException) as error:
            service.create_local_profile('valid-session', allow_recreate=True)
        assert error.value.message == 'Local SSH Setup Unavailable'
        assert service.get_profile('valid-session')['saved_profiles'] == []
    else:
        assert service.create_local_profile('valid-session', allow_recreate=True)['configured']
    assert calls[0]['image'] == 'installed-image'
    assert calls[0]['privileged'] is True
    assert calls[0]['pid_mode'] == 'host'
    assert calls[0]['entrypoint'][0] == 'nsenter'
    assert calls[0]['command'][0:2] == ['python3', '-c']
    assert 'def prepare(data_root, requested):' in calls[0]['command'][2]
    assert calls[0]['command'][3:] == [str(data_root), '']
    assert removed == [{'force': True}]
    assert closed == [True]


@pytest.mark.parametrize('defect', [None, 'symlink', 'hardlink'])
def test_deleting_automatic_connection_revokes_only_its_key(automatic_local_host, tmp_path, monkeypatch, defect):
    service = automatic_local_host
    metadata, private_key = prepare_local_credentials(service, pwd.getpwuid(os.getuid()).pw_name)
    authorization = tmp_path / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    retained = b'# ssh-rsa AUTOMATIC-KEY\nssh-ed25519 OTHER-KEY comment ssh-rsa AUTOMATIC-KEY\n'
    authorization.write_bytes(retained + b'ssh-rsa AUTOMATIC-KEY platform\ncommand="echo test",no-pty ssh-rsa AUTOMATIC-KEY platform\n')
    original = authorization.read_bytes()
    metadata.write_text(json.dumps({'username': pwd.getpwuid(os.getuid()).pw_name, 'authorization_path': str(authorization)}))
    if defect == 'symlink':
        target = tmp_path / 'original-authorization'
        authorization.rename(target)
        authorization.symlink_to(target)
    elif defect == 'hardlink':
        os.link(authorization, tmp_path / 'linked-authorization')
    key = SimpleNamespace(get_name=lambda: 'ssh-rsa', get_base64=lambda: 'AUTOMATIC-KEY')
    monkeypatch.setattr(service, '_parse_private_key', lambda *args: key)
    closed = []
    monkeypatch.setattr(service, '_connect_client', lambda profile: SimpleNamespace(close=lambda: closed.append(True)))

    def run_command(client, command, title, prefix):
        result = subprocess.run(shlex.split(command), capture_output=True, text=True)
        if result.returncode:
            raise CustomException(400, title, prefix)

    monkeypatch.setattr(service, '_run_remote_command', run_command)
    connection = service.create_local_profile('valid-session')
    if defect:
        with pytest.raises(CustomException) as error:
            service.delete_saved_profile('valid-session', connection['active_profile_id'])
        assert error.value.message == 'Local SSH Key Cleanup Failed'
        assert authorization.read_bytes() == original
        assert metadata.exists() and private_key.exists()
        assert service.get_profile('valid-session')['configured'] is True
    else:
        service.delete_saved_profile('valid-session', connection['active_profile_id'])
        assert authorization.read_bytes() == retained
        assert not metadata.exists() and not private_key.exists()
        assert service.get_profile('valid-session')['saved_profiles'] == []
    assert closed == [True]


@pytest.mark.parametrize('defect', ['permissions', 'symlink', 'hardlink', 'invalid-json', 'missing-key', 'directory-permissions'])
def test_automatic_local_host_rejects_unsafe_prepared_credentials(automatic_local_host, tmp_path, defect):
    service = automatic_local_host
    metadata, private_key = prepare_local_credentials(service)
    if defect == 'permissions':
        private_key.chmod(0o644)
    elif defect == 'symlink':
        private_key.unlink()
        private_key.symlink_to(tmp_path / 'unrelated')
    elif defect == 'hardlink':
        os.link(private_key, tmp_path / 'unrelated')
    elif defect == 'invalid-json':
        metadata.write_text('invalid')
    elif defect == 'missing-key':
        private_key.unlink()
    else:
        service.data_dir.chmod(0o755)
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert 'unreadable or unsafe' in error.value.details
    assert service.get_profile('valid-session')['saved_profiles'] == []


def test_automatic_local_host_does_not_save_unverified_prepared_credentials(automatic_local_host, monkeypatch):
    service = automatic_local_host
    prepare_local_credentials(service)

    def reject(profile):
        raise CustomException(400, 'SSH Authentication Failed', 'The host rejected the prepared key')

    monkeypatch.setattr(service, '_verify_profile', reject)
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert error.value.message == 'SSH Authentication Failed'
    assert service.get_profile('valid-session')['saved_profiles'] == []


@pytest.mark.parametrize('message,details', [
    ('SSH Authentication Failed', 'Authentication rejected; root login disabled'),
    ('SSH Connection Failed', 'Connection refused'),
    ('Permission Denied', 'Application volume is not accessible'),
])
def test_automatic_local_host_preserves_failure_and_manual_profile(automatic_local_host, monkeypatch, message, details):
    service = automatic_local_host
    saved = service.save_profile('valid-session', {'username': 'ubuntu', 'auth_method': 'password', 'password': 'manual-secret'})
    original = service.database_file.read_bytes()

    def reject(profile):
        raise CustomException(400, message, details)

    monkeypatch.setattr(service, '_verify_profile', reject)
    with pytest.raises(CustomException) as error:
        service.create_local_profile('valid-session')
    assert error.value.message == message
    assert details in error.value.details
    assert 'Terminal' in error.value.details
    assert service.get_profile('valid-session')['active_profile_id'] == saved['active_profile_id']
    assert service.database_file.read_bytes() == original


def test_automatic_local_host_skips_remote_profiles(automatic_local_host, monkeypatch):
    service = automatic_local_host
    saved = service.save_profile('valid-session', {'host': 'remote.example.com', 'username': 'ubuntu', 'auth_method': 'password', 'password': 'manual-secret'})
    monkeypatch.setattr(service, '_verify_profile', lambda profile: pytest.fail('Remote profiles must not be verified'))
    with pytest.raises(CustomException):
        service.create_local_profile('valid-session')
    assert service.get_profile('valid-session')['active_profile_id'] == saved['active_profile_id']


def test_automatic_local_host_tries_another_local_account(automatic_local_host, monkeypatch):
    service = automatic_local_host
    usable = service.save_profile('valid-session', {'username': 'ubuntu', 'auth_method': 'password', 'password': 'valid-secret'})
    service.save_profile('valid-session', {'username': 'root', 'auth_method': 'password', 'password': 'invalid-secret'})

    def verify(profile):
        if profile['username'] == 'root':
            raise CustomException(400, 'SSH Authentication Failed', 'Root login disabled')
        return dict(profile, working_directory='/home/ubuntu')

    monkeypatch.setattr(service, '_verify_profile', verify)
    response = service.create_local_profile('valid-session')
    assert response['active_profile_id'] == usable['active_profile_id']
    assert service.get_connection_profile('valid-session')['working_directory'] == '/home/ubuntu'


@pytest.fixture
def host_ssh_preparer(tmp_path, monkeypatch):
    if os.getuid() != 0 or not shutil.which('ssh-keygen'):
        pytest.skip('Host authorization preparation requires root and ssh-keygen')
    source = (PROJECT_ROOT / 'src/services/host_access_prepare.py').read_text()
    namespace = {'__name__': 'websoft9_host_ssh_test'}
    exec(compile(source, 'host_access_prepare.py', 'exec'), namespace)
    home = tmp_path / 'host-home'
    home.mkdir(mode=0o700)
    account = SimpleNamespace(pw_name='root', pw_uid=0, pw_gid=0, pw_dir=str(home), pw_shell='/bin/bash')
    monkeypatch.setattr(namespace['pwd'], 'getpwnam', lambda username: SimpleNamespace(**{**vars(account), 'pw_name': username}))
    monkeypatch.setattr(namespace['pwd'], 'getpwall', lambda: [])
    monkeypatch.delenv('SUDO_USER', raising=False)
    monkeypatch.delenv('WEBSOFT9_HOST_ACCESS_PORT', raising=False)
    return namespace, home


@pytest.mark.parametrize('username', ['root', 'ubuntu', 'ec2-user', 'azureuser'])
def test_host_ssh_preparation_preserves_keys_and_is_idempotent(host_ssh_preparer, tmp_path, monkeypatch, username):
    preparation, home = host_ssh_preparer
    original_run = subprocess.run

    def run(command, **kwargs):
        if command[0].endswith('sshd'):
            return SimpleNamespace(stdout='pubkeyauthentication yes\npermitrootlogin prohibit-password\nauthorizedkeysfile .ssh/authorized_keys\nport 22\n')
        if command[0] == 'ssh':
            return SimpleNamespace(returncode=0)
        return original_run(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.write_bytes(b'existing-key-without-newline')
    preparation['prepare'](str(tmp_path / 'data'), username)
    original = authorization.read_bytes()
    credentials = tmp_path / 'data/config/host-access'
    assert original.startswith(b'existing-key-without-newline\nssh-rsa ')
    assert json.loads((credentials / 'local-ssh.json').read_text())['username'] == username
    assert stat.S_IMODE((credentials / 'local-ssh.key').stat().st_mode) == 0o600
    assert stat.S_IMODE((credentials / 'local-ssh.json').stat().st_mode) == 0o600
    assert stat.S_IMODE(credentials.stat().st_mode) == 0o700
    preparation['prepare'](str(tmp_path / 'data'), username)
    assert authorization.read_bytes() == original
    restricted = b'command="true" ' + original.splitlines(keepends=True)[-1]
    authorization.write_bytes(restricted)
    preparation['prepare'](str(tmp_path / 'data'), username)
    assert authorization.read_bytes() == restricted


def test_host_ssh_preparation_rolls_back_failed_login(host_ssh_preparer, tmp_path, monkeypatch):
    preparation, home = host_ssh_preparer
    monkeypatch.setitem(preparation, 'ssh_policy', lambda username: {'authorizedkeysfile': '.ssh/authorized_keys', 'port': '22'})
    original_run = subprocess.run

    def run(command, **kwargs):
        if command[0] == 'ssh':
            raise subprocess.CalledProcessError(255, command, stderr=b'Permission denied')
        return original_run(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.write_bytes(b'existing-key')
    with pytest.raises(subprocess.CalledProcessError):
        preparation['prepare'](str(tmp_path / 'data'), 'ubuntu')
    assert authorization.read_bytes() == b'existing-key'
    assert not (tmp_path / 'data/config/host-access/local-ssh.json').exists()


def test_host_ssh_preparation_respects_disabled_root_login(host_ssh_preparer, tmp_path, monkeypatch):
    preparation, home = host_ssh_preparer
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='pubkeyauthentication yes\npermitrootlogin no\n'))
    with pytest.raises(ValueError, match='non-root'):
        preparation['prepare'](str(tmp_path / 'data'), 'root')
    assert not (home / '.ssh/authorized_keys').exists()


@pytest.mark.parametrize('sudo_user', ['', 'azureuser'])
def test_host_ssh_preparation_detects_a_non_root_account(host_ssh_preparer, tmp_path, monkeypatch, sudo_user):
    preparation, home = host_ssh_preparer
    os.chown(home, 1000, 1000)
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.write_text('existing-cloud-key')
    account = SimpleNamespace(pw_name='azureuser', pw_uid=1000, pw_gid=1000, pw_dir=str(home), pw_shell='/bin/bash')
    monkeypatch.setattr(preparation['pwd'], 'getpwnam', lambda username: account)
    monkeypatch.setattr(preparation['pwd'], 'getpwall', lambda: [account])
    monkeypatch.setenv('SUDO_USER', sudo_user)
    selected = preparation['choose_account']('', tmp_path / 'missing-metadata')
    assert selected.pw_name == 'azureuser'
    assert selected.pw_uid == 1000


def test_host_ssh_preparation_does_not_guess_between_accounts(host_ssh_preparer, tmp_path, monkeypatch):
    preparation, home = host_ssh_preparer
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.write_text('existing-cloud-key')
    accounts = [SimpleNamespace(pw_name=username, pw_uid=1000 + index, pw_dir=str(home), pw_shell='/bin/bash') for index, username in enumerate(['ubuntu', 'azureuser'])]
    monkeypatch.setattr(preparation['pwd'], 'getpwall', lambda: accounts)
    with pytest.raises(ValueError, match='manual connection'):
        preparation['choose_account']('', tmp_path / 'missing-metadata')


def test_host_ssh_preparation_rejects_linked_authorization(host_ssh_preparer, tmp_path, monkeypatch):
    preparation, home = host_ssh_preparer
    monkeypatch.setitem(preparation, 'ssh_policy', lambda username: {'authorizedkeysfile': '.ssh/authorized_keys', 'port': '22'})
    target = tmp_path / 'unrelated'
    target.write_text('untouched')
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.symlink_to(target)
    with pytest.raises(OSError):
        preparation['prepare'](str(tmp_path / 'data'), 'ubuntu')
    assert target.read_text() == 'untouched'


@pytest.mark.parametrize('path', ['/etc/passwd', '/app/data/../../etc', '/app/data-other/file', 'relative'])
def test_app_sftp_rejects_paths_outside_volume(path):
    guarded = ScopedSftp(SimpleNamespace(), '/app/data')
    with pytest.raises(CustomException) as error:
        guarded.checked(path)
    assert error.value.status_code == 403


def test_app_sftp_rejects_symlinks_and_root_mutations():
    def lstat(path):
        return SimpleNamespace(st_mode=stat.S_IFLNK if path.endswith('/link') else stat.S_IFDIR)

    guarded = ScopedSftp(SimpleNamespace(lstat=lstat), '/app/data')
    with pytest.raises(CustomException):
        guarded.checked('/app/data/link/file')
    with pytest.raises(CustomException):
        guarded.checked('/app/data', mutate=True)
    assert guarded.checked('/app/data/file') == '/app/data/file'


def test_app_sftp_normalizes_current_directory_without_escaping():
    remote = SimpleNamespace(lstat=lambda path: SimpleNamespace(st_mode=stat.S_IFDIR), normalize=lambda path: '/app/data')
    assert ScopedSftp(remote, '/app/data').normalize('.') == '/app/data'
    remote.normalize = lambda path: '/etc'
    with pytest.raises(CustomException):
        ScopedSftp(remote, '/app/data').normalize('.')


def test_app_sftp_sessions_reject_other_operators_and_expiry():
    host = SimpleNamespace(auth_service=FakeAuthService())
    service = AppSftpService(host)
    service.sessions['other'] = {'operator_id': 'operator-2', 'expires_at': float('inf')}
    service.sessions['expired'] = {'operator_id': 'operator-1', 'expires_at': 0}
    for identifier in ['other', 'expired', 'missing']:
        with pytest.raises(CustomException) as error:
            service.access('valid-session', identifier)
        assert error.value.status_code == 403


class FakeAuthService:
    def _require_authenticated_operator(self, session_token: Optional[str]):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")
        return {"id": "operator-1"}


class LocalTestSftp:
    def __init__(self, root):
        self.cwd = str(root)

    def lstat(self, path):
        return Path(path).lstat()

    def stat(self, path):
        return Path(path).stat()

    def normalize(self, path):
        return str(Path(self.cwd if path == '.' else path).resolve())

    def chdir(self, path):
        self.cwd = path

    def listdir_attr(self, path):
        result = []
        for child in Path(path).iterdir():
            entry = child.lstat()
            result.append(SimpleNamespace(filename=child.name, st_mode=entry.st_mode, st_uid=entry.st_uid, st_gid=entry.st_gid, st_size=entry.st_size))
        return result

    def open(self, path, mode='r', *args, **kwargs):
        return open(path, 'xb' if mode == 'wx' else mode, *args, **kwargs)

    def mkdir(self, path):
        Path(path).mkdir()

    def remove(self, path):
        Path(path).unlink()

    def rmdir(self, path):
        Path(path).rmdir()

    def rename(self, source, target):
        Path(source).rename(target)

    def putfo(self, handle, path):
        Path(path).write_bytes(handle.read())

    def chmod(self, path, mode):
        Path(path).chmod(mode)


@pytest.fixture
def scoped_files(tmp_path):
    root = tmp_path / 'application'
    root.mkdir()
    remote = LocalTestSftp(root)
    host = HostAccessService(data_dir=str(tmp_path), auth_service=FakeAuthService())

    @contextmanager
    def open_sftp(profile):
        yield remote

    host._open_sftp = open_sftp
    return ScopedHostAccess(host, {}, str(root)), root


def test_app_sftp_resolves_identity_names_without_exposing_account_files(scoped_files, monkeypatch):
    service, _ = scoped_files
    sources = {
        '/etc/passwd': b'root:x:0:0:root:/root:/bin/sh\nappuser:x:1000:1000::/home/appuser:/bin/sh\n',
        '/etc/group': b'root:x:0:\nappgroup:x:1000:\n',
    }
    reads = []

    @contextmanager
    def open_identity_source(path, mode='r'):
        reads.append((path, mode))
        yield SimpleNamespace(read=lambda: sources[path])

    with service._open_sftp({}) as guarded:
        monkeypatch.setattr(guarded.sftp, 'open', open_identity_source)
        owners, groups = service._load_identity_labels(guarded, [0, 1000, 4242], [0, 1000, 4242])
        assert owners == {0: 'root', 1000: 'appuser', 4242: '4242'}
        assert groups == {0: 'root', 1000: 'appgroup', 4242: '4242'}
        assert service._resolve_identity_label(0, owners) == 'root(0)'
        assert service._resolve_identity_label(1000, groups) == 'appgroup(1000)'
        assert reads == [('/etc/passwd', 'r'), ('/etc/group', 'r')]
        for path in sources:
            with pytest.raises(CustomException) as failure:
                guarded.open(path)
            assert failure.value.status_code == 403


def test_app_sftp_keeps_numeric_identity_when_names_are_unavailable(scoped_files, monkeypatch):
    service, _ = scoped_files

    def deny_identity_source(*args, **kwargs):
        raise PermissionError('Identity source unavailable')

    with service._open_sftp({}) as guarded:
        monkeypatch.setattr(guarded.sftp, 'open', deny_identity_source)
        owners, groups = service._load_identity_labels(guarded, [0, 1000], [0, 1000])
        assert service._resolve_identity_label(0, owners) == '0'
        assert service._resolve_identity_label(1000, groups) == '1000'


def test_app_sftp_file_operations_stay_in_directory(scoped_files):
    service, root = scoped_files
    service.create_directory('valid-session', str(root), 'docs')
    service.create_empty_file('valid-session', str(root / 'docs'), 'notes.txt')
    service.write_text_file('valid-session', str(root / 'docs/notes.txt'), 'hello')
    assert service.read_text_file('valid-session', str(root / 'docs/notes.txt'))['content'] == 'hello'
    service.create_directory('valid-session', str(root), 'backup')
    service.copy_item('valid-session', str(root / 'docs'), str(root / 'backup'))
    assert (root / 'backup/docs/notes.txt').read_text() == 'hello'
    service.rename_item('valid-session', str(root / 'docs/notes.txt'), 'renamed.txt')
    service.move_item('valid-session', str(root / 'docs/renamed.txt'), str(root))
    service.upload_file('valid-session', str(root), 'upload.bin', b'content')
    assert service.download_file('valid-session', str(root / 'upload.bin'))['content'] == b'content'
    assert service.list_directory('valid-session', str(root))['current_path'] == str(root)
    service.delete_item('valid-session', str(root / 'backup'))
    assert not (root / 'backup').exists()


@pytest.mark.parametrize('operation', ['read', 'write', 'upload', 'copy', 'move', 'delete', 'rename', 'chmod'])
def test_app_sftp_all_operations_reject_escape(scoped_files, operation):
    service, root = scoped_files
    (root / 'notes.txt').write_text('safe')
    outside = str(root.parent / 'outside.txt')
    calls = {
        'read': lambda: service.read_text_file('valid-session', outside),
        'write': lambda: service.write_text_file('valid-session', outside, 'unsafe'),
        'upload': lambda: service.upload_file('valid-session', str(root.parent), 'outside.txt', b'unsafe'),
        'copy': lambda: service.copy_item('valid-session', str(root / 'notes.txt'), str(root.parent)),
        'move': lambda: service.move_item('valid-session', str(root / 'notes.txt'), str(root.parent)),
        'delete': lambda: service.delete_item('valid-session', outside),
        'rename': lambda: service.rename_item('valid-session', outside, 'changed'),
        'chmod': lambda: service.update_item_attributes('valid-session', {'source_path': outside}),
    }
    with pytest.raises(CustomException) as error:
        calls[operation]()
    assert error.value.status_code == 403
    assert (root / 'notes.txt').read_text() == 'safe'


def test_app_sftp_symlink_and_root_operations_are_blocked(scoped_files):
    service, root = scoped_files
    (root / 'escape').symlink_to(root.parent, target_is_directory=True)
    assert service.list_directory('valid-session', str(root))['items'] == []
    for path in [str(root), str(root / 'escape')]:
        with pytest.raises(CustomException):
            service.delete_item('valid-session', path)
    with pytest.raises(CustomException):
        service.read_text_file('valid-session', str(root / 'escape/outside.txt'))


def test_app_sftp_volume_ownership_and_connection_binding(scoped_files):
    scoped, root = scoped_files
    host = scoped.host_service
    profile = {'profile_id': 'local', 'host': '127.0.0.1', 'port': 22, 'username': 'operator'}
    profile_available = True

    def get_profile(token, profile_id=None):
        if not profile_available:
            raise CustomException(400, 'Host Access Profile Not Found', 'The requested host profile is unavailable for file operations')
        return profile

    host.get_connection_profile = get_profile
    volume = {'Driver': 'local', 'Options': {}, 'Mountpoint': str(root), 'Labels': {'com.docker.compose.project': 'example'}}
    client = SimpleNamespace(volumes=SimpleNamespace(get=lambda identifier: SimpleNamespace(attrs=volume)))
    service = AppSftpService(host, docker_client_factory=lambda: client)
    with pytest.raises(CustomException):
        service.create('valid-session', 'other-app', 'data', 'local')
    session = service.create('valid-session', 'example', 'data', 'local')
    assert service.access('valid-session', session['session_id']).root == str(root)
    profile_available = False
    with pytest.raises(CustomException, match='unavailable for file operations'):
        service.access('valid-session', session['session_id'])
    profile_available = True
    profile['username'] = 'another-account'
    with pytest.raises(CustomException):
        service.access('valid-session', session['session_id'])
    profile['host'] = 'remote.example'
    with pytest.raises(CustomException):
        service.create('valid-session', 'example', 'data', 'local')


def test_app_sftp_invalidate_profile_only_removes_matching_sessions():
    service = AppSftpService(None)
    service.sessions = {
        'same-profile': {'operator_id': 'operator-a', 'profile_id': 'profile-a'},
        'other-operator': {'operator_id': 'operator-b', 'profile_id': 'profile-a'},
        'other-profile': {'operator_id': 'operator-a', 'profile_id': 'profile-b'},
    }
    service.invalidate_profile('operator-a', 'profile-a')
    assert set(service.sessions) == {'other-operator', 'other-profile'}


def test_app_sftp_http_endpoints_enforce_scope(scoped_files, monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from src.api.v1.routers import host_access
    from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME

    scoped, root = scoped_files
    host = scoped.host_service
    profile = {'profile_id': 'local', 'host': '127.0.0.1', 'port': 22, 'username': 'operator'}
    host.get_connection_profile = lambda token, profile_id=None: profile
    volume = {'Driver': 'local', 'Options': {}, 'Mountpoint': str(root), 'Labels': {'com.docker.compose.project': 'example'}}
    docker_client = SimpleNamespace(volumes=SimpleNamespace(get=lambda identifier: SimpleNamespace(attrs=volume)))
    service = AppSftpService(host, docker_client_factory=lambda: docker_client)
    monkeypatch.setattr(host_access, '_app_sftp_service', service)
    app = FastAPI()
    app.include_router(host_access.router)

    @app.exception_handler(CustomException)
    async def handle_custom_error(request, error):
        return JSONResponse(status_code=error.status_code, content={'detail': str(error)})

    with TestClient(app) as client:
        payload = {'app_id': 'example', 'volume_id': 'data', 'profile_id': 'local'}
        assert client.post('/host-access/app-files/sessions', json=payload).status_code == 401
        client.cookies.set(PRODUCT_AUTH_COOKIE_NAME, 'valid-session')
        assert client.post('/host-access/app-files/sessions', json={**payload, 'app_id': 'other'}).status_code == 403
        response = client.post('/host-access/app-files/sessions', json=payload)
        assert response.status_code == 200
        identifier = response.json()['session_id']
        prefix = f'/host-access/app-files/{identifier}'
        assert client.get(prefix + '/tree', params={'path': str(root)}).status_code == 200
        assert client.get(prefix + '/tree', params={'path': '/etc'}).status_code == 403
        assert client.put(prefix + '/content', json={'path': '/etc/passwd', 'content': 'unsafe'}).status_code == 403
        assert client.post(prefix + '/upload', json={'parent_path': '/etc', 'file_name': 'unsafe', 'content_base64': 'aGVsbG8='}).status_code == 403
        assert client.post(prefix + '/upload', json={'parent_path': str(root), 'file_name': 'unsafe', 'content_base64': '!!'}).status_code == 400
        assert client.request('DELETE', prefix + '/item', json={'path': str(root)}).status_code == 403
        assert client.post(prefix + '/items', json={'parent_path': str(root), 'name': 'notes.txt'}).status_code == 200
        assert client.put(prefix + '/content', json={'path': str(root / 'notes.txt'), 'content': 'safe'}).status_code == 200
        assert client.get(prefix + '/content', params={'path': str(root / 'notes.txt')}).json()['content'] == 'safe'
        assert client.get(prefix + '/download', params={'path': str(root / 'notes.txt')}).content == b'safe'
        assert client.delete(prefix + '/session').status_code == 200
        assert identifier not in service.sessions
        assert client.get(prefix + '/tree', params={'path': str(root)}).status_code == 403
        identifier = client.post('/host-access/app-files/sessions', json=payload).json()['session_id']
        prefix = f'/host-access/app-files/{identifier}'
        service.sessions[identifier]['expires_at'] = 0
        assert client.get(prefix + '/tree', params={'path': str(root)}).status_code == 403


@pytest.mark.skipif(not shutil.which('sshd') or not shutil.which('ssh-keygen') or os.getuid() != 0, reason='An isolated SSH daemon requires sshd, ssh-keygen and root')
@pytest.mark.asyncio
@pytest.mark.parametrize('pty_closed', [False, True])
async def test_terminal_websocket_refresh_does_not_report_pty_exit(monkeypatch, pty_closed):
    import asyncio
    from fastapi import WebSocketDisconnect
    from src.api.v1.routers import host_access

    messages = []
    detached = []
    async def accept():
        pass
    async def send_text(payload):
        messages.append(json.loads(payload))
    async def receive_text():
        await asyncio.sleep(0)
        raise WebSocketDisconnect()
    service = SimpleNamespace(
        attach_terminal_session=lambda **kwargs: {'profile': {'working_directory': '/root', 'username': 'root'}, 'buffer': '', 'cursor': 0},
        read_terminal_updates=lambda **kwargs: ([], 0, pty_closed),
        detach_terminal_session=lambda **kwargs: detached.append(kwargs['session_id']),
    )
    monkeypatch.setattr(host_access, '_get_host_access_service', lambda: service)
    websocket = SimpleNamespace(accept=accept, send_text=send_text, receive_text=receive_text, cookies={}, query_params={'session_id': 'refresh-session'})
    await host_access.host_access_terminal_ws(websocket)
    await asyncio.sleep(0)
    assert [message['type'] for message in messages] == (['ready', 'closed'] if pty_closed else ['ready'])
    assert detached == ['refresh-session']


def test_app_sftp_over_real_ssh(tmp_path, host_ssh_preparer, monkeypatch):
    preparation, home = host_ssh_preparer
    host_key = tmp_path / 'host-key'
    user_key = tmp_path / 'user-key'
    for key in [host_key, user_key]:
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    authorization = home / '.ssh/authorized_keys'
    authorization.parent.mkdir(mode=0o700)
    authorization.write_bytes(Path(str(user_key) + '.pub').read_bytes())
    command = [shutil.which('sshd'), '-D', '-e', '-f', '/dev/null', '-h', str(host_key), '-p', str(port), '-o', 'ListenAddress=127.0.0.1', '-o', f'AuthorizedKeysFile={authorization}', '-o', 'StrictModes=no', '-o', 'PermitRootLogin=prohibit-password', '-o', 'PasswordAuthentication=no', '-o', 'UsePAM=no', '-o', f'PidFile={tmp_path}/sshd.pid', '-o', 'Subsystem=sftp internal-sftp']
    server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        startup = server.stderr.readline()
        assert 'Server listening' in startup, startup
        monkeypatch.setitem(preparation, 'ssh_policy', lambda username: {'authorizedkeysfile': str(authorization), 'port': str(port)})
        preparation['prepare'](str(tmp_path / 'data'), 'root')
        original_authorization = authorization.read_bytes()
        preparation['prepare'](str(tmp_path / 'data'), 'root')
        assert authorization.read_bytes() == original_authorization
        script = r'''
import os
import pwd
import sys
from pathlib import Path
from types import SimpleNamespace
from src.services.host_access import HostAccessService
from src.services.app_sftp import ScopedHostAccess
from src.core.exception import CustomException
from src.services import host_access
root = Path(sys.argv[1]) / 'application'
root.mkdir()
host_access.HOST_ACCESS_HOST = '127.0.0.1'
host = HostAccessService(data_dir=str(Path(sys.argv[1]) / 'data/config/host-access'), auth_service=SimpleNamespace(_require_authenticated_operator=lambda token: {'id': 'integration-operator'}))
response = host.create_local_profile('test-session')
profile = host.get_connection_profile('test-session')
assert response['configured'] and profile['username'] == 'root'
assert profile['private_key'] not in str(response)
assert profile['port'] == int(sys.argv[2])
assert host.create_local_profile('test-session')['active_profile_id'] == response['active_profile_id']
authorization = Path(host._read_local_ssh_credentials()['authorization_path'])
files = ScopedHostAccess(host, profile, str(root))
files.create_directory(None, str(root), 'docs')
files.upload_file(None, str(root / 'docs'), 'hello.txt', b'first')
files.write_text_file(None, str(root / 'docs/hello.txt'), 'updated')
assert files.read_text_file(None, str(root / 'docs/hello.txt'))['content'] == 'updated'
files.copy_item(None, str(root / 'docs/hello.txt'), str(root))
assert files.download_file(None, str(root / 'hello.txt'))['content'] == b'updated'
files.rename_item(None, str(root / 'hello.txt'), 'renamed.txt')
files.create_directory(None, str(root), 'backup')
files.move_item(None, str(root / 'renamed.txt'), str(root / 'backup'))
files.update_item_attributes(None, {'source_path': str(root / 'backup/renamed.txt'), 'owner_permissions': {'read': True, 'write': True, 'execute': False}, 'group_permissions': {'read': False, 'write': False, 'execute': False}, 'other_permissions': {'read': False, 'write': False, 'execute': False}})
assert files.list_directory(None, str(root))['current_path'] == str(root)
for path in ['/etc/passwd', str(root / '../outside')]:
    try:
        files.read_text_file(None, path)
    except CustomException as error:
        assert error.status_code == 403
    else:
        raise AssertionError('Path escape accepted')
(root / 'escape').symlink_to('/etc', target_is_directory=True)
try:
    files.read_text_file(None, str(root / 'escape/passwd'))
except CustomException as error:
    assert error.status_code == 403
else:
    raise AssertionError('Symlink escape accepted')
files.delete_item(None, str(root / 'backup'))
assert not (root / 'backup').exists()
try:
    host._connect_client({**profile, 'auth_method': 'password', 'password': 'invalid-test-password'})
except CustomException as error:
    assert error.status_code == 400
else:
    raise AssertionError('Invalid SSH credentials accepted')
host.attach_terminal_session('test-session', 'cleanup-terminal', 80, 24)
original_channel = host._terminal_sessions['cleanup-terminal']['channel']
host.detach_terminal_session('cleanup-terminal')
reattached = host.attach_terminal_session('test-session', 'cleanup-terminal', 100, 30)
assert reattached['resumed'] is True
assert host._terminal_sessions['cleanup-terminal']['channel'] is original_channel
assert not original_channel.closed
host.attach_terminal_session('test-session', 'cleanup-terminal', 100, 30)
host.detach_terminal_session('cleanup-terminal')
assert host._terminal_sessions['cleanup-terminal']['attachments'] == 1
assert host._terminal_sessions['cleanup-terminal']['detached_at'] is None
host.delete_saved_profile('test-session', response['active_profile_id'])
assert 'cleanup-terminal' not in host._terminal_sessions
assert authorization.read_bytes() == Path(sys.argv[3] + '.pub').read_bytes()
assert not (host.data_dir / 'local-ssh.key').exists()
assert not (host.data_dir / 'local-ssh.json').exists()
try:
    host._connect_client(profile)
except CustomException as error:
    assert error.status_code == 400
else:
    raise AssertionError('Revoked SSH key still authenticates')
source = Path(sys.argv[4]).read_text()
preparation = {'__name__': 'recreation_test'}
exec(compile(source, 'host_access_prepare.py', 'exec'), preparation)
account = SimpleNamespace(pw_name='root', pw_uid=0, pw_gid=0, pw_dir=sys.argv[5], pw_shell='/bin/bash')
preparation['pwd'].getpwnam = lambda username: account
preparation['ssh_policy'] = lambda username: {'pubkeyauthentication': 'yes', 'permitrootlogin': 'prohibit-password', 'authorizedkeysfile': str(authorization), 'port': sys.argv[2]}
host._prepare_local_ssh_credentials = lambda: preparation['prepare'](str(Path(sys.argv[1]) / 'data'), 'root')
recreated = host.create_local_profile('test-session', allow_recreate=True)
new_profile = host.get_connection_profile('test-session')
assert recreated['configured']
assert recreated['active_profile_id'] != response['active_profile_id']
assert new_profile['private_key'] != profile['private_key']
assert (host.data_dir / 'local-ssh.key').exists()
assert (host.data_dir / 'local-ssh.json').exists()
assert not host._is_local_setup_revoked('integration-operator')
with host._open_sftp(new_profile) as sftp:
    assert sftp.stat(str(root)).st_mode
host.attach_terminal_session('test-session', 'recreated-terminal', 80, 24)
assert 'recreated-terminal' in host._terminal_sessions
host._close_terminal_session_locked('recreated-terminal')
try:
    host._connect_client(profile)
except CustomException:
    pass
else:
    raise AssertionError('Old revoked key was restored instead of generating a new key')
'''
        result = subprocess.run([sys.executable, '-c', script, str(tmp_path), str(port), str(user_key), str(PROJECT_ROOT / 'src/services/host_access_prepare.py'), str(home)], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
    finally:
        server.terminate()
        server.wait(timeout=10)


def test_app_sftp_does_not_override_write_permissions(scoped_files):
    service, root = scoped_files

    class ReadOnlySftp(LocalTestSftp):
        def open(self, path, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wax+'):
                raise PermissionError('Read-only SSH account')
            return super().open(path, mode, *args, **kwargs)

    @contextmanager
    def open_sftp(profile):
        yield ReadOnlySftp(root)

    service.host_service._open_sftp = open_sftp
    (root / 'notes.txt').write_text('original')
    with pytest.raises(CustomException):
        service.write_text_file('valid-session', str(root / 'notes.txt'), 'changed')
    assert (root / 'notes.txt').read_text() == 'original'


def test_list_directory_uses_locked_sftp_helper(monkeypatch):
    service = HostAccessService(auth_service=FakeAuthService())
    profile = {"working_directory": "/home/websoft9"}
    file_item_calls: list[str] = []
    open_sftp_calls: list[dict[str, str]] = []

    class FakeSFTP:
        def listdir_attr(self, path: str):
            return [
                SimpleNamespace(filename="docs", st_mode=stat.S_IFDIR | 0o755, st_uid=1002, st_gid=1002),
                SimpleNamespace(filename="notes.txt", st_mode=stat.S_IFREG | 0o644, st_uid=1002, st_gid=1002),
            ]

        def stat(self, path: str):
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=1002, st_gid=1002)

    @contextmanager
    def fake_open_sftp(active_profile):
        open_sftp_calls.append(active_profile)
        yield FakeSFTP()

    def unexpected_open_file_client(_profile):
        raise AssertionError("list_directory should use _open_sftp")

    monkeypatch.setattr(service, "get_connection_profile", lambda session_token, profile_id=None: profile)
    monkeypatch.setattr(service, "_open_sftp", fake_open_sftp)
    monkeypatch.setattr(service, "_open_file_client", unexpected_open_file_client)
    monkeypatch.setattr(service, "_resolve_directory_path", lambda sftp, path: path)
    monkeypatch.setattr(service, "_load_identity_labels", lambda sftp, owner_ids, group_ids: ({1002: "websoft9"}, {1002: "websoft9"}))
    monkeypatch.setattr(service, "_build_path_metadata", lambda sftp, path, entry=None, owner_labels=None, group_labels=None: {"path": path})
    monkeypatch.setattr(
        service,
        "_build_file_item",
        lambda base_path, entry, owner_labels=None, group_labels=None: file_item_calls.append(entry.filename) or {"path": f"{base_path}/{entry.filename}"},
    )

    payload = service.list_directory("valid-session", "/home/websoft9", profile_id="profile-1")

    assert open_sftp_calls == [profile]
    assert file_item_calls == ["docs", "notes.txt"]
    assert payload == {
        "current_path": "/home/websoft9",
        "metadata": {"path": "/home/websoft9"},
        "items": [
            {"path": "/home/websoft9/docs"},
            {"path": "/home/websoft9/notes.txt"},
        ],
    }


def test_delete_saved_profile_rejects_a_profile_used_by_scheduled_tasks(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    service = HostAccessService(data_dir=str(data_root / "config" / "host-access"), auth_service=FakeAuthService())
    service._ensure_storage()
    with service._db_connect() as connection:
        connection.execute(
            "INSERT INTO host_profiles (profile_id, operator_id, payload, updated_at, is_default) VALUES (?, ?, ?, ?, ?)",
            ("profile-1", "operator-1", "{}", "2026-08-24T00:00:00+00:00", 1),
        )
        connection.commit()

    scheduled_tasks_dir = data_root / "config" / "scheduled-tasks"
    scheduled_tasks_dir.mkdir(parents=True)
    with sqlite3.connect(scheduled_tasks_dir / "scheduled-tasks.sqlite") as connection:
        connection.execute("CREATE TABLE scheduled_tasks (operator_id TEXT, target TEXT, profile_id TEXT)")
        connection.execute("INSERT INTO scheduled_tasks VALUES (?, ?, ?)", ("operator-1", "host", "profile-1"))
        connection.commit()

    with pytest.raises(CustomException) as error:
        service.delete_saved_profile("valid-session", "profile-1")

    assert error.value.status_code == 409


def test_host_ssh_preparation_configures_and_rolls_back_sftp_sudoers_for_non_root(host_ssh_preparer, tmp_path, monkeypatch):
    preparation, home = host_ssh_preparer
    os.chown(home, 1000, 1000)
    sudoers_dir = tmp_path / "sudoers.d"
    sudoers_dir.mkdir(mode=0o750)
    sftp_binary = tmp_path / "sftp-server"
    sftp_binary.write_text("#!/bin/sh\nexit 0\n")
    sftp_binary.chmod(0o755)
    account = SimpleNamespace(pw_name="ubuntu", pw_uid=1000, pw_gid=1000, pw_dir=str(home), pw_shell="/bin/bash")
    monkeypatch.setattr(preparation["pwd"], "getpwnam", lambda username: account)
    monkeypatch.setitem(preparation, "SUDOERS_DIR", sudoers_dir)
    monkeypatch.setitem(preparation, "SFTP_SERVER_CANDIDATES", (str(sftp_binary),))
    monkeypatch.setitem(
        preparation,
        "ssh_policy",
        lambda username: {"authorizedkeysfile": ".ssh/authorized_keys", "port": "22", "subsystem": f"sftp {sftp_binary}"},
    )
    original_run = subprocess.run
    ssh_should_fail = False

    def run(command, **kwargs):
        if command[0] == "ssh":
            if ssh_should_fail:
                raise subprocess.CalledProcessError(255, command, stderr=b"Permission denied")
            return SimpleNamespace(returncode=0)
        return original_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    sudoers_file = sudoers_dir / "websoft9-local-sftp"
    ssh_should_fail = True
    with pytest.raises(subprocess.CalledProcessError):
        preparation["prepare"](str(tmp_path / "data"), "ubuntu")
    assert not sudoers_file.exists()

    ssh_should_fail = False
    preparation["prepare"](str(tmp_path / "data"), "ubuntu")
    assert sudoers_file.is_file()
    assert stat.S_IMODE(sudoers_file.stat().st_mode) == 0o440
    assert f"ubuntu ALL=(root) NOPASSWD: {sftp_binary}" in sudoers_file.read_text()


def test_app_sftp_elevates_non_root_sftp_and_auto_prepares_on_permission_error(tmp_path, monkeypatch):
    import paramiko

    root = tmp_path / "volume"
    root.mkdir()
    host = HostAccessService(data_dir=str(tmp_path / "host-access"), auth_service=FakeAuthService())
    profile = {"profile_id": "auto-local-1", "host": "127.0.0.1", "port": 22, "username": "ubuntu", "auth_method": "key", "private_key": "KEY"}
    monkeypatch.setattr(host, "get_connection_profile", lambda token, profile_id=None: profile)

    exec_commands = []
    sudo_ready = False

    class DeniedSftp(LocalTestSftp):
        def lstat(self, path):
            if not sudo_ready:
                raise PermissionError(13, "Permission denied", path)
            return super().lstat(path)

        def close(self):
            pass

        def get_channel(self):
            return SimpleNamespace(closed=False)

    class ElevatedSftp(LocalTestSftp):
        def close(self):
            pass

        def get_channel(self):
            return SimpleNamespace(closed=False)

    class FakeChannel:
        closed = False

        def exec_command(self, cmd):
            exec_commands.append(cmd)
            if not sudo_ready:
                raise RuntimeError("sudo password required")

        def close(self):
            self.closed = True

    fake_client = SimpleNamespace(
        get_transport=lambda: SimpleNamespace(is_active=lambda: True, open_session=lambda: FakeChannel()),
        open_sftp=lambda: DeniedSftp(root),
        close=lambda: None,
    )

    @contextmanager
    def fake_open_file_client(_profile):
        yield fake_client

    monkeypatch.setattr(host, "_open_file_client", fake_open_file_client)
    monkeypatch.setattr(paramiko, "SFTPClient", lambda channel: ElevatedSftp(root))
    prepared_users = []

    def fake_prepare(username=""):
        nonlocal sudo_ready
        prepared_users.append(username)
        sudo_ready = True

    monkeypatch.setattr(host, "_prepare_local_ssh_credentials", fake_prepare)
    volume = {"Driver": "local", "Options": {}, "Mountpoint": str(root), "Labels": {"com.docker.compose.project": "example"}}
    docker_client = SimpleNamespace(volumes=SimpleNamespace(get=lambda identifier: SimpleNamespace(attrs=volume)))
    service = AppSftpService(host, docker_client_factory=lambda: docker_client)

    session = service.create("valid-session", "example", "data", "auto-local-1")
    assert session["username"] == "ubuntu"
    assert prepared_users == ["ubuntu"]
    assert len(exec_commands) == 2
    assert "exec sudo -n" in exec_commands[0]

    scoped = service.access("valid-session", session["session_id"])
    scoped.create_empty_file("valid-session", str(root), "hello.txt")
    assert (root / "hello.txt").is_file()
