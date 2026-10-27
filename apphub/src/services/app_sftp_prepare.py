"""Host-side bootstrap for the platform application-file SFTP account.

This script is executed by AppHub inside a short-lived privileged helper
container that enters the host namespaces (``nsenter --target 1 --root``).
It therefore runs with the *host* Python runtime and standard library only.

Responsibilities:
  * create/verify the dedicated ``websoft9-sftp`` system account
  * install the ``sshd`` ``Match User`` configuration (idempotent)
  * create/verify the platform key pair and its ``authorized_keys`` entry
  * write the state file consumed by AppHub

The account has no password, no login shell, no sudo rule and no docker
group membership. It exists only so AppHub can move files over SFTP.
"""

import fcntl
import json
import os
import pwd
import secrets
import stat
import string
import subprocess
import sys
import tempfile
from pathlib import Path

ACCOUNT = "websoft9-sftp"
PREFERRED_UID = 2001
ACCOUNT_HOME = Path("/var/lib/websoft9-sftp")
STATE_VERSION = 3
KEY_COMMENT = "websoft9-platform-sftp"
MARKER_BEGIN = "# >>> websoft9-sftp (managed by Websoft9)"
MARKER_END = "# <<< websoft9-sftp (managed by Websoft9)"
SSHD_CONFIG = Path("/etc/ssh/sshd_config")
SSHD_DROPIN_DIR = Path("/etc/ssh/sshd_config.d")
SSHD_DROPIN = SSHD_DROPIN_DIR / "60-websoft9-sftp.conf"
NOLOGIN_SHELLS = {"/usr/sbin/nologin", "/sbin/nologin", "/bin/false", "/usr/bin/false"}
FORBIDDEN_GROUPS = {"root", "sudo", "wheel", "docker", "adm"}

SSHD_BLOCK = """\
Match User {account}
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PubkeyAuthentication yes
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    AllowTcpForwarding no
    PermitTunnel no
    ForceCommand internal-sftp -u 0002
"""


def account_home(name):
    return ACCOUNT_HOME if name == ACCOUNT else Path(f"/var/lib/{name}")


def run(command, timeout=30):
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)


def secure_directory(path, owner):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Symbolic links are not allowed in the SFTP account directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    attributes = path.stat()
    if attributes.st_uid not in (0, owner):
        raise ValueError("SFTP account directory has an unexpected owner")
    os.chown(path, owner, -1)
    path.chmod(0o700)


def account_groups(username):
    try:
        import grp

        primary = pwd.getpwnam(username).pw_gid
        groups = {group.gr_name for group in grp.getgrall() if username in group.gr_mem or group.gr_gid == primary}
        return groups
    except Exception:
        return set()


def account_complies(account):
    shell = str(account.pw_shell or "")
    if shell not in NOLOGIN_SHELLS:
        return False
    if Path(account.pw_dir) != account_home(account.pw_name):
        return False
    return not (account_groups(account.pw_name) & FORBIDDEN_GROUPS)


def choose_account_name():
    """Return the account name to use.

    The reserved name is reused only when the existing account is compliant.
    If somebody else already owns it, fall back to ``websoft9-<4 letters>``
    instead of touching that account.
    """
    try:
        existing = pwd.getpwnam(ACCOUNT)
    except KeyError:
        return ACCOUNT
    if account_complies(existing):
        return ACCOUNT
    alphabet = string.ascii_lowercase
    for _ in range(20):
        candidate = f"websoft9-{''.join(secrets.choice(alphabet) for _ in range(4))}"
        try:
            pwd.getpwnam(candidate)
        except KeyError:
            return candidate
    raise ValueError("Unable to allocate a free SFTP account name")


def ensure_account():
    name = choose_account_name()
    home = account_home(name)
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        command = [
            "useradd", "--system", "--user-group",
            "--home-dir", str(home), "--create-home",
            "--shell", "/usr/sbin/nologin", "--comment", "Websoft9 application file access",
        ]
        try:
            run([*command, "--uid", str(PREFERRED_UID), name])
        except subprocess.CalledProcessError:
            run([*command, name])
        account = pwd.getpwnam(name)

    shell = str(account.pw_shell or "")
    if shell not in NOLOGIN_SHELLS:
        raise ValueError(f"The existing '{name}' account has a login shell; refusing to use it")
    if Path(account.pw_dir) != home:
        raise ValueError(f"The existing '{name}' account has an unexpected home directory")
    forbidden = account_groups(name) & FORBIDDEN_GROUPS
    if forbidden:
        raise ValueError(f"The existing '{name}' account belongs to privileged groups: {', '.join(sorted(forbidden))}")
    if not home.is_dir():
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(home, account.pw_uid, account.pw_gid)
    home.chmod(0o700)
    return account


def sshd_supports_dropin(main_config):
    if not SSHD_DROPIN_DIR.is_dir():
        return False
    for line in main_config.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("include ") and "sshd_config.d" in stripped:
            return True
    return False


def write_atomic(path, content, mode, owner=0):
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, owner, -1)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install_sshd_config(data_dir, account_name=None):
    block = SSHD_BLOCK.format(account=account_name or ACCOUNT)
    if not SSHD_CONFIG.is_file():
        raise ValueError("The host does not expose an OpenSSH server configuration")
    original = SSHD_CONFIG.read_text()
    use_dropin = sshd_supports_dropin(original)
    if use_dropin:
        current = SSHD_DROPIN.read_text() if SSHD_DROPIN.is_file() else None
        changed = current != block
        if changed:
            write_atomic(SSHD_DROPIN, block, 0o644)
        target = SSHD_DROPIN
        mode = "dropin"
    else:
        legacy = f"{MARKER_BEGIN}\n{block}{MARKER_END}\n"
        if MARKER_BEGIN in original:
            head, _, rest = original.partition(MARKER_BEGIN)
            _, _, tail = rest.partition(MARKER_END)
            updated = head + legacy + tail.lstrip("\n")
        else:
            separator = "" if original.endswith("\n") else "\n"
            updated = original + separator + "\n" + legacy
        changed = updated != original
        if changed:
            backup = data_dir / "sshd_config.websoft9.bak"
            if not backup.exists():
                write_atomic(backup, original, 0o600)
            write_atomic(SSHD_CONFIG, updated, 0o600)
        target = SSHD_CONFIG
        mode = "main"

    sshd = "/usr/sbin/sshd" if Path("/usr/sbin/sshd").is_file() else "/usr/sbin/sshd"
    try:
        run([sshd, "-t"], timeout=15)
    except Exception as exc:
        if use_dropin:
            SSHD_DROPIN.unlink(missing_ok=True)
        else:
            backup = data_dir / "sshd_config.websoft9.bak"
            if backup.is_file():
                write_atomic(SSHD_CONFIG, backup.read_text(), 0o600)
        raise ValueError(f"The generated sshd configuration was rejected: {exc}") from exc

    if changed:
        reload_sshd()
    return {"mode": mode, "path": str(target), "changed": changed}


def sshd_unit():
    if not Path("/bin/systemctl").exists() and not Path("/usr/bin/systemctl").exists():
        return None
    for unit in ("ssh.service", "sshd.service"):
        try:
            result = run(["systemctl", "list-unit-files", unit], timeout=10)
        except Exception:
            continue
        if unit in result.stdout:
            return unit
    return None


def reload_sshd():
    unit = sshd_unit()
    if unit is None:
        return
    try:
        run(["systemctl", "reload", unit], timeout=20)
    except Exception:
        try:
            run(["systemctl", "restart", unit], timeout=30)
        except Exception:
            pass


def ensure_keypair(data_dir):
    key_file = data_dir / "sftp.key"
    if key_file.exists() or key_file.is_symlink():
        attributes = key_file.lstat()
        if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink != 1 or attributes.st_uid != os.geteuid():
            raise ValueError("The prepared SFTP private key is unsafe")
        key_file.chmod(0o600)
    else:
        with tempfile.TemporaryDirectory(dir=str(data_dir)) as temporary:
            generated = Path(temporary) / "key"
            run(["ssh-keygen", "-q", "-t", "rsa", "-b", "3072", "-N", "", "-C", KEY_COMMENT, "-f", str(generated)])
            os.replace(generated, key_file)
            key_file.chmod(0o600)
    public_key = run(["ssh-keygen", "-y", "-f", str(key_file)]).stdout.strip()
    if not public_key:
        raise ValueError("Unable to derive the platform SFTP public key")
    return key_file, public_key


def ensure_authorized_key(account, public_key):
    directory = ACCOUNT_HOME / ".ssh"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(directory, account.pw_uid, account.pw_gid)
    directory.chmod(0o700)
    authorization = directory / "authorized_keys"
    descriptor = os.open(authorization, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        attributes = os.fstat(handle.fileno())
        if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink != 1:
            raise ValueError("The SFTP authorization file is unsafe")
        os.fchown(handle.fileno(), account.pw_uid, account.pw_gid)
        os.fchmod(handle.fileno(), 0o600)
        original = handle.read()
        kept = [line for line in original.splitlines() if KEY_COMMENT not in line]
        line = f"restrict {public_key} {KEY_COMMENT}"
        updated = "\n".join([*kept, line]) + "\n"
        if updated != original:
            handle.seek(0)
            handle.write(updated)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
    return authorization


def write_state(data_dir, payload):
    state_file = data_dir / "app-sftp-account.json"
    descriptor, temporary = tempfile.mkstemp(dir=str(data_dir))
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, state_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return state_file


def prepare_volume_root(account):
    """Give the platform account inheritable access to future Docker volumes.

    Applying a default ACL to ``/var/lib/docker/volumes`` means volumes created
    later inherit access, so they never need a temporary helper container.
    Existing volumes are granted on first use and recorded until removal.
    """
    root = Path("/var/lib/docker/volumes")
    if not root.is_dir():
        return False
    try:
        run(["setfacl", "-m", f"u:{account.pw_name}:rwX,d:u:{account.pw_name}:rwX,d:m:rwX", str(root)], timeout=20)
        return True
    except Exception:
        return False


def prepare(data_root):
    if os.geteuid() != 0:
        raise ValueError("The SFTP account must be prepared as root on the host")
    data_dir = Path(data_root) / "config/host-access"
    secure_directory(data_dir, 0)
    # The AppHub process serializes preparation with ``.app-sftp.lock``; the host
    # side must use a different file or the two flock() calls deadlock.
    lock_path = data_dir / ".app-sftp-prepare.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        account = ensure_account()
        sshd_state = install_sshd_config(data_dir, account.pw_name)
        key_file, public_key = ensure_keypair(data_dir)
        authorization = ensure_authorized_key(account, public_key)
        volume_root_acl = prepare_volume_root(account)
        state = {
            "version": STATE_VERSION,
            "username": account.pw_name,
            "uid": account.pw_uid,
            "gid": account.pw_gid,
            "home": str(account.pw_dir),
            "key_path": str(key_file),
            "authorization_path": str(authorization),
            "volume_root_acl": volume_root_acl,
            "sshd_mode": sshd_state["mode"],
            "sshd_path": sshd_state["path"],
            "sshd_changed": sshd_state["changed"],
        }
        write_state(data_dir, state)
    print(json.dumps(state))


def revoke(data_root):
    """Remove the platform SFTP authorization from the host.

    The OS account itself is kept (it has no shell and no credentials), but the
    public key, private key, state file and sshd ``Match`` configuration are
    removed so the platform can no longer log in over SFTP.
    """
    if os.geteuid() != 0:
        raise ValueError("The SFTP account must be revoked as root on the host")
    data_dir = Path(data_root) / "config/host-access"
    if not data_dir.is_dir():
        return {"revoked": False}
    lock_path = data_dir / ".app-sftp-prepare.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    removed_key_lines = False
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state_file = data_dir / "app-sftp-account.json"
        username = ACCOUNT
        if state_file.is_file():
            try:
                username = str(json.loads(state_file.read_text()).get("username") or ACCOUNT)
            except (OSError, ValueError):
                username = ACCOUNT
        try:
            account = pwd.getpwnam(username)
        except KeyError:
            account = None
        if account is not None:
            authorization = Path(account.pw_dir) / ".ssh" / "authorized_keys"
            if authorization.is_file() and not authorization.is_symlink():
                original = authorization.read_text()
                kept = [line for line in original.splitlines() if KEY_COMMENT not in line]
                if len(kept) != len(original.splitlines()):
                    write_atomic(authorization, ("\n".join(kept) + "\n") if kept else "", 0o600, account.pw_uid)
                    removed_key_lines = True

        key_file = data_dir / "sftp.key"
        if key_file.exists() or key_file.is_symlink():
            key_file.unlink()
        if state_file.exists() or state_file.is_symlink():
            state_file.unlink()

        changed = False
        if SSHD_DROPIN.is_file() or SSHD_DROPIN.is_symlink():
            SSHD_DROPIN.unlink()
            changed = True
        elif SSHD_CONFIG.is_file() and MARKER_BEGIN in SSHD_CONFIG.read_text():
            original = SSHD_CONFIG.read_text()
            head, _, rest = original.partition(MARKER_BEGIN)
            _, _, tail = rest.partition(MARKER_END)
            write_atomic(SSHD_CONFIG, head + tail.lstrip("\n"), 0o600)
            changed = True
        if changed:
            sshd = "/usr/sbin/sshd" if Path("/usr/sbin/sshd").is_file() else "/usr/sbin/sshd"
            try:
                run([sshd, "-t"], timeout=15)
            except Exception as exc:
                raise ValueError(f"The sshd configuration was rejected after revoking the SFTP account: {exc}") from exc
            reload_sshd()

        volume_root = Path("/var/lib/docker/volumes")
        if volume_root.is_dir():
            try:
                run(["setfacl", "-x", f"u:{ACCOUNT},d:u:{ACCOUNT}", str(volume_root)], timeout=15)
            except Exception:
                pass
    print(json.dumps({"revoked": True, "removed_key_lines": removed_key_lines}))


if __name__ == "__main__":
    try:
        operation = sys.argv[1] if len(sys.argv) > 1 else "prepare"
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if not target:
            raise ValueError("The platform data root is required")
        if operation == "prepare":
            prepare(target)
        elif operation == "revoke":
            revoke(target)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    except Exception as error:
        print(f"SFTP account operation failed: {error}", file=sys.stderr)
        sys.exit(1)
