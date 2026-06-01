import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Optional


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


class FakeAuthService:
    def _require_authenticated_operator(self, session_token: Optional[str]):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")
        return {"id": "operator-1"}


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