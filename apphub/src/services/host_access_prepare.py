import fcntl
import json
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SFTP_SERVER_CANDIDATES = (
    "/usr/lib/openssh/sftp-server",
    "/usr/libexec/openssh/sftp-server",
    "/usr/lib/ssh/sftp-server",
    "/usr/lib/sftp-server",
)
SUDOERS_DIR = Path("/etc/sudoers.d")


def secure_directory(path, owner):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Symbolic links are not allowed in SSH authorization paths")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid not in (0, owner):
        raise ValueError("SSH authorization directory has an unexpected owner")
    os.chown(path, owner, -1)
    path.chmod(0o700)


def check_file(path):
    attributes = path.lstat()
    if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink != 1 or attributes.st_uid != os.geteuid() or attributes.st_mode & 0o077:
        raise ValueError("Prepared SSH credential file has unsafe ownership or permissions")


def ssh_policy(username):
    executable = shutil.which("sshd") or "/usr/sbin/sshd"
    output = subprocess.run([executable, "-T", "-C", f"user={username},host=localhost,addr=127.0.0.1"], check=True, capture_output=True, text=True, timeout=10).stdout
    settings = dict(line.split(None, 1) for line in output.splitlines() if " " in line)
    if settings.get("pubkeyauthentication") != "yes":
        raise ValueError("The host SSH policy does not allow public-key authentication")
    if username == "root" and settings.get("permitrootlogin") not in ("yes", "prohibit-password", "without-password"):
        raise ValueError("The host SSH policy does not allow root key login; create a manual connection with a non-root account")
    return settings


def choose_account(requested, metadata):
    if requested:
        username = requested
    elif metadata.exists():
        check_file(metadata)
        username = json.loads(metadata.read_text())["username"]
    elif os.getenv("SUDO_USER") and os.getenv("SUDO_USER") != "root":
        username = os.environ["SUDO_USER"]
    else:
        accounts = [account for account in pwd.getpwall() if 1000 <= account.pw_uid < 65534 and account.pw_shell not in ("/bin/false", "/usr/sbin/nologin", "/sbin/nologin") and (Path(account.pw_dir) / ".ssh/authorized_keys").is_file()]
        if len(accounts) > 1:
            raise ValueError("Multiple SSH accounts found; create a manual connection with the intended account")
        username = accounts[0].pw_name if accounts else "root"
    account = pwd.getpwnam(username)
    home = Path(account.pw_dir)
    if not home.is_absolute() or home.is_symlink() or not home.is_dir() or home.stat().st_uid != account.pw_uid or home.stat().st_mode & 0o022:
        raise ValueError("The selected host account has an unsafe home directory")
    if metadata.exists():
        check_file(metadata)
        if json.loads(metadata.read_text())["username"] != username:
            raise ValueError("Local SSH authorization is already prepared for another account; existing credentials were preserved")
    return account


def sftp_server_paths(policy):
    candidates = []
    for line in str(policy.get("subsystem") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "sftp" and parts[1].startswith("/"):
            candidates.append(parts[1])
    candidates.extend(SFTP_SERVER_CANDIDATES)
    paths = []
    for item in candidates:
        candidate = Path(item)
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            continue
        for value in (str(candidate), str(candidate.resolve())):
            if value not in paths:
                paths.append(value)
    return paths


def prepare_sftp_sudoers(account, policy):
    if account.pw_uid == 0 or SUDOERS_DIR.is_symlink() or not SUDOERS_DIR.is_dir():
        return lambda: None
    servers = sftp_server_paths(policy)
    if not servers:
        return lambda: None
    target = SUDOERS_DIR / "websoft9-local-sftp"
    if target.is_symlink():
        raise ValueError("Unsafe sudoers authorization file")
    previous = target.read_bytes() if target.exists() else None
    rule = f"{account.pw_name} ALL=(root) NOPASSWD: {', '.join(servers)}\n".encode()
    with tempfile.NamedTemporaryFile(mode="wb", dir=SUDOERS_DIR, delete=False) as pending:
        temporary = Path(pending.name)
        try:
            os.fchown(pending.fileno(), 0, 0)
            os.fchmod(pending.fileno(), 0o440)
            pending.write(rule)
            pending.flush()
            os.fsync(pending.fileno())
            visudo = shutil.which("visudo") or "/usr/sbin/visudo"
            if Path(visudo).is_file() and os.access(visudo, os.X_OK):
                subprocess.run([visudo, "-cf", str(temporary)], check=True, capture_output=True, timeout=10)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def rollback():
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            with tempfile.NamedTemporaryFile(mode="wb", dir=SUDOERS_DIR, delete=False) as pending:
                restore = Path(pending.name)
                try:
                    os.fchown(pending.fileno(), 0, 0)
                    os.fchmod(pending.fileno(), 0o440)
                    pending.write(previous)
                    pending.flush()
                    os.fsync(pending.fileno())
                    os.replace(restore, target)
                finally:
                    restore.unlink(missing_ok=True)

    return rollback


def prepare(data_root, requested):
    if os.geteuid() != 0:
        raise ValueError("Host SSH preparation must run as root on the host")
    directory = Path(data_root) / "config/host-access"
    secure_directory(directory, 0)
    metadata = directory / "local-ssh.json"
    private_key = directory / "local-ssh.key"
    descriptor = os.open(directory / ".local-ssh.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "r+b") as lock:
        attributes = os.fstat(lock.fileno())
        if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink != 1 or attributes.st_uid != 0:
            raise ValueError("Unsafe SSH preparation lock")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        account = choose_account(requested, metadata)
        policy = ssh_policy(account.pw_name)
        home = Path(account.pw_dir)
        authorization = home / ".ssh/authorized_keys"
        allowed_paths = [Path(value.replace("%h", str(home)).replace("%u", account.pw_name)) for value in policy.get("authorizedkeysfile", "").split()]
        if not any((path if path.is_absolute() else home / path) == authorization for path in allowed_paths):
            raise ValueError("The host uses a custom SSH authorization path; use a manual Terminal connection")
        port = int(os.getenv("WEBSOFT9_HOST_ACCESS_PORT") or policy.get("port", "22"))
        if not 1 <= port <= 65535:
            raise ValueError("Invalid SSH port")
        if private_key.exists() or private_key.is_symlink():
            check_file(private_key)
        else:
            with tempfile.TemporaryDirectory(dir=directory) as temporary:
                generated = Path(temporary) / "key"
                subprocess.run(["ssh-keygen", "-q", "-t", "rsa", "-b", "3072", "-N", "", "-f", str(generated)], check=True, capture_output=True, timeout=30)
                os.replace(generated, private_key)
        public_key = subprocess.run(["ssh-keygen", "-y", "-f", str(private_key)], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        public_line = (public_key + " websoft9-local\n").encode()
        secure_directory(authorization.parent, account.pw_uid)
        descriptor = os.open(authorization, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(descriptor, "r+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            attributes = os.fstat(handle.fileno())
            if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink != 1 or attributes.st_uid not in (0, account.pw_uid) or attributes.st_size > 8 * 1024 * 1024:
                raise ValueError("The host authorization file is unsafe; existing keys were preserved")
            os.fchown(handle.fileno(), account.pw_uid, account.pw_gid)
            os.fchmod(handle.fileno(), 0o600)
            original = handle.read()
            fields = public_key.split()[:2]
            existing = [line.decode(errors="replace").split() for line in original.splitlines() if not line.lstrip().startswith(b"#")]
            added = not any(words[index:index + 2] == fields for words in existing for index in range(len(words) - 1))
            if added:
                handle.write((b"" if not original or original.endswith(b"\n") else b"\n") + public_line)
                handle.flush()
                os.fsync(handle.fileno())
            rollback_sudoers = lambda: None
            try:
                rollback_sudoers = prepare_sftp_sudoers(account, policy)
                subprocess.run(["ssh", "-F", "/dev/null", "-i", str(private_key), "-p", str(port), "-l", account.pw_name, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=5", "-o", "LogLevel=ERROR", "127.0.0.1", "true"], check=True, capture_output=True, timeout=15)
                with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as pending:
                    temporary_metadata = Path(pending.name)
                    try:
                        json.dump({"username": account.pw_name, "port": port, "authorization_path": str(authorization)}, pending)
                        pending.flush()
                        os.fsync(pending.fileno())
                        os.replace(temporary_metadata, metadata)
                    finally:
                        temporary_metadata.unlink(missing_ok=True)
            except Exception:
                rollback_sudoers()
                if added:
                    handle.seek(0)
                    current = handle.read()
                    expected = original + (b"" if not original or original.endswith(b"\n") else b"\n") + public_line
                    restored = original if current == expected else b"".join(line for line in current.splitlines(keepends=True) if line != public_line)
                    handle.seek(0)
                    handle.write(restored)
                    handle.truncate()
                    handle.flush()
                    os.fsync(handle.fileno())
                raise
    print(f"Local SSH authorization prepared for {account.pw_name} (port {port})")


if __name__ == "__main__":
    try:
        prepare(sys.argv[1], sys.argv[2])
    except Exception as error:
        reason = error.stderr.decode(errors="replace").strip() if isinstance(error, subprocess.CalledProcessError) and isinstance(error.stderr, bytes) else str(error)
        print(f"Local SSH preparation unavailable: {reason}. Create a manual Terminal connection with an allowed host account.", file=sys.stderr)
        sys.exit(1)