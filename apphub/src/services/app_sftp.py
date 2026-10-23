import posixpath
import logging
import stat
import threading
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Optional

from src.core.exception import CustomException
from src.services.app_sftp_account import AppSftpAccountService
from src.services.host_access import HostAccessService
from src.services.sftp_path_authorization import AppSftpAuthority, PLATFORM_ACCOUNT_PROFILE_ID, SESSION_TTL_SECONDS

logger = logging.getLogger(__name__)


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
def open_host_sftp(host_service, profile, elevated=False):
    if elevated:
        with host_service._open_sftp(profile, elevated=True) as sftp:
            yield sftp
    else:
        with host_service._open_sftp(profile) as sftp:
            yield sftp


class ScopedHostAccess(HostAccessService):
    def __init__(self, host_service, profile, root, elevated=False):
        super().__init__(data_dir=str(host_service.data_dir), auth_service=host_service.auth_service)
        self.host_service = host_service
        self.profile = profile
        self.root = root
        self.elevated = elevated
        self._identity_label_cache = {}
        self._identity_source_cache = {}

    def get_connection_profile(self, session_token, profile_id=None):
        return self.profile

    @contextmanager
    def _open_sftp(self, profile):
        with open_host_sftp(self.host_service, profile, elevated=self.elevated) as sftp:
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
    """Application file access over the platform-owned SFTP account.

    The session root is authorized with a POSIX ACL for the duration of the
    session and restored from a snapshot when the session ends. No user host
    credentials, sudo rules or per-application accounts are involved.
    """

    def __init__(self, host_service, docker_client_factory=None, account_service=None, authority=None):
        self.host_service = host_service
        self.docker_client_factory = docker_client_factory
        self.sessions = {}
        self.lock = threading.RLock()
        data_dir = str(getattr(host_service, 'data_dir', '') or '') or None
        self.account = account_service or AppSftpAccountService(data_dir=data_dir, docker_client_factory=docker_client_factory)
        self.authority = authority or AppSftpAuthority(data_dir=Path(data_dir) if data_dir else None, docker_client_factory=docker_client_factory)
        self._reconciled = False

    def _ensure_reconciled(self):
        if self._reconciled:
            return
        self._reconciled = True

        def release_stale_sessions():
            # Leftover sessions are cleaned shortly after startup, never in the
            # critical path of the first file session.
            time.sleep(3)
            try:
                self.authority.reconcile()
            except Exception as exc:
                logger.warning(f"Application SFTP reconciliation skipped: {exc}")

        # Never block the first file session on cleaning up sessions left behind
        # by a previous AppHub process.
        threading.Thread(target=release_stale_sessions, daemon=True).start()

    def account_status(self, session_token):
        self.host_service.auth_service._require_authenticated_operator(session_token)
        return self.account.status()

    def account_prepare(self, session_token):
        self.host_service.auth_service._require_authenticated_operator(session_token)
        state = self.account.ensure()
        self.account_status(session_token)
        return state

    def revoke_account(self, session_token):
        """Remove the platform SFTP authorization and close every session."""
        self.host_service.auth_service._require_authenticated_operator(session_token)
        with self.lock:
            identifiers = [sid for sid, session in self.sessions.items() if session.get('mode') != 'profile']
        for identifier in identifiers:
            self.release(identifier)
        self.authority.release_all()
        return self.account.revoke()

    def create(self, session_token, app_id, volume_id, profile_id=None, elevate=False, use_platform=False):
        operator = self.host_service.auth_service._require_authenticated_operator(session_token)
        self._ensure_reconciled()
        target = self.authority.resolve(app_id, volume_id)

        local_profile = None if use_platform else self._usable_local_profile(operator['id'], profile_id)
        if local_profile is not None:
            elevated = False
            try:
                self._verify_volume_access(local_profile, target['source_path'])
            except CustomException:
                if not elevate:
                    raise
                self._verify_volume_access(local_profile, target['source_path'], elevated=True)
                elevated = True
            identifier = self.authority.new_session_id()
            now = time.time()
            with self.lock:
                self.sessions = {key: value for key, value in self.sessions.items() if value['expires_at'] > now}
                self.sessions[identifier] = {
                    'operator_id': operator['id'],
                    'root': target['source_path'],
                    'app_id': app_id,
                    'volume_id': volume_id,
                    'expires_at': now + SESSION_TTL_SECONDS,
                    'profile': local_profile,
                    'container_uid': int(target.get('container_uid') or 0),
                    'mode': 'profile',
                    'elevated': elevated,
                }
            self._warm_connection(local_profile)
            return {
                'session_id': identifier,
                'root_path': target['source_path'],
                'app_id': app_id,
                'volume_id': volume_id,
                'profile_id': local_profile.get('profile_id'),
                'account': local_profile.get('username'),
                'source_container': target.get('container_name'),
                'expires_at': now + SESSION_TTL_SECONDS,
                'host': local_profile.get('host'),
                'username': local_profile.get('username'),
                'port': local_profile.get('port'),
                'elevated': elevated,
            }

        if self.account.status().get('state') != 'ready':
            # No usable local connection and no platform account: the operator
            # must confirm automatic setup first.
            raise CustomException(
                409,
                'SFTP Account Unavailable',
                'The platform SFTP account is not prepared yet. Confirm automatic setup to continue.',
            )
        profile = self.account.credentials()
        identifier = self.authority.new_session_id()
        try:
            self.authority.authorize(
                session_id=identifier,
                operator_id=operator['id'],
                app_id=app_id,
                volume_id=volume_id,
                target=target,
            )
        except Exception:
            self.authority.release(identifier)
            raise
        now = time.time()
        with self.lock:
            self.sessions = {key: value for key, value in self.sessions.items() if value['expires_at'] > now}
            self.sessions[identifier] = {
                'operator_id': operator['id'],
                'root': target['source_path'],
                'app_id': app_id,
                'volume_id': volume_id,
                'expires_at': now + SESSION_TTL_SECONDS,
                'profile': profile,
                'container_uid': int(target.get('container_uid') or 0),
            }
        self._warm_connection(profile)
        return {
            'session_id': identifier,
            'root_path': target['source_path'],
            'app_id': app_id,
            'volume_id': volume_id,
            'profile_id': None,
            'account': profile.get('username'),
            'source_container': target.get('container_name'),
            'expires_at': now + SESSION_TTL_SECONDS,
            'host': profile.get('host'),
            'username': profile.get('username'),
            'port': profile.get('port'),
        }

    def _usable_local_profile(self, operator_id: str, profile_id: Optional[str] = None) -> Optional[dict]:
        """Return a saved local connection that can actually authenticate."""
        try:
            profiles = self.host_service._list_operator_profiles(str(operator_id))
        except Exception:
            return None
        usable = {
            str(entry.get('profile_id'))
            for entry in profiles
            if entry.get('is_local') and (entry.get('has_password') or entry.get('has_private_key'))
        }
        if not usable:
            return None
        order: list[str] = []
        if profile_id and str(profile_id) in usable:
            order.append(str(profile_id))
        try:
            active = self.host_service._get_active_profile_id(str(operator_id))
        except Exception:
            active = None
        if active in usable and active not in order:
            order.append(active)
        for entry in profiles:
            identifier = str(entry.get('profile_id'))
            if entry.get('is_default') and identifier in usable and identifier not in order:
                order.append(identifier)
        for entry in profiles:
            identifier = str(entry.get('profile_id'))
            if identifier in usable and identifier not in order:
                order.append(identifier)
        for identifier in order:
            try:
                profile = self.host_service._load_saved_profile(str(operator_id), identifier)
            except Exception:
                continue
            if profile is not None and self.host_service._is_local_host_value(profile.get('host')):
                return profile
        return None

    def _warm_connection(self, profile):
        def warm():
            try:
                with open_host_sftp(self.host_service, profile):
                    pass
            except Exception as exc:
                logger.debug(f"Application SFTP warm-up skipped: {exc}")

        threading.Thread(target=warm, daemon=True).start()

    def _verify_volume_access(self, profile, root, elevated=False):
        try:
            with open_host_sftp(self.host_service, profile, elevated=elevated) as sftp:
                try:
                    guarded = ScopedSftp(sftp, root)
                    guarded.stat(root)
                    guarded.listdir_attr(root)
                except OSError as exc:
                    raise CustomException(403, 'SFTP Directory Unavailable', f'The connection cannot access the application directory: {exc}') from exc
        except OSError as exc:
            raise CustomException(403, 'SFTP Directory Unavailable', f'The connection cannot access the application directory: {exc}') from exc

    def grant_path(self, session_id, path):
        with self.lock:
            if session_id not in self.sessions:
                return None
        try:
            return self.authority.grant(session_id, path)
        except CustomException as exc:
            logger.warning(f"Application SFTP grant failed for {path}: {exc.details or exc.message}")
            return None

    def release(self, session_id):
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session is not None:
            try:
                with self.host_service._lock:
                    self.host_service._close_file_browser_client_locked(
                        self.host_service._build_file_client_cache_key(session['profile'])
                    )
            except Exception:
                pass
        self.authority.release(session_id)

    def access(self, session_token, identifier):
        operator = self.host_service.auth_service._require_authenticated_operator(session_token)
        with self.lock:
            session = self.sessions.get(identifier)
            if session and session['expires_at'] <= time.time():
                self.sessions.pop(identifier, None)
                session = None
        if not session or session['operator_id'] != operator['id']:
            raise CustomException(403, 'SFTP Session Expired', 'The application SFTP session is unavailable; reopen it from the application')
        try:
            self.authority.store.touch(identifier)
        except Exception:
            pass
        return ScopedHostAccess(self.host_service, session['profile'], session['root'], elevated=bool(session.get('elevated')))

    def invalidate_profile(self, operator_id, profile_id):
        # Application file sessions are not bound to saved host profiles, but the
        # terminal still uses this hook; drop any legacy matching entries.
        with self.lock:
            self.sessions = {
                key: session for key, session in self.sessions.items()
                if session.get('operator_id') != operator_id
                or (session.get('profile_id') or (session.get('profile') or {}).get('profile_id')) != profile_id
            }

    def invalidate_profile(self, operator_id, profile_id):
        with self.lock:
            self.sessions = {
                key: session for key, session in self.sessions.items()
                if session['operator_id'] != operator_id or session['profile_id'] != profile_id
            }