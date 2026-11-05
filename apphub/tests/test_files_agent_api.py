"""HTTP surface of the files agent.

Two answers have to stay identical no matter where the bytes live: on this host, or inside the
host's Docker volumes (served through a privileged helper container). The console talks to these
endpoints only, so the request/response shapes and the error mapping are the contract.
"""

import base64
import os
import stat
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src import files_agent


@pytest.fixture
def agent(monkeypatch, tmp_path):
    volume = tmp_path / "volume"
    volume.mkdir()
    monkeypatch.setenv("WEBSOFT9_FILES_AGENT_ALLOWED_ROOTS", str(volume))
    monkeypatch.setenv("WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH", str(tmp_path / "gateway" / "cert.pem"))
    monkeypatch.setattr(files_agent, "_detect_docker_volumes_root", lambda: str(volume))
    for cached in (files_agent._allowed_roots, files_agent._docker_allowed_roots):
        cache_clear = getattr(cached, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()
    yield SimpleNamespace(client=TestClient(files_agent.app), volume=volume, tmp=tmp_path)
    for cached in (files_agent._allowed_roots, files_agent._docker_allowed_roots):
        cache_clear = getattr(cached, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()


class FakeHelperManager:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {"status": "ok"}

    def execute(self, root_path, action, payload):
        self.calls.append({"root": root_path, "action": action, "payload": payload})
        return self.result


def test_health_check(agent):
    response = agent.client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── directory listing ─────────────────────────────────────────────────────


def test_directory_listing_is_sorted_and_reports_sizes(agent):
    (agent.volume / "b.txt").write_text("12345")
    (agent.volume / "A.txt").write_text("1")
    (agent.volume / "nested").mkdir()

    response = agent.client.post("/internal/files/directory", json={"root_path": str(agent.volume)})

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["path"] == "/"
    names = [item["name"] for item in body["items"]]
    # 大小写不敏感排序,目录大小为 0
    assert names == ["A.txt", "b.txt", "nested"]
    by_name = {item["name"]: item for item in body["items"]}
    assert by_name["b.txt"]["size"] == 5
    assert by_name["b.txt"]["path"] == "/b.txt"
    assert by_name["nested"]["item_type"] == "directory"
    assert by_name["nested"]["size"] == 0
    assert by_name["b.txt"]["text_editable"] is True


def test_listing_a_file_is_rejected(agent):
    (agent.volume / "a.txt").write_text("x")

    response = agent.client.post("/internal/files/directory", json={"root_path": str(agent.volume), "path": "/a.txt"})

    assert response.status_code == 400
    assert response.json()["details"] == "The requested path is not a directory"


def test_listing_a_missing_directory_is_not_found(agent):
    response = agent.client.post("/internal/files/directory", json={"root_path": str(agent.volume), "path": "/nope"})

    assert response.status_code == 404


def test_the_root_must_be_inside_the_allowlist(agent):
    response = agent.client.post("/internal/files/directory", json={"root_path": str(agent.tmp)})

    assert response.status_code == 400
    assert "outside the allowed files-agent roots" in response.json()["details"]


def test_a_missing_root_is_not_found(agent):
    response = agent.client.post("/internal/files/directory", json={"root_path": str(agent.tmp / "gateway" / "missing")})

    assert response.status_code == 404


def test_a_missing_request_field_is_a_validation_error(agent):
    response = agent.client.post("/internal/files/directory", json={"path": "/"})

    assert response.status_code == 400
    assert response.json()["message"] == "Request Validation Error"
    assert "root_path" in response.json()["details"]


# ── metadata ──────────────────────────────────────────────────────────────


def test_metadata_includes_identity_ids(agent):
    target = agent.volume / "a.txt"
    target.write_text("x")

    response = agent.client.post(
        "/internal/files/metadata",
        json={"root_path": str(agent.volume), "path": "/a.txt", "display_name": "ignored"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "a.txt"
    assert body["mode"].startswith("-")
    # 详情接口带上数字 id,方便设置面板展示
    assert ") " in body["owner"] or body["owner"].endswith(")")


# ── reading and writing ───────────────────────────────────────────────────


def test_reading_a_text_file(agent):
    (agent.volume / "notes.txt").write_text("hello\n")

    response = agent.client.post("/internal/files/read-text", json={"root_path": str(agent.volume), "path": "/notes.txt"})

    assert response.status_code == 200
    assert response.json() == {"content": "hello\n"}


def test_binary_files_are_not_offered_to_the_editor(agent):
    (agent.volume / "data.bin").write_bytes(b"abc\x00def")

    response = agent.client.post("/internal/files/read-text", json={"root_path": str(agent.volume), "path": "/data.bin"})

    assert response.status_code == 400
    assert "Binary files" in response.json()["details"]


def test_non_utf8_files_are_rejected(agent):
    (agent.volume / "latin.txt").write_bytes(b"caf\xe9")

    response = agent.client.post("/internal/files/read-text", json={"root_path": str(agent.volume), "path": "/latin.txt"})

    assert response.status_code == 400
    assert "UTF-8" in response.json()["details"]


def test_files_above_the_editor_limit_are_rejected(agent):
    (agent.volume / "big.txt").write_bytes(b"a" * (files_agent.TEXT_FILE_LIMIT_BYTES + 1))

    response = agent.client.post("/internal/files/read-text", json={"root_path": str(agent.volume), "path": "/big.txt"})

    assert response.status_code == 400
    assert "too large" in response.json()["details"]


def test_the_volume_root_cannot_be_edited_as_a_file(agent):
    response = agent.client.post("/internal/files/read-text", json={"root_path": str(agent.volume), "path": "/"})

    assert response.status_code == 400
    assert response.json()["details"] == "The volume root is not a valid target for this operation"


def test_writing_creates_missing_directories(agent):
    response = agent.client.put(
        "/internal/files/write-text",
        json={"root_path": str(agent.volume), "path": "/cfg/app.conf", "content": "port=8080\n"},
    )

    assert response.status_code == 200
    assert (agent.volume / "cfg" / "app.conf").read_text() == "port=8080\n"


def test_overwriting_a_file_keeps_its_mode(agent):
    target = agent.volume / "run.sh"
    target.write_text("old")
    target.chmod(0o640)

    response = agent.client.put(
        "/internal/files/write-text",
        json={"root_path": str(agent.volume), "path": "/run.sh", "content": "new"},
    )

    assert response.status_code == 200
    assert target.read_text() == "new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_writing_outside_the_root_is_rejected(agent):
    response = agent.client.put(
        "/internal/files/write-text",
        json={"root_path": str(agent.volume), "path": "/../escape.txt", "content": "x"},
    )

    assert response.status_code == 400
    assert not (agent.tmp / "escape.txt").exists()


# ── create / rename / copy / move ─────────────────────────────────────────


def test_create_directory_and_file(agent):
    assert (
        agent.client.post(
            "/internal/files/create-directory",
            json={"root_path": str(agent.volume), "path": "/plugins"},
        ).status_code
        == 200
    )
    assert (
        agent.client.post(
            "/internal/files/create-file",
            json={"root_path": str(agent.volume), "path": "/plugins/readme.md"},
        ).status_code
        == 200
    )

    assert (agent.volume / "plugins").is_dir()
    assert (agent.volume / "plugins" / "readme.md").read_text() == ""


def test_rename_moves_the_entry(agent):
    (agent.volume / "old.txt").write_text("x")

    response = agent.client.post(
        "/internal/files/rename",
        json={"root_path": str(agent.volume), "source_path": "/old.txt", "target_path": "/new.txt"},
    )

    assert response.status_code == 200
    assert not (agent.volume / "old.txt").exists()
    assert (agent.volume / "new.txt").read_text() == "x"


def test_rename_into_a_missing_directory_is_rejected(agent):
    (agent.volume / "old.txt").write_text("x")

    response = agent.client.post(
        "/internal/files/rename",
        json={"root_path": str(agent.volume), "source_path": "/old.txt", "target_path": "/nope/new.txt"},
    )

    assert response.status_code == 400
    assert response.json()["details"] == "The target parent directory does not exist"


def test_copy_places_a_file_in_the_destination_directory(agent):
    (agent.volume / "a.txt").write_text("x")
    (agent.volume / "backup").mkdir()

    response = agent.client.post(
        "/internal/files/copy",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "destination_path": "/backup"},
    )

    assert response.status_code == 200
    assert (agent.volume / "backup" / "a.txt").read_text() == "x"


def test_copy_into_the_same_directory_is_rejected(agent):
    (agent.volume / "a.txt").write_text("x")

    response = agent.client.post(
        "/internal/files/copy",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "destination_path": "/"},
    )

    assert response.status_code == 400
    assert response.json()["details"] == "The selected item is already in this directory"


def test_copy_refuses_to_overwrite_an_existing_entry(agent):
    (agent.volume / "a.txt").write_text("x")
    (agent.volume / "backup").mkdir()
    (agent.volume / "backup" / "a.txt").write_text("y")

    response = agent.client.post(
        "/internal/files/copy",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "destination_path": "/backup"},
    )

    assert response.status_code == 400
    assert "same name already exists" in response.json()["details"]


def test_a_directory_cannot_be_copied_into_itself(agent):
    (agent.volume / "parent").mkdir()
    (agent.volume / "parent" / "child").mkdir()

    response = agent.client.post(
        "/internal/files/copy",
        json={"root_path": str(agent.volume), "source_path": "/parent", "destination_path": "/parent/child"},
    )

    assert response.status_code == 400
    assert response.json()["details"] == "A directory cannot be copied into itself"


def test_move_relocates_a_directory(agent):
    (agent.volume / "src").mkdir()
    (agent.volume / "src" / "a.txt").write_text("x")
    (agent.volume / "dst").mkdir()

    response = agent.client.post(
        "/internal/files/move",
        json={"root_path": str(agent.volume), "source_path": "/src", "destination_path": "/dst"},
    )

    assert response.status_code == 200
    assert (agent.volume / "dst" / "src" / "a.txt").read_text() == "x"


def test_a_directory_cannot_be_moved_into_itself(agent):
    (agent.volume / "parent").mkdir()
    (agent.volume / "parent" / "child").mkdir()

    response = agent.client.post(
        "/internal/files/move",
        json={"root_path": str(agent.volume), "source_path": "/parent", "destination_path": "/parent/child"},
    )

    assert response.status_code == 400
    assert response.json()["details"] == "A directory cannot be moved into itself"


# ── attributes ────────────────────────────────────────────────────────────


def test_permission_bits_are_applied(agent):
    target = agent.volume / "run.sh"
    target.write_text("#!/bin/sh\n")

    response = agent.client.put(
        "/internal/files/attributes",
        json={
            "root_path": str(agent.volume),
            "source_path": "/run.sh",
            "owner_permissions": {"read": True, "write": True},
            "group_permissions": {"read": True},
            "other_permissions": {},
        },
    )

    assert response.status_code == 200
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert response.json()["mode"] == "-rw-r-----"


def test_attributes_can_rename_the_entry(agent):
    (agent.volume / "old.txt").write_text("x")

    response = agent.client.put(
        "/internal/files/attributes",
        json={"root_path": str(agent.volume), "source_path": "/old.txt", "target_name": "renamed.txt"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "renamed.txt"
    assert (agent.volume / "renamed.txt").exists()


def test_attributes_reject_a_name_collision(agent):
    (agent.volume / "a.txt").write_text("x")
    (agent.volume / "b.txt").write_text("y")

    response = agent.client.put(
        "/internal/files/attributes",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "target_name": "b.txt"},
    )

    assert response.status_code == 400
    assert "same name already exists" in response.json()["details"]


def test_unknown_owners_are_rejected(agent):
    (agent.volume / "a.txt").write_text("x")

    response = agent.client.put(
        "/internal/files/attributes",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "owner": "no-such-user-here"},
    )

    assert response.status_code == 400
    assert "Unknown owner" in response.json()["details"]


def test_numeric_owners_are_passed_through(agent):
    (agent.volume / "a.txt").write_text("x")
    current_uid = os.stat(agent.volume / "a.txt").st_uid

    response = agent.client.put(
        "/internal/files/attributes",
        json={"root_path": str(agent.volume), "source_path": "/a.txt", "owner": str(current_uid)},
    )

    # 传自己的 uid 应当成功(非 root 下 chown 到相同 uid 是允许的)
    assert response.status_code == 200


# ── delete ────────────────────────────────────────────────────────────────


def test_delete_removes_files_and_directories(agent):
    (agent.volume / "a.txt").write_text("x")
    (agent.volume / "tree").mkdir()
    (agent.volume / "tree" / "b.txt").write_text("y")

    assert (
        agent.client.request(
            "DELETE", "/internal/files/path", json={"root_path": str(agent.volume), "path": "/a.txt"}
        ).status_code
        == 200
    )
    assert (
        agent.client.request(
            "DELETE", "/internal/files/path", json={"root_path": str(agent.volume), "path": "/tree"}
        ).status_code
        == 200
    )

    assert not (agent.volume / "a.txt").exists()
    assert not (agent.volume / "tree").exists()


def test_the_volume_root_cannot_be_deleted(agent):
    response = agent.client.request("DELETE", "/internal/files/path", json={"root_path": str(agent.volume), "path": "/"})

    assert response.status_code == 400
    assert response.json()["details"] == "The volume root is not a valid target for this operation"


# ── upload and download ───────────────────────────────────────────────────


def test_upload_decodes_base64_into_the_parent_directory(agent):
    response = agent.client.post(
        "/internal/files/upload",
        json={
            "root_path": str(agent.volume),
            "parent_path": "/",
            "file_name": "logo.bin",
            "content_base64": base64.b64encode(b"\x00\x01\x02").decode(),
        },
    )

    assert response.status_code == 200
    assert (agent.volume / "logo.bin").read_bytes() == b"\x00\x01\x02"


def test_upload_rejects_invalid_base64(agent):
    response = agent.client.post(
        "/internal/files/upload",
        json={
            "root_path": str(agent.volume),
            "parent_path": "/",
            "file_name": "logo.bin",
            "content_base64": "not base64!!",
        },
    )

    assert response.status_code == 400
    assert "valid base64" in response.json()["details"]


def test_upload_rejects_a_name_with_a_separator(agent):
    response = agent.client.post(
        "/internal/files/upload",
        json={
            "root_path": str(agent.volume),
            "parent_path": "/",
            "file_name": "../evil.sh",
            "content_base64": base64.b64encode(b"x").decode(),
        },
    )

    assert response.status_code == 400
    assert "path separators" in response.json()["details"]


def test_download_returns_the_raw_bytes(agent):
    (agent.volume / "dump.sql").write_bytes(b"-- sql\n")

    response = agent.client.post("/internal/files/download", json={"root_path": str(agent.volume), "path": "/dump.sql"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == b"-- sql\n"


def test_download_only_accepts_files(agent):
    (agent.volume / "dir").mkdir()

    response = agent.client.post("/internal/files/download", json={"root_path": str(agent.volume), "path": "/dir"})

    assert response.status_code == 400
    assert response.json()["details"] == "Only file downloads are supported"


# ── docker-helper branch ──────────────────────────────────────────────────


def test_a_root_that_only_exists_in_docker_is_served_by_the_helper(agent, monkeypatch):
    helper = FakeHelperManager({"items": [], "metadata": {}})
    monkeypatch.setattr(files_agent, "_helper_manager", lambda: helper)
    root = str(agent.volume / "missing-volume")

    response = agent.client.post("/internal/files/directory", json={"root_path": root, "path": "/sub"})

    assert response.status_code == 200
    assert helper.calls == [
        {"root": root, "action": "directory", "payload": {"root_path": root, "path": "/sub", "display_name": ""}}
    ]


def test_helper_failures_keep_their_status_code(agent, monkeypatch):
    class FailingHelper(FakeHelperManager):
        def execute(self, root_path, action, payload):
            raise files_agent.CustomException(404, "File Not Found", "gone inside the volume")

    monkeypatch.setattr(files_agent, "_helper_manager", lambda: FailingHelper())

    response = agent.client.post(
        "/internal/files/metadata", json={"root_path": str(agent.volume / "missing-volume"), "path": "/a.txt"}
    )

    assert response.status_code == 404
    assert response.json()["details"] == "gone inside the volume"


def test_helper_downloads_are_decoded_back_to_bytes(agent, monkeypatch):
    payload = base64.b64encode(b"\x89PNG").decode()
    monkeypatch.setattr(files_agent, "_helper_manager", lambda: FakeHelperManager({"content_base64": payload}))

    response = agent.client.post(
        "/internal/files/download",
        json={"root_path": str(agent.volume / "missing-volume"), "path": "/logo.png"},
    )

    assert response.status_code == 200
    assert response.content == b"\x89PNG"


# ── every action can be delegated to the helper ──────────────────────────


@pytest.mark.parametrize(
    ("method", "url", "action", "payload"),
    [
        ("PUT", "/internal/files/write-text", "write-text", {"path": "/a.txt", "content": "x"}),
        ("POST", "/internal/files/create-directory", "create-directory", {"path": "/dir"}),
        ("POST", "/internal/files/create-file", "create-file", {"path": "/a.txt"}),
        (
            "POST",
            "/internal/files/rename",
            "rename",
            {"source_path": "/a.txt", "target_path": "/b.txt"},
        ),
        (
            "POST",
            "/internal/files/copy",
            "copy",
            {"source_path": "/a.txt", "destination_path": "/dir"},
        ),
        (
            "POST",
            "/internal/files/move",
            "move",
            {"source_path": "/a.txt", "destination_path": "/dir"},
        ),
        ("PUT", "/internal/files/attributes", "attributes", {"source_path": "/a.txt"}),
        ("DELETE", "/internal/files/path", "delete", {"path": "/a.txt"}),
        (
            "POST",
            "/internal/files/upload",
            "upload",
            {"parent_path": "/", "file_name": "a.bin", "content_base64": "eA=="},
        ),
        ("POST", "/internal/files/metadata", "metadata", {"path": "/a.txt"}),
        ("POST", "/internal/files/read-text", "read-text", {"path": "/a.txt"}),
    ],
)
def test_actions_are_delegated_when_the_root_lives_in_docker(agent, monkeypatch, method, url, action, payload):
    helper = FakeHelperManager({"status": "ok"})
    monkeypatch.setattr(files_agent, "_helper_manager", lambda: helper)
    root = str(agent.volume / "missing-volume")

    response = agent.client.request(method, url, json={"root_path": root, **payload})

    assert response.status_code == 200, response.text
    assert helper.calls[0]["action"] == action
    assert helper.calls[0]["root"] == root
    # 原始请求体(含 root_path)原样转给 helper
    assert helper.calls[0]["payload"]["root_path"] == root
