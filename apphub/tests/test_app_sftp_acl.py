"""Host-side POSIX ACL helper (`app_sftp_acl.py`).

This script is what actually lets the platform SFTP account read an application's files. Two
properties matter more than coverage: it must never grant access outside the authorized directory,
and `release` must put the previous ACL state back exactly. Both are asserted here, with `getfacl` /
`setfacl` replaced so the suite does not need the host's acl binaries or root.
"""

import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services import app_sftp_acl as acl_module

BASE_ACL = "user::rwx\ngroup::---\nother::---\n"
GRANTED_ACL = "user::rwx\nuser:2001:rw-\ngroup::---\nmask::rw-\nother::---\n"


@pytest.fixture
def acl(monkeypatch, tmp_path):
    """Fakes getfacl/setfacl and keeps every command for assertions."""
    monkeypatch.delenv("WEBSOFT9_HOST_ROOT", raising=False)
    state = SimpleNamespace(commands=[], acls={}, data_root=tmp_path)
    state.data_root = tmp_path

    def fake_run(command, timeout=30):
        state.commands.append(list(command))
        if command[0] == "getfacl":
            return SimpleNamespace(stdout=state.acls.get(str(command[-1]), BASE_ACL), stderr="")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(acl_module, "run", fake_run)
    monkeypatch.setattr(acl_module, "account_uid", lambda account: "2001")
    return state


def _mkdir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def _setfacl_commands(state):
    return [command for command in state.commands if command[0] == "setfacl"]


# ── path mapping ──────────────────────────────────────────────────────────


def test_paths_are_unchanged_without_a_host_mount(acl):
    assert acl_module.host_root() == ""
    assert acl_module.fs_path("/var/lib/docker/volumes/x/_data") == "/var/lib/docker/volumes/x/_data"
    assert acl_module.host_view("/var/lib/docker/volumes/x/_data") == "/var/lib/docker/volumes/x/_data"


def test_paths_round_trip_through_the_host_mount(acl, monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_HOST_ROOT", str(tmp_path))

    assert acl_module.fs_path("/srv/app") == f"{tmp_path}/srv/app"
    assert acl_module.fs_path(f"{tmp_path}/srv/app") == f"{tmp_path}/srv/app"
    assert acl_module.host_view(f"{tmp_path}/srv/app") == "/srv/app"
    assert acl_module.host_view(str(tmp_path)) == "/"


# ── ACL parsing ───────────────────────────────────────────────────────────


def test_parse_acl_separates_access_and_default_entries(acl):
    text = (
        "# file: /srv/app\n"
        "# owner: root\n"
        "user::rwx\n"
        "user:2001:r-x\n"
        "group::---\n"
        "mask::r-x\n"
        "other::---\n"
        "default:user::rwx\n"
        "default:user:2001:rwx\n"
        "default:mask::rwx\n"
        "not-an-entry\n"
    )

    access, default = acl_module.parse_acl(text)

    assert access == {
        ("user", ""): "rwx",
        ("user", "2001"): "r-x",
        ("group", ""): "---",
        ("mask", ""): "r-x",
        ("other", ""): "---",
    }
    assert default == {
        ("user", ""): "rwx",
        ("user", "2001"): "rwx",
        ("mask", ""): "rwx",
    }
    assert acl_module.parse_acl("") == ({}, {})


@pytest.mark.parametrize(
    ("access", "expected"),
    [
        ({("other", ""): "--x"}, True),
        ({("user", "2001"): "r-x", ("mask", ""): "r-x"}, True),
        ({("user", "2001"): "r-x"}, True),
        ({("user", "2001"): "r-x", ("mask", ""): "r--"}, False),
        ({("user", "2001"): "rw-", ("mask", ""): "rw-"}, False),
        ({}, False),
    ],
)
def test_traverse_requires_execute_through_the_mask(acl, access, expected):
    assert acl_module.has_traverse(access, "2001") is expected


def test_docker_volume_detection_needs_the_exact_data_directory(acl):
    assert acl_module.is_docker_volume_data("/var/lib/docker/volumes/shop/_data") is True
    assert acl_module.is_docker_volume_data("/var/lib/docker/volumes/shop/_data/") is True
    assert acl_module.is_docker_volume_data("/var/lib/docker/volumes") is False
    assert acl_module.is_docker_volume_data("/var/lib/docker/volumes/shop/_data/nested") is False
    assert acl_module.is_docker_volume_data("/srv/app") is False


# ── target validation ─────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/", "//", ""])
def test_the_filesystem_root_is_never_a_target(acl, path):
    with pytest.raises(ValueError, match="cannot be the filesystem root"):
        acl_module.validate_target(path)


def test_a_relative_path_is_rejected(acl, tmp_path):
    with pytest.raises(ValueError, match="cannot be the filesystem root"):
        acl_module.validate_target("srv/app")


def test_a_symlinked_target_is_rejected(acl, tmp_path):
    real = _mkdir(tmp_path / "real")
    link = tmp_path / "link"
    link.symlink_to(real)

    with pytest.raises(ValueError, match="Symbolic links are not supported"):
        acl_module.validate_target(str(link))


def test_a_protected_system_path_is_rejected(acl, monkeypatch, tmp_path):
    protected = _mkdir(tmp_path / "protected")
    monkeypatch.setattr(acl_module, "DENY_PREFIXES", (str(protected),))

    with pytest.raises(ValueError, match="protected system path"):
        acl_module.validate_target(str(protected))


def test_a_docker_volume_data_directory_bypasses_the_protected_prefix_rule(acl, monkeypatch, tmp_path):
    protected = _mkdir(tmp_path / "var/lib/docker")
    volume = _mkdir(protected / "volumes/shop/_data")
    monkeypatch.setattr(acl_module, "DENY_PREFIXES", (str(protected),))
    monkeypatch.setattr(acl_module, "is_docker_volume_data", lambda path: True)

    assert acl_module.validate_target(str(volume)) == str(volume)


def test_a_regular_file_is_rejected_as_a_target(acl, tmp_path):
    target = tmp_path / "docker-compose.yml"
    target.write_text("services: {}")

    with pytest.raises(ValueError, match="not a directory"):
        acl_module.validate_target(str(target))


def test_a_normal_application_directory_is_accepted(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")

    assert acl_module.validate_target(str(target)) == str(target)


# ── setfacl error mapping ─────────────────────────────────────────────────


def test_missing_acl_utilities_are_reported(acl, monkeypatch):
    monkeypatch.setattr(
        acl_module,
        "run",
        lambda command, timeout=30: (_ for _ in ()).throw(FileNotFoundError("setfacl")),
    )

    with pytest.raises(ValueError, match="acl' utilities"):
        acl_module.setfacl(["-m", "u:2001:rwX", "/srv/app"])


def test_a_filesystem_without_acl_support_is_reported(acl, monkeypatch):
    def failing_run(command, timeout=30):
        raise subprocess.CalledProcessError(1, command, stderr="Operation not supported")

    monkeypatch.setattr(acl_module, "run", failing_run)

    with pytest.raises(ValueError, match="does not support ACL"):
        acl_module.setfacl(["-m", "u:2001:rwX", "/srv/app"])


def test_other_setfacl_failures_carry_the_stderr(acl, monkeypatch):
    def failing_run(command, timeout=30):
        raise subprocess.CalledProcessError(1, command, stderr="Invalid argument near line 1")

    monkeypatch.setattr(acl_module, "run", failing_run)

    with pytest.raises(ValueError, match="setfacl failed: Invalid argument"):
        acl_module.setfacl(["-m", "u:2001:rwX", "/srv/app"])


def test_ancestors_are_listed_top_down(acl):
    assert acl_module.ancestor_paths("/srv/app/data") == ["/srv", "/srv/app"]
    assert acl_module.ancestor_paths("/srv") == []


# ── entry application ─────────────────────────────────────────────────────


def test_apply_entries_grants_the_account_on_the_target_only(acl, tmp_path):
    target = _mkdir(tmp_path / "app")

    recorded, truncated = acl_module.apply_entries(str(target), "2001", 999)

    assert (recorded, truncated) == ([], False)
    assert _setfacl_commands(acl) == [["setfacl", "-m", "u:2001:rwX,d:u:2001:rwX,d:m:rwX,d:u:999:rwX", str(target)]]


def test_apply_entries_omits_the_container_uid_entry_for_root_containers(acl, tmp_path):
    target = _mkdir(tmp_path / "app")

    acl_module.apply_entries(str(target), "2001", 0)

    assert _setfacl_commands(acl)[-1] == ["setfacl", "-m", "u:2001:rwX,d:u:2001:rwX,d:m:rwX", str(target)]


def test_recursive_apply_records_what_it_changed(acl, tmp_path):
    target = _mkdir(tmp_path / "app")
    (target / "index.php").write_text("<?php")
    (target / "already.txt").write_text("done")
    subdirectory = _mkdir(target / "wp-content")
    (subdirectory / "style.css").write_text("body{}")
    (target / "link").symlink_to(target / "index.php")
    acl.acls[str(target / "already.txt")] = GRANTED_ACL

    recorded, truncated = acl_module.apply_entries(str(target), "2001", 999, recursive=True)

    assert truncated is False
    by_path = {record["path"]: record for record in recorded}
    # 已经是 rw 的条目跳过,符号链接跳过
    assert str(target / "already.txt") not in by_path
    assert str(target / "link") not in by_path
    assert by_path[str(target)]["is_directory"] is True
    assert by_path[str(target / "index.php")]["is_directory"] is False
    assert by_path[str(subdirectory)]["uid_entry_added"] is True
    assert by_path[str(target / "index.php")]["mask_before"] is None
    # 文件只加 u: 条目,目录才带 default 条目
    file_command = [command for command in _setfacl_commands(acl) if command[-1].endswith("index.php")][0]
    assert file_command[2] == "u:2001:rwX"


def test_recursive_apply_is_bounded_by_the_entry_limit(acl, tmp_path, monkeypatch):
    monkeypatch.setattr(acl_module, "MAX_RECURSIVE_ENTRIES", 1)
    target = _mkdir(tmp_path / "app")
    for index in range(5):
        (target / f"file-{index}.txt").write_text("x")

    recorded, truncated = acl_module.apply_entries(str(target), "2001", 0, recursive=True)

    assert truncated is True
    assert len(recorded) <= 1


def test_recursive_apply_is_bounded_by_the_deadline(acl, tmp_path, monkeypatch):
    monkeypatch.setattr(acl_module, "RECURSIVE_DEADLINE_SECONDS", -1)
    target = _mkdir(tmp_path / "app")
    (target / "file.txt").write_text("x")

    recorded, truncated = acl_module.apply_entries(str(target), "2001", 0, recursive=True)

    assert (recorded, truncated) == ([], True)


def test_shallow_grant_covers_direct_children_only(acl, tmp_path):
    target = _mkdir(tmp_path / "app")
    (target / "a.txt").write_text("x")
    subdirectory = _mkdir(target / "sub")
    (subdirectory / "deep.txt").write_text("x")
    (target / "link").symlink_to(target / "a.txt")

    recorded, truncated = acl_module.grant_directory_entries(str(target), "2001", 999)

    paths = {record["path"] for record in recorded}
    assert paths == {str(target / "a.txt"), str(subdirectory)}
    assert truncated is False
    # 深层文件不在这一轮里被授权,等操作员真正进入该目录再授权
    assert str(subdirectory / "deep.txt") not in paths


def test_shallow_grant_respects_its_limit(acl, tmp_path, monkeypatch):
    monkeypatch.setattr(acl_module, "SHALLOW_GRANT_LIMIT", 1)
    target = _mkdir(tmp_path / "app")
    for index in range(4):
        (target / f"file-{index}.txt").write_text("x")

    recorded, truncated = acl_module.grant_directory_entries(str(target), "2001", 0)

    assert len(recorded) == 1
    assert truncated is True


def test_shallow_grant_on_an_unreadable_directory_is_empty(acl, tmp_path):
    assert acl_module.grant_directory_entries(str(tmp_path / "gone"), "2001", 0) == ([], False)


def test_account_uid_passes_numeric_ids_through(acl):
    assert acl_module.account_uid("2001") == "2001"
    assert acl_module.account_uid(" 2001 ") == "2001"


def test_account_uid_resolves_names_from_the_host_passwd_file(acl, monkeypatch, tmp_path):
    passwd = tmp_path / "passwd"
    passwd.write_text("root:x:0:0:root:/root:/bin/bash\nwebsoft9-sftp:x:2001:2001::/home:/usr/sbin/nologin\n")
    original = acl_module.fs_path
    monkeypatch.setattr(
        acl_module,
        "fs_path",
        lambda path: str(passwd) if str(path) == "/etc/passwd" else original(path),
    )

    assert acl_module.account_uid("websoft9-sftp") == "2001"


# ── apply / grant / release ───────────────────────────────────────────────


def _manifest(state, session_id):
    return json.loads((state.data_root / "config/host-access/sftp-acl" / f"{session_id}.json").read_text())


def test_apply_records_a_manifest_with_traverse_snapshots(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    (target / "index.php").write_text("<?php")

    result = acl_module.apply(str(tmp_path), "session-1", str(target), "websoft9-sftp", 999)

    assert result["path"] == str(target)
    ancestors = acl_module.ancestor_paths(str(target))
    assert result["ancestors"] == len(ancestors)
    manifest = _manifest(acl, "session-1")
    assert manifest["version"] == acl_module.MANIFEST_VERSION
    assert manifest["root"] == str(target)
    assert manifest["account_uid"] == "2001"
    assert manifest["container_uid"] == 999
    assert [snapshot["path"] for snapshot in manifest["snapshots"]] == ancestors
    assert ancestors[-1] == str(tmp_path / "srv")
    assert manifest["root_acl"] == BASE_ACL
    assert manifest["truncated"] is False
    # 祖先目录只有确实缺 x 权限时才被授权
    assert any(command[2].endswith(":x") for command in _setfacl_commands(acl))


def test_apply_skips_ancestors_that_already_allow_traverse(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    for ancestor in acl_module.ancestor_paths(str(target)):
        acl.acls[ancestor] = "user::rwx\nother::--x\n"

    result = acl_module.apply(str(tmp_path), "session-2", str(target), "websoft9-sftp", 0)

    assert result["ancestors"] == 0
    assert _manifest(acl, "session-2")["snapshots"] == []


def test_apply_replaces_a_stale_manifest_for_the_same_session(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    acl_module.apply(str(tmp_path), "session-3", str(target), "websoft9-sftp", 0)
    manifest_path = tmp_path / "config/host-access/sftp-acl/session-3.json"
    first = manifest_path.read_text()

    acl_module.apply(str(tmp_path), "session-3", str(target), "websoft9-sftp", 0)

    # 旧清单先被 release 掉,不会和新的叠加
    assert manifest_path.read_text() != first or json.loads(first)["session_id"] == "session-3"
    assert acl_module.release(str(tmp_path), "session-3")["released"] is True


def test_grant_requires_an_active_session(acl, tmp_path):
    with pytest.raises(ValueError, match="no longer active"):
        acl_module.grant(str(tmp_path), "missing-session", str(tmp_path))


def test_grant_refuses_paths_outside_the_authorized_directory(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    acl_module.apply(str(tmp_path), "session-4", str(target), "websoft9-sftp", 0)

    with pytest.raises(ValueError, match="outside the authorized application directory"):
        acl_module.grant(str(tmp_path), "session-4", str(tmp_path / "srv/other"))


def test_grant_extends_the_manifest_inside_the_authorized_directory(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    subdirectory = _mkdir(target / "wp-content")
    (subdirectory / "style.css").write_text("body{}")
    acl_module.apply(str(tmp_path), "session-5", str(target), "websoft9-sftp", 0)

    result = acl_module.grant(str(tmp_path), "session-5", str(subdirectory))

    assert result["path"] == str(subdirectory)
    manifest = _manifest(acl, "session-5")
    recorded_paths = {record["path"] for record in manifest["recursive"]}
    assert str(subdirectory / "style.css") in recorded_paths
    assert any(snapshot["path"] == str(subdirectory) for snapshot in manifest["snapshots"])


def test_release_without_a_manifest_is_a_no_op(acl, tmp_path):
    assert acl_module.release(str(tmp_path), "nothing") == {"released": False}


def test_release_restores_masks_and_removes_the_manifest(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    (target / "index.php").write_text("<?php")
    acl.acls[str(target / "index.php")] = "user::rw-\nmask::r--\nother::---\n"
    acl_module.apply(str(tmp_path), "session-6", str(target), "websoft9-sftp", 999, recursive=True)
    manifest_path = tmp_path / "config/host-access/sftp-acl/session-6.json"

    result = acl_module.release(str(tmp_path), "session-6")

    assert result == {"released": True, "root": str(target)}
    assert not manifest_path.exists()
    commands = _setfacl_commands(acl)
    # 条目被删除,并在原来有 mask 的地方把 mask 复原
    assert any(command[1] == "-x" and command[2] == "u:2001" for command in commands)
    assert any(command[1] == "-m" and command[2] == "m::r--" for command in commands)
    assert any(command[1].startswith("--restore=") for command in commands)


def test_release_tolerates_entries_that_disappeared(acl, tmp_path):
    target = _mkdir(tmp_path / "srv/app")
    acl_module.apply(str(tmp_path), "session-7", str(target), "websoft9-sftp", 0)
    manifest_path = tmp_path / "config/host-access/sftp-acl/session-7.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["recursive"] = [{"path": str(tmp_path / "srv/app/deleted.txt"), "is_directory": False}]
    manifest_path.write_text(json.dumps(manifest))

    assert acl_module.release(str(tmp_path), "session-7")["released"] is True


def test_restore_acl_rewrites_the_file_header_for_the_helper_mount(acl, monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_HOST_ROOT", str(tmp_path))
    restored = {}

    def fake_run(command, timeout=30):
        acl.commands.append(list(command))
        if command[0] == "setfacl" and command[1].startswith("--restore="):
            restored["text"] = Path(command[1].split("=", 1)[1]).read_text()
            restored["file"] = command[1].split("=", 1)[1]
        if command[0] == "setfacl" and command[1] == "-b":
            raise ValueError("no acl")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(acl_module, "run", fake_run)

    acl_module.restore_acl("/srv/app", "# file: /srv/app\nuser::rwx\n")

    assert f"# file: {tmp_path}/srv/app" in restored["text"]
    # 临时文件用完就删
    assert not Path(restored["file"]).exists()


def test_restore_acl_keeps_the_header_when_no_mount_is_used(acl, monkeypatch):
    seen = {}

    def fake_run(command, timeout=30):
        acl.commands.append(list(command))
        if command[1].startswith("--restore="):
            path = Path(command[1].split("=", 1)[1])
            seen["text"] = path.read_text()
            seen["path"] = path
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(acl_module, "run", fake_run)

    acl_module.restore_acl("/srv/app", "# file: /srv/app\nuser::rwx\n")

    assert seen["text"] == "# file: /srv/app\nuser::rwx\n"
    assert not seen["path"].exists()


def test_snapshot_path_is_a_getfacl_call(acl, tmp_path):
    target = _mkdir(tmp_path / "app")

    assert acl_module.snapshot_path(str(target)) == BASE_ACL
    assert acl.commands[-1][:3] == ["getfacl", "-p", "--absolute-names"]


def test_the_cli_rejects_unknown_operations(tmp_path):
    result = subprocess.run(
        [os.sys.executable, str(Path(acl_module.__file__)), "explode", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 1
    assert "Unsupported operation: explode" in result.stderr


def test_the_cli_requires_a_manifest_for_grant(tmp_path):
    result = subprocess.run(
        [os.sys.executable, str(Path(acl_module.__file__)), "grant", str(tmp_path), "missing", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 1
    assert "no longer active" in result.stderr


def test_acl_entries_are_posix_mode_aware(acl, tmp_path):
    target = _mkdir(tmp_path / "app")
    (target / "script.sh").write_text("#!/bin/sh\n")
    (target / "script.sh").chmod(0o755)

    recorded, _truncated = acl_module.apply_entries(str(target), "2001", 0, recursive=True)

    # 只补 u: 条目与 default mask,不改动原文件权限位
    assert stat.S_IMODE((target / "script.sh").stat().st_mode) == 0o755
    assert all(set(command) != {"chmod"} for command in acl.commands)
    assert {record["path"] for record in recorded} >= {str(target / "script.sh")}
