"""Host-side bootstrap for the platform SFTP account (`app_sftp_prepare.py`).

This script runs as root inside a privileged helper container, so the interesting cases are the ones
where it must refuse to act: an account that already exists with a login shell, a home directory
somewhere else, or a privileged group. Those messages are asserted verbatim because
`AppSftpAccountService` classifies a 409 "account conflict" purely by matching their wording - if the
wording drifts, a real conflict silently degrades into a generic failure.

Everything that touches the host (`useradd`, `ssh-keygen`, `sshd -t`, `systemctl`, `chown`) is
replaced, so the suite never needs root or a real sshd.
"""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services import app_sftp_prepare as prepare

REAL_PATH = Path


class FakeAccount:
    def __init__(self, name, uid=2001, gid=2001, home=None, shell="/usr/sbin/nologin"):
        self.pw_name = name
        self.pw_uid = uid
        self.pw_gid = gid
        self.pw_dir = str(home if home is not None else prepare.ACCOUNT_HOME)
        self.pw_shell = shell


@pytest.fixture
def host(monkeypatch, tmp_path):
    """Redirects every host path into tmp_path and fakes the privileged commands."""
    state = SimpleNamespace(
        accounts={},
        commands=[],
        chowns=[],
        euid=0,
        sshd_rejects=False,
        reject_preferred_uid=False,
        public_key=f"ssh-rsa AAAAB3NZA {prepare.KEY_COMMENT}",
        generation_error=None,
    )

    account_home = tmp_path / "var/lib/websoft9-sftp"
    ssh_dir = tmp_path / "etc/ssh"
    ssh_dir.mkdir(parents=True)
    monkeypatch.setattr(prepare, "ACCOUNT_HOME", account_home)
    monkeypatch.setattr(prepare, "SSHD_CONFIG", ssh_dir / "sshd_config")
    monkeypatch.setattr(prepare, "SSHD_DROPIN_DIR", ssh_dir / "sshd_config.d")
    monkeypatch.setattr(prepare, "SSHD_DROPIN", ssh_dir / "sshd_config.d" / "60-websoft9-sftp.conf")
    monkeypatch.setattr(prepare, "Path", lambda value: REAL_PATH(value))
    monkeypatch.setattr(prepare, "pwd", SimpleNamespace(getpwnam=lambda name: state.accounts[name]))
    monkeypatch.setattr(prepare.os, "geteuid", lambda: state.euid)
    monkeypatch.setattr(prepare.os, "chown", lambda path, uid, gid: state.chowns.append((str(path), uid, gid)))
    monkeypatch.setattr(prepare.os, "fchown", lambda fd, uid, gid: state.chowns.append((fd, uid, gid)))

    def fake_run(command, timeout=30):
        state.commands.append(list(command))
        if state.generation_error and command[0] == "ssh-keygen":
            raise state.generation_error
        if command[0] == "useradd":
            name = command[-1]
            if state.reject_preferred_uid and "--uid" in command:
                raise subprocess.CalledProcessError(1, command)
            uid = int(command[command.index("--uid") + 1]) if "--uid" in command else 2001
            state.accounts[name] = FakeAccount(
                name,
                uid=uid,
                home=command[command.index("--home-dir") + 1],
                shell=command[command.index("--shell") + 1],
            )
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if command[0] == "ssh-keygen" and command[1] == "-y":
            return SimpleNamespace(stdout=state.public_key + "\n", stderr="", returncode=0)
        if command[0] == "ssh-keygen":
            target = REAL_PATH(command[command.index("-f") + 1])
            target.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n")
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if command[0].endswith("sshd") and state.sshd_rejects:
            raise subprocess.CalledProcessError(255, command, stderr="bad configuration")
        if command[0] == "systemctl":
            return SimpleNamespace(stdout="ssh.service enabled", stderr="", returncode=0)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(prepare, "run", fake_run)
    monkeypatch.setattr(prepare, "reload_sshd", lambda: state.commands.append(["reload_sshd"]))

    state.tmp_path = tmp_path
    state.ssh_dir = ssh_dir
    return state


def _write_sshd_config(host, content):
    host.ssh_dir.joinpath("sshd_config").write_text(content)


# ── account compliance ────────────────────────────────────────────────────


def test_account_compliance_accepts_a_nologin_account_in_the_platform_home(host, monkeypatch):
    monkeypatch.setattr(prepare, "account_groups", lambda name: {"websoft9-sftp"})

    assert prepare.account_complies(FakeAccount("websoft9-sftp")) is True


@pytest.mark.parametrize("shell", ["/bin/bash", "/bin/sh", "/usr/bin/zsh"])
def test_account_compliance_rejects_any_login_shell(host, monkeypatch, shell):
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())

    assert prepare.account_complies(FakeAccount("websoft9-sftp", shell=shell)) is False


def test_account_compliance_rejects_a_foreign_home_directory(host, monkeypatch):
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())

    assert prepare.account_complies(FakeAccount("websoft9-sftp", home="/root")) is False


@pytest.mark.parametrize("group", sorted(prepare.FORBIDDEN_GROUPS))
def test_account_compliance_rejects_privileged_groups(host, monkeypatch, group):
    monkeypatch.setattr(prepare, "account_groups", lambda name: {group})

    assert prepare.account_complies(FakeAccount("websoft9-sftp")) is False


# ── name selection and creation ───────────────────────────────────────────


def test_the_reserved_name_is_used_when_no_account_exists(host):
    assert prepare.choose_account_name() == prepare.ACCOUNT


def test_a_compliant_existing_account_keeps_the_reserved_name(host, monkeypatch):
    host.accounts[prepare.ACCOUNT] = FakeAccount(prepare.ACCOUNT)
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())

    assert prepare.choose_account_name() == prepare.ACCOUNT


def test_a_foreign_owner_of_the_reserved_name_is_never_reused(host, monkeypatch):
    host.accounts[prepare.ACCOUNT] = FakeAccount(prepare.ACCOUNT, shell="/bin/bash")
    monkeypatch.setattr(prepare, "account_groups", lambda name: {"sudo"})

    chosen = prepare.choose_account_name()

    assert chosen != prepare.ACCOUNT
    assert chosen.startswith("websoft9-")
    assert len(chosen) == len("websoft9-") + 4


def test_name_allocator_gives_up_when_every_candidate_is_taken(host, monkeypatch):
    host.accounts[prepare.ACCOUNT] = FakeAccount(prepare.ACCOUNT, home="/root")
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())
    monkeypatch.setattr(prepare.secrets, "choice", lambda alphabet: "a")
    # 20 次尝试全部撞名
    host.accounts["websoft9-aaaa"] = FakeAccount("websoft9-aaaa")

    with pytest.raises(ValueError, match="Unable to allocate"):
        prepare.choose_account_name()


def test_ensure_account_creates_the_account_with_the_preferred_uid(host, monkeypatch):
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())

    account = prepare.ensure_account()

    assert account.pw_name == prepare.ACCOUNT
    created = [command for command in host.commands if command[0] == "useradd"][0]
    assert "--uid" in created and "2001" in created
    assert created[created.index("--shell") + 1] == "/usr/sbin/nologin"
    # 家目录被收紧到 0700 并交给该账号
    assert prepare.ACCOUNT_HOME.stat().st_mode & 0o777 == 0o700
    assert (str(prepare.ACCOUNT_HOME), account.pw_uid) in [(path, uid) for path, uid, _ in host.chowns]


def test_ensure_account_retries_without_the_preferred_uid(host, monkeypatch):
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())
    host.reject_preferred_uid = True

    account = prepare.ensure_account()

    useradd_calls = [command for command in host.commands if command[0] == "useradd"]
    assert len(useradd_calls) == 2
    assert "--uid" in useradd_calls[0]
    assert "--uid" not in useradd_calls[1]
    assert account.pw_name == prepare.ACCOUNT


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        (FakeAccount("websoft9-sftp", shell="/bin/bash"), "refusing to use it"),
        (FakeAccount("websoft9-sftp", home="/root"), "unexpected home directory"),
    ],
)
def test_ensure_account_refuses_a_foreign_reserved_account(host, monkeypatch, account, expected):
    host.accounts[prepare.ACCOUNT] = account
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())
    # `choose_account_name` 平时会给同名的非合规账号改个名字，这里直接注入该名字，
    # 覆盖"名字选好之后账号才被第三方改动"的竞态守卫。
    monkeypatch.setattr(prepare, "choose_account_name", lambda: prepare.ACCOUNT)

    with pytest.raises(ValueError) as error:
        prepare.ensure_account()

    # 这些措辞被 AppSftpAccountService 用来判定 409 "SFTP Account Conflict"
    assert expected in str(error.value)


def test_ensure_account_refuses_a_privileged_group_membership(host, monkeypatch):
    host.accounts[prepare.ACCOUNT] = FakeAccount(prepare.ACCOUNT)
    monkeypatch.setattr(prepare, "account_groups", lambda name: {"docker", "root"})
    monkeypatch.setattr(prepare, "choose_account_name", lambda: prepare.ACCOUNT)

    with pytest.raises(ValueError) as error:
        prepare.ensure_account()

    message = str(error.value)
    assert "privileged groups" in message
    assert "docker" in message and "root" in message


def test_account_groups_never_raises_for_unknown_accounts(monkeypatch):
    monkeypatch.setattr(prepare.pwd, "getpwnam", lambda name: (_ for _ in ()).throw(KeyError(name)))

    assert prepare.account_groups("nobody-here") == set()


# ── sshd configuration ────────────────────────────────────────────────────


def test_dropin_support_requires_the_directory_and_an_include(host):
    assert prepare.sshd_supports_dropin("Include /etc/ssh/sshd_config.d/*.conf") is False

    prepare.SSHD_DROPIN_DIR.mkdir(parents=True)
    assert prepare.sshd_supports_dropin("Include /etc/ssh/sshd_config.d/*.conf") is True
    assert prepare.sshd_supports_dropin("#Include /etc/ssh/sshd_config.d/*.conf") is False
    assert prepare.sshd_supports_dropin("Include /etc/ssh/other.conf") is False


def test_install_sshd_config_requires_an_existing_server_configuration(host):
    with pytest.raises(ValueError, match="does not expose an OpenSSH"):
        prepare.install_sshd_config(host.tmp_path)


def test_install_sshd_config_writes_a_dropin_and_is_idempotent(host):
    prepare.SSHD_DROPIN_DIR.mkdir(parents=True)
    _write_sshd_config(host, f"Port 22\nInclude {prepare.SSHD_DROPIN_DIR}/*.conf\n")

    first = prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")

    assert first == {"mode": "dropin", "path": str(prepare.SSHD_DROPIN), "changed": True}
    content = prepare.SSHD_DROPIN.read_text()
    assert "Match User websoft9-sftp" in content
    assert "ForceCommand internal-sftp -u 0002" in content
    assert "PasswordAuthentication no" in content
    assert prepare.SSHD_DROPIN.stat().st_mode & 0o777 == 0o644
    # 主配置在 dropin 模式下不被改写
    assert "websoft9-sftp" not in Path(prepare.SSHD_CONFIG).read_text()

    host.commands.clear()
    second = prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")

    assert second["changed"] is False
    assert ["reload_sshd"] not in host.commands


def test_install_sshd_config_rolls_back_a_rejected_dropin(host):
    prepare.SSHD_DROPIN_DIR.mkdir(parents=True)
    _write_sshd_config(host, "Include /etc/ssh/sshd_config.d/*.conf\n")
    host.sshd_rejects = True

    with pytest.raises(ValueError, match="was rejected"):
        prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")

    assert not prepare.SSHD_DROPIN.exists()


def test_install_sshd_config_edits_the_main_config_when_dropins_are_unsupported(host):
    _write_sshd_config(host, "Port 22\n")

    result = prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")

    assert result["mode"] == "main"
    updated = Path(prepare.SSHD_CONFIG).read_text()
    assert prepare.MARKER_BEGIN in updated and prepare.MARKER_END in updated
    assert "Match User websoft9-sftp" in updated
    # 原内容保留在最前面,便于人工排查
    assert updated.startswith("Port 22\n")
    # 第一次改写前会留下备份
    backup = host.tmp_path / "sshd_config.websoft9.bak"
    assert backup.read_text() == "Port 22\n"
    assert backup.stat().st_mode & 0o777 == 0o600
    assert Path(prepare.SSHD_CONFIG).stat().st_mode & 0o777 == 0o600


def test_install_sshd_config_replaces_an_existing_block_instead_of_appending(host):
    _write_sshd_config(host, "Port 22\n")
    prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")
    first = Path(prepare.SSHD_CONFIG).read_text()

    prepare.install_sshd_config(host.tmp_path, "websoft9-other")
    second = Path(prepare.SSHD_CONFIG).read_text()

    assert second.count(prepare.MARKER_BEGIN) == 1
    assert first.count(prepare.MARKER_BEGIN) == 1
    assert "Match User websoft9-other" in second
    assert "Match User websoft9-sftp" not in second


def test_install_sshd_config_restores_the_main_config_when_rejected(host):
    _write_sshd_config(host, "Port 22\n")
    host.sshd_rejects = True

    with pytest.raises(ValueError, match="was rejected"):
        prepare.install_sshd_config(host.tmp_path, "websoft9-sftp")

    assert Path(prepare.SSHD_CONFIG).read_text() == "Port 22\n"


# ── key material ──────────────────────────────────────────────────────────


def test_write_atomic_replaces_the_target_and_leaves_no_temporary_file(host, tmp_path):
    target = tmp_path / "state.json"

    prepare.write_atomic(target, '{"a": 1}', 0o600)

    assert target.read_text() == '{"a": 1}'
    assert target.stat().st_mode & 0o777 == 0o600
    assert [name for name in tmp_path.iterdir() if name.name != "state.json" and name.is_file()] == []
    # 属主在 rename 之前就设好,避免出现"已可见但权限还没改"的窗口
    assert [uid for _path, uid, _gid in host.chowns] == [0]


def test_ensure_keypair_reuses_an_existing_key_and_tightens_its_mode(host, tmp_path):
    key = tmp_path / "sftp.key"
    key.write_text("existing")
    key.chmod(0o644)

    key_file, public_key = prepare.ensure_keypair(tmp_path)

    assert key_file == key
    assert key.read_text() == "existing"
    assert key.stat().st_mode & 0o777 == 0o600
    assert public_key == f"ssh-rsa AAAAB3NZA {prepare.KEY_COMMENT}"


def test_ensure_keypair_rejects_a_symlinked_key(host, tmp_path):
    real = tmp_path / "real.key"
    real.write_text("secret")
    (tmp_path / "sftp.key").symlink_to(real)

    with pytest.raises(ValueError, match="unsafe"):
        prepare.ensure_keypair(tmp_path)


def test_ensure_keypair_rejects_a_hardlinked_key(host, tmp_path):
    key = tmp_path / "sftp.key"
    key.write_text("secret")
    (tmp_path / "copy.key").hardlink_to(key)

    with pytest.raises(ValueError, match="unsafe"):
        prepare.ensure_keypair(tmp_path)


def test_ensure_keypair_generates_a_new_key(host, tmp_path):
    key_file, _public_key = prepare.ensure_keypair(tmp_path)

    assert key_file.read_text().startswith("-----BEGIN")
    assert key_file.stat().st_mode & 0o777 == 0o600
    generate = [command for command in host.commands if command[0] == "ssh-keygen" and "-b" in command]
    assert generate[0][generate[0].index("-b") + 1] == "3072"
    assert generate[0][generate[0].index("-N") + 1] == ""


def test_ensure_keypair_reports_a_missing_public_key(host, tmp_path):
    host.public_key = ""

    with pytest.raises(ValueError, match="Unable to derive"):
        prepare.ensure_keypair(tmp_path)


def test_authorized_key_keeps_foreign_lines_and_replaces_platform_ones(host):
    account = FakeAccount(prepare.ACCOUNT)
    host.accounts[account.pw_name] = account
    ssh_directory = prepare.ACCOUNT_HOME / ".ssh"
    ssh_directory.mkdir(parents=True)
    authorization = ssh_directory / "authorized_keys"
    authorization.write_text(f"ssh-ed25519 AAAA operator@laptop\nrestrict ssh-rsa OLD {prepare.KEY_COMMENT}\n")

    prepare.ensure_authorized_key(account, "ssh-rsa NEW")
    prepare.ensure_authorized_key(account, "ssh-rsa NEW")

    content = authorization.read_text()
    assert "operator@laptop" in content
    assert "OLD" not in content
    assert content.count(prepare.KEY_COMMENT) == 1
    assert "restrict ssh-rsa NEW " + prepare.KEY_COMMENT in content
    assert authorization.stat().st_mode & 0o777 == 0o600
    assert ssh_directory.stat().st_mode & 0o777 == 0o700


def test_write_state_records_the_payload_with_restrictive_mode(host, tmp_path):
    state_file = prepare.write_state(tmp_path, {"version": 3})

    assert state_file.name == "app-sftp-account.json"
    assert state_file.read_text() == '{"version": 3}'
    assert state_file.stat().st_mode & 0o777 == 0o600


def test_prepare_volume_root_requires_the_docker_volume_tree(host, monkeypatch, tmp_path):
    monkeypatch.setattr(prepare, "Path", _path_with_volume_root(tmp_path / "missing"))

    assert prepare.prepare_volume_root(FakeAccount(prepare.ACCOUNT)) is False


def test_prepare_volume_root_applies_an_inheritable_default_acl(host, monkeypatch, tmp_path):
    volume_root = tmp_path / "volumes"
    volume_root.mkdir()
    monkeypatch.setattr(prepare, "Path", _path_with_volume_root(volume_root))

    assert prepare.prepare_volume_root(FakeAccount(prepare.ACCOUNT)) is True

    command = [item for item in host.commands if item[0] == "setfacl"][-1]
    assert "u:websoft9-sftp:rwX,d:u:websoft9-sftp:rwX,d:m:rwX" in command


def test_prepare_volume_root_is_not_fatal_when_setfacl_fails(host, monkeypatch, tmp_path):
    volume_root = tmp_path / "volumes"
    volume_root.mkdir()
    monkeypatch.setattr(prepare, "Path", _path_with_volume_root(volume_root))

    def failing_run(command, timeout=30):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(prepare, "run", failing_run)

    assert prepare.prepare_volume_root(FakeAccount(prepare.ACCOUNT)) is False


def _path_with_volume_root(volume_root):
    """Redirects the hard-coded `/var/lib/docker/volumes` lookup to the test directory."""

    def fake_path(value):
        if str(value) == "/var/lib/docker/volumes":
            return volume_root
        return REAL_PATH(value)

    return fake_path


# ── end-to-end prepare / revoke ───────────────────────────────────────────


def test_prepare_requires_root(host):
    host.euid = 1000

    with pytest.raises(ValueError, match="must be prepared as root"):
        prepare.prepare(str(host.tmp_path))


def test_prepare_writes_the_state_the_service_expects(host, monkeypatch, capsys):
    monkeypatch.setattr(prepare, "account_groups", lambda name: set())
    monkeypatch.setattr(prepare, "prepare_volume_root", lambda account: True)
    _write_sshd_config(host, "Port 22\n")

    prepare.prepare(str(host.tmp_path))

    import json

    state = json.loads((host.tmp_path / "config/host-access/app-sftp-account.json").read_text())
    assert state["version"] == prepare.STATE_VERSION
    assert state["username"] == prepare.ACCOUNT
    assert state["uid"] == 2001
    assert state["sshd_mode"] == "main"
    assert state["volume_root_acl"] is True
    assert Path(state["key_path"]).stat().st_mode & 0o777 == 0o600
    # 最后一行 stdout 是 AppHub 解析的状态 JSON
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == state


def test_revoke_requires_root(host):
    host.euid = 1000

    with pytest.raises(ValueError, match="must be revoked as root"):
        prepare.revoke(str(host.tmp_path))


def test_revoke_without_a_prepared_account_is_a_no_op(host):
    assert prepare.revoke(str(host.tmp_path / "nothing-here")) == {"revoked": False}


def test_revoke_removes_keys_state_and_sshd_configuration(host, capsys):
    import json

    account = FakeAccount(prepare.ACCOUNT)
    host.accounts[prepare.ACCOUNT] = account
    ssh_directory = prepare.ACCOUNT_HOME / ".ssh"
    ssh_directory.mkdir(parents=True)
    authorization = ssh_directory / "authorized_keys"
    authorization.write_text(f"ssh-ed25519 AAAA operator@laptop\nrestrict ssh-rsa KEY {prepare.KEY_COMMENT}\n")

    data_dir = host.tmp_path / "config/host-access"
    data_dir.mkdir(parents=True)
    (data_dir / "app-sftp-account.json").write_text(json.dumps({"username": prepare.ACCOUNT}))
    (data_dir / "sftp.key").write_text("private")
    prepare.SSHD_DROPIN_DIR.mkdir(parents=True)
    prepare.SSHD_DROPIN.write_text("Match User websoft9-sftp\n")

    prepare.revoke(str(host.tmp_path))

    result = json.loads(capsys.readouterr().out.strip())
    assert result == {"revoked": True, "removed_key_lines": True}
    assert "operator@laptop" in authorization.read_text()
    assert prepare.KEY_COMMENT not in authorization.read_text()
    assert not (data_dir / "sftp.key").exists()
    assert not (data_dir / "app-sftp-account.json").exists()
    assert not prepare.SSHD_DROPIN.exists()
    assert ["reload_sshd"] in host.commands


def test_revoke_strips_the_marker_block_from_the_main_config(host, capsys):
    import json

    (host.tmp_path / "config/host-access").mkdir(parents=True)
    _write_sshd_config(host, "Port 22\n")
    prepare.install_sshd_config(host.tmp_path, prepare.ACCOUNT)
    assert prepare.MARKER_BEGIN in Path(prepare.SSHD_CONFIG).read_text()

    prepare.revoke(str(host.tmp_path))

    assert json.loads(capsys.readouterr().out.strip())["revoked"] is True
    restored = Path(prepare.SSHD_CONFIG).read_text()
    assert prepare.MARKER_BEGIN not in restored
    assert restored == "Port 22\n"


def test_enable_disable_cycles_restore_the_original_main_config(host):
    (host.tmp_path / "config/host-access").mkdir(parents=True)
    _write_sshd_config(host, "Port 22\nAcceptEnv LANG\n")

    for _ in range(3):
        prepare.install_sshd_config(host.tmp_path, prepare.ACCOUNT)
        prepare.revoke(str(host.tmp_path))

    # 每轮启用/停用后文件必须逐字节回到原样,不能每次都多一个空行
    assert Path(prepare.SSHD_CONFIG).read_text() == "Port 22\nAcceptEnv LANG\n"


def test_revoke_reports_a_rejected_sshd_configuration(host):
    (host.tmp_path / "config/host-access").mkdir(parents=True)
    _write_sshd_config(host, "Port 22\n")
    prepare.SSHD_DROPIN_DIR.mkdir(parents=True)
    prepare.SSHD_DROPIN.write_text("Match User websoft9-sftp\n")
    host.sshd_rejects = True

    with pytest.raises(ValueError, match="rejected after revoking"):
        prepare.revoke(str(host.tmp_path))


def run_script(*arguments):
    """Runs the script the same way the helper container does: `python3 <file> <operation> <root>`."""
    return subprocess.run(
        [sys.executable, str(Path(prepare.__file__)), *arguments],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_the_cli_entry_point_requires_a_data_root():
    result = run_script("prepare", "")

    assert result.returncode == 1
    assert "data root is required" in result.stderr


def test_the_cli_entry_point_rejects_unknown_operations():
    result = run_script("explode", "/data")

    assert result.returncode == 1
    assert "Unsupported operation: explode" in result.stderr
