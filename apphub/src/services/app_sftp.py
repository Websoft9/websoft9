import posixpath
import stat
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import PurePosixPath

from src.core.exception import CustomException
from src.services.host_access import HostAccessService


class ScopedSftp:
    def __init__(self, sftp, root):
        self.sftp = sftp
        self.root = posixpath.normpath(root)

    def checked(self, path, mutate=False):
        candidate = posixpath.normpath(str(path))
        if not candidate.startswith('/') or not (candidate == self.root or candidate.startswith(self.root + '/')):
            raise CustomException(403, 'SFTP Scope Denied', 'The path is outside the application directory')
        if mutate and candidate == self.root:
            raise CustomException(403, 'SFTP Scope Denied', 'The application root cannot be modified')
        current = '/'
        for part in candidate.strip('/').split('/'):
            current = posixpath.join(current, part)
            try:
                entry = self.sftp.lstat(current)
            except FileNotFoundError:
                if current != candidate:
                    raise
                break
            if stat.S_ISLNK(entry.st_mode):
                raise CustomException(403, 'SFTP Scope Denied', 'Symbolic links are not supported in application SFTP')
            if current == candidate and mutate and stat.S_ISREG(entry.st_mode) and getattr(entry, 'st_nlink', 1) > 1:
                raise CustomException(403, 'SFTP Scope Denied', 'Hard-linked files cannot be modified')
        return candidate

    def normalize(self, path):
        candidate = path if path == '.' else self.checked(path)
        return self.checked(self.sftp.normalize(candidate))

    def chdir(self, path):
        return self.sftp.chdir(self.checked(path))

    def stat(self, path):
        return self.sftp.stat(self.checked(path))

    def lstat(self, path):
        return self.sftp.lstat(self.checked(path))

    def listdir_attr(self, path):
        return [entry for entry in self.sftp.listdir_attr(self.checked(path)) if stat.S_ISDIR(entry.st_mode) or stat.S_ISREG(entry.st_mode)]

    def open(self, path, mode='r', *args, **kwargs):
        candidate = self.checked(path, mutate=any(flag in mode for flag in 'wax+'))
        try:
            entry = self.sftp.lstat(candidate)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(entry.st_mode):
                raise CustomException(403, 'SFTP Scope Denied', 'Only regular files can be opened')
        return self.sftp.open(candidate, mode, *args, **kwargs)

    def mkdir(self, path):
        return self.sftp.mkdir(self.checked(path, mutate=True))

    def remove(self, path):
        return self.sftp.remove(self.checked(path, mutate=True))

    def rmdir(self, path):
        return self.sftp.rmdir(self.checked(path, mutate=True))

    def rename(self, source, target):
        return self.sftp.rename(self.checked(source, mutate=True), self.checked(target, mutate=True))

    def putfo(self, handle, path):
        return self.sftp.putfo(handle, self.checked(path, mutate=True))

    def chmod(self, path, mode):
        return self.sftp.chmod(self.checked(path, mutate=True), mode)


@contextmanager
def open_host_sftp(host_service, profile):
    if '_open_sftp' in getattr(host_service, '__dict__', {}) or not isinstance(host_service, HostAccessService):
        with host_service._open_sftp(profile) as sftp:
            yield sftp
    else:
        with host_service._open_sftp(profile, elevated=True) as sftp:
            yield sftp


class ScopedHostAccess(HostAccessService):
    def __init__(self, host_service, profile, root):
        super().__init__(data_dir=str(host_service.data_dir), auth_service=host_service.auth_service)
        self.host_service = host_service
        self.profile = profile
        self.root = root
        self._identity_label_cache = {}
        self._identity_source_cache = {}

    def get_connection_profile(self, session_token, profile_id=None):
        return self.profile

    @contextmanager
    def _open_sftp(self, profile):
        with open_host_sftp(self.host_service, profile) as sftp:
            yield ScopedSftp(sftp, self.root)

    def _load_identity_labels(self, sftp, owner_ids, group_ids):
        return super()._load_identity_labels(sftp.sftp, owner_ids, group_ids)

    def copy_item(self, session_token, source_path, destination_path, profile_id=None):
        with self._open_sftp(self.profile) as sftp:
            source = sftp.checked(source_path, mutate=True)
            destination = sftp.checked(destination_path)
            target = self._join_remote_path(destination, PurePosixPath(source).name)
            if target == source or target.startswith(source + '/'):
                raise CustomException(400, 'Copy Failed', 'A directory cannot be copied into itself')
            self._copy_tree(sftp, source, target)
        return {'path': target, 'operation': 'copy'}

    def _copy_tree(self, sftp, source, target):
        try:
            sftp.stat(target)
        except FileNotFoundError:
            pass
        else:
            raise CustomException(400, 'Copy Failed', 'A file or directory with the same name already exists')
        entry = sftp.stat(source)
        if stat.S_ISDIR(entry.st_mode):
            sftp.mkdir(target)
            for child in sftp.listdir_attr(source):
                self._copy_tree(sftp, self._join_remote_path(source, child.filename), self._join_remote_path(target, child.filename))
        elif stat.S_ISREG(entry.st_mode):
            with sftp.open(source, 'rb') as reader, sftp.open(target, 'wx') as writer:
                while chunk := reader.read(65536):
                    writer.write(chunk)
        else:
            raise CustomException(403, 'SFTP Scope Denied', 'Only regular files and directories can be copied')

    def update_item_attributes(self, session_token, payload, profile_id=None):
        if payload.get('owner') or payload.get('group'):
            raise CustomException(403, 'SFTP Scope Denied', 'Owner and group changes are not available in application SFTP')
        path = payload['source_path']
        if payload.get('target_name') and payload['target_name'] != PurePosixPath(path).name:
            path = self.rename_item(session_token, path, payload['target_name'])['path']
        mode = self._build_permission_mode(payload)
        with self._open_sftp(self.profile) as sftp:
            if mode is not None:
                sftp.chmod(path, int(str(mode), 8))
            metadata = self._build_path_metadata(sftp, path, entry=sftp.stat(path), owner_labels={}, group_labels={})
        return {'path': path, 'operation': 'update-attributes', 'metadata': metadata}


class AppSftpService:
    def __init__(self, host_service, docker_client_factory=None):
        self.host_service = host_service
        self.docker_client_factory = docker_client_factory
        self.sessions = {}
        self.lock = threading.RLock()

    def volume_root(self, app_id, volume_id):
        import docker

        client = self.docker_client_factory() if self.docker_client_factory else docker.from_env()
        try:
            if not self.docker_client_factory and not client.api.base_url.startswith('http+docker://'):
                raise CustomException(422, 'Unsupported Host', 'Application SFTP currently requires the local Docker host')
            volume = client.volumes.get(volume_id).attrs
        except docker.errors.NotFound as exc:
            raise CustomException(404, 'Volume Not Found', 'The application volume no longer exists') from exc
        except docker.errors.DockerException as exc:
            raise CustomException(503, 'Docker Unavailable', 'Unable to resolve the application volume') from exc
        finally:
            if not self.docker_client_factory:
                client.close()
        if (volume.get('Labels') or {}).get('com.docker.compose.project') != app_id:
            raise CustomException(403, 'Volume Access Denied', 'The volume does not belong to this application')
        root = volume.get('Mountpoint') or ''
        if volume.get('Driver') != 'local' or volume.get('Options') or not root.startswith('/') or posixpath.normpath(root) == '/':
            raise CustomException(422, 'Unsupported Volume', 'Application SFTP requires a local Docker volume')
        return posixpath.normpath(root)

    def create(self, session_token, app_id, volume_id, profile_id):
        operator = self.host_service.auth_service._require_authenticated_operator(session_token)
        root = self.volume_root(app_id, volume_id)
        if not profile_id:
            profiles = self.host_service.get_profile(session_token)
            candidates = [entry for entry in profiles.get('saved_profiles', []) if entry.get('is_local') and (entry.get('has_password') or entry.get('has_private_key'))]
            preferred = next((identifier for identifier in [profiles.get('active_profile_id'), profiles.get('default_profile_id')] if any(entry['profile_id'] == identifier for entry in candidates)), None)
            candidates.sort(key=lambda entry: entry['profile_id'] != preferred)
            if len(candidates) > 1 and candidates[0]['profile_id'] != preferred:
                raise CustomException(409, 'SFTP Connection Required', 'Choose a local host connection')
            if candidates:
                profile_id = candidates[0]['profile_id']
        profile = self.host_service.get_connection_profile(session_token, profile_id=profile_id)
        if not self.host_service._is_local_host_value(profile.get('host')):
            raise CustomException(403, 'SFTP Host Mismatch', 'Choose a connection to the application host')
        try:
            self._verify_volume_access(profile, root)
        except CustomException as exc:
            if isinstance(exc.__cause__, PermissionError) and self._prepare_elevated_sftp(profile):
                self._verify_volume_access(profile, root)
            else:
                raise
        now = time.time()
        identifier = uuid.uuid4().hex
        profile_id = profile.get('profile_id') or profile_id
        with self.lock:
            self.sessions = {key: value for key, value in self.sessions.items() if value['expires_at'] > now}
            self.sessions[identifier] = {'operator_id': operator['id'], 'profile_id': profile_id, 'root': root, 'app_id': app_id, 'volume_id': volume_id, 'expires_at': now + 1800, 'connection': (profile.get('host'), profile.get('port'), profile.get('username'))}
        return {'session_id': identifier, 'root_path': root, 'app_id': app_id, 'volume_id': volume_id, 'profile_id': profile_id, 'expires_at': now + 1800, 'host': profile.get('host'), 'username': profile.get('username'), 'port': profile.get('port')}

    def _verify_volume_access(self, profile, root):
        try:
            with open_host_sftp(self.host_service, profile) as sftp:
                try:
                    guarded = ScopedSftp(sftp, root)
                    guarded.stat(root)
                    guarded.listdir_attr(root)
                except OSError as exc:
                    raise CustomException(403, 'SFTP Directory Unavailable', f'The connection cannot access the application directory: {exc}') from exc
        except OSError as exc:
            raise CustomException(403, 'SFTP Directory Unavailable', f'The connection cannot access the application directory: {exc}') from exc

    def _prepare_elevated_sftp(self, profile):
        if not isinstance(self.host_service, HostAccessService):
            return False
        username = str(profile.get('username') or '').strip()
        if username in ('', 'root'):
            return False
        try:
            self.host_service._prepare_local_ssh_credentials(username)
            with self.host_service._lock:
                self.host_service._close_file_browser_client_locked(self.host_service._build_file_client_cache_key(profile))
            return True
        except Exception:
            return False

    def access(self, session_token, identifier):
        operator = self.host_service.auth_service._require_authenticated_operator(session_token)
        with self.lock:
            session = self.sessions.get(identifier)
            if session and session['expires_at'] <= time.time():
                self.sessions.pop(identifier, None)
                session = None
        if not session or session['operator_id'] != operator['id']:
            raise CustomException(403, 'SFTP Session Expired', 'The application SFTP session is unavailable; reopen it from the application')
        if self.volume_root(session['app_id'], session['volume_id']) != session['root']:
            raise CustomException(403, 'SFTP Scope Denied', 'The application volume has changed')
        profile = self.host_service.get_connection_profile(session_token, profile_id=session['profile_id'])
        if not self.host_service._is_local_host_value(profile.get('host')):
            raise CustomException(403, 'SFTP Host Mismatch', 'The connection no longer targets the application host')
        if session['connection'] != (profile.get('host'), profile.get('port'), profile.get('username')):
            raise CustomException(403, 'SFTP Connection Changed', 'The saved connection has changed; reopen application SFTP')
        return ScopedHostAccess(self.host_service, profile, session['root'])

    def invalidate_profile(self, operator_id, profile_id):
        with self.lock:
            self.sessions = {
                key: session for key, session in self.sessions.items()
                if session['operator_id'] != operator_id or session['profile_id'] != profile_id
            }