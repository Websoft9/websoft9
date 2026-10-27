"""Regression tests for administrator-mode scoping and session lifecycle.

These cover behaviour that only shows up in real flows:
  * an application file session must never silently use another account
  * administrator mode is scoped per view (host vs each application)
  * signing out closes every interactive session and drops elevation state
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services.app_sftp import AppSftpService
from src.services.host_access import HostAccessService


class FakeAuth:
    def _require_authenticated_operator(self, session_token):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")
        return {"id": "operator-1"}


class FakeAccount:
    def ensure(self, force: bool = False):
        return {"state": "ready"}

    def status(self):
        return {"state": "ready"}

    def credentials(self):
        return {"profile_id": "platform-sftp", "host": "127.0.0.1", "port": 22, "username": "websoft9-sftp", "auth_method": "key", "private_key": "", "passphrase": ""}


class FakeAuthority:
    def __init__(self, root):
        self.root = root
        self.released: list[str] = []
        self.counter = 0
        self.store = SimpleNamespace(touch=lambda identifier: None)

    def new_session_id(self):
        self.counter += 1
        return f"session-{self.counter}"

    def resolve(self, app_id, volume_id):
        return {"source_path": self.root, "container_uid": 0, "container_name": "app-1"}

    def authorize(self, **kwargs):
        return {"path": self.root}

    def grant(self, session_id, path):
        return {"path": path}

    def release(self, session_id):
        self.released.append(session_id)

    def reconcile(self):
        return None


def _service(tmp_path, profiles):
    host = HostAccessService(data_dir=str(tmp_path / "host-access"), auth_service=FakeAuth())
    host._list_operator_profiles = lambda operator_id: profiles
    host._get_active_profile_id = lambda operator_id: profiles[0]["profile_id"] if profiles else None
    return host


def test_create_never_falls_back_to_another_connection(tmp_path):
    root = tmp_path / "volume"
    root.mkdir()
    host = _service(tmp_path, [{"profile_id": "auto-local", "is_local": True, "has_private_key": True}])
    service = AppSftpService(host, account_service=FakeAccount(), authority=FakeAuthority(str(root)))

    with pytest.raises(CustomException) as error:
        service.create("valid-session", "example", "data", profile_id="chosen-connection")
    assert error.value.status_code == 400
    assert error.value.message == "Host Access Profile Not Found"

    # Without an explicit choice the service falls back to the platform account,
    # never to some other saved local connection.
    session = service.create("valid-session", "example", "data")
    assert session["account"] == "websoft9-sftp"
    assert session["profile_id"] is None


def test_elevation_status_is_scoped_per_view(tmp_path):
    host = _service(tmp_path, [])
    profile = {"profile_id": "p1", "username": "sftpadmin", "auth_method": "key"}
    host.get_connection_profile = lambda token, profile_id=None: profile
    host._probe_file_elevation = lambda value: {"can_elevate": True, "requires_password": False, "reason": "passwordless"}

    @contextmanager
    def open_client(value):
        yield object()

    host._open_file_client = open_client
    host._elevated_sftp_works = lambda client, password: True

    host.set_file_elevation("valid-session", {"enabled": True, "profile_id": "p1"})

    assert host.file_elevation_status("valid-session", "p1", scope="host")["enabled"] is True
    assert host.file_elevation_status("valid-session", "p1", scope="app", app_id="a1", volume_id="v1")["enabled"] is False
    assert host.file_elevation_status("valid-session", "p1", scope="app", app_id="a2", volume_id="v1")["enabled"] is False

    host.set_file_elevation("valid-session", {"enabled": True, "profile_id": "p1", "scope": "app", "app_id": "a1", "volume_id": "v1"})
    assert host.file_elevation_status("valid-session", "p1", scope="app", app_id="a1", volume_id="v1")["enabled"] is True
    assert host.file_elevation_status("valid-session", "p1", scope="host")["enabled"] is True

    host.set_file_elevation("valid-session", {"enabled": False, "profile_id": "p1", "scope": "app", "app_id": "a1", "volume_id": "v1"})
    disabled = host.file_elevation_status("valid-session", "p1", scope="app", app_id="a1", volume_id="v1")
    assert disabled["enabled"] is False
    assert disabled["can_elevate"] is True


def test_logout_clears_sessions_and_elevation(tmp_path):
    host = _service(tmp_path, [{"profile_id": "p1"}])
    HostAccessService._terminal_sessions.clear()
    HostAccessService._file_elevation.clear()
    HostAccessService._terminal_sessions["t1"] = {"operator_id": "operator-1", "client": None, "channel": None}
    HostAccessService._terminal_sessions["t2"] = {"operator_id": "operator-2", "client": None, "channel": None}
    HostAccessService._file_elevation["host:p1"] = {"enabled": True, "password": ""}
    HostAccessService._file_elevation["app:a1:v1:p1"] = {"enabled": True, "password": ""}
    HostAccessService._file_elevation["host:p9"] = {"enabled": True, "password": ""}

    closed = host.close_operator_sessions("operator-1")

    assert closed == 1
    assert "t1" not in HostAccessService._terminal_sessions
    assert "t2" in HostAccessService._terminal_sessions
    assert "host:p1" not in HostAccessService._file_elevation
    assert "app:a1:v1:p1" not in HostAccessService._file_elevation
    assert "host:p9" in HostAccessService._file_elevation

    HostAccessService._terminal_sessions.clear()
    HostAccessService._file_elevation.clear()


def test_logout_releases_application_file_sessions(tmp_path):
    root = tmp_path / "volume"
    root.mkdir()
    host = _service(tmp_path, [])
    authority = FakeAuthority(str(root))
    service = AppSftpService(host, account_service=FakeAccount(), authority=authority)
    service.sessions = {
        "mine": {"operator_id": "operator-1", "root": str(root), "profile": {"profile_id": "p1"}, "expires_at": 9e18},
        "other": {"operator_id": "operator-2", "root": str(root), "profile": {"profile_id": "p1"}, "expires_at": 9e18},
    }

    released = service.close_operator_sessions("operator-1")

    assert released == 1
    assert "mine" not in service.sessions
    assert "other" in service.sessions
