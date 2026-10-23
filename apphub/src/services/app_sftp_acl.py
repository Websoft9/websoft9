"""Host-side POSIX ACL helper for application-file SFTP sessions.

Runs inside a short-lived privileged helper container that enters the host
namespaces, so it uses the host Python runtime and the host ``setfacl`` /
``getfacl`` binaries.

Operations:
  apply   <data_root> <session_id> <path> <account> <container_uid> [--recursive]
  grant   <data_root> <session_id> <subpath>     # recursive grant inside a session
  release <data_root> <session_id>

Every mutation is recorded in a manifest so ``release`` can restore the exact
previous ACL state. Nothing is ever left behind silently.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_RECURSIVE_ENTRIES = 20000
RECURSIVE_DEADLINE_SECONDS = 60
SHALLOW_GRANT_LIMIT = 500
DENY_PREFIXES = (
    "/etc",
    "/root",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/var/run",
    "/var/lib/docker",
    "/var/lib/kubelet",
)
MANIFEST_VERSION = 1


def run(command, timeout=30):
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)


def host_root():
    """Return the host root mount point when the helper runs with the host tree mounted."""
    candidate = os.getenv("WEBSOFT9_HOST_ROOT", "/host")
    return candidate if os.path.isdir(candidate) else ""


def fs_path(path):
    """Map a host path to the path visible inside the helper container (idempotent)."""
    root = host_root()
    text = str(path)
    if not root or not text.startswith("/") or text == root or text.startswith(root + "/"):
        return text
    return os.path.join(root, text.lstrip("/"))


def host_view(path):
    """Map a helper-container path back to the host path recorded in manifests."""
    root = host_root()
    text = str(path)
    if root and (text == root or text.startswith(root + "/")):
        return text[len(root):] or "/"
    return text


def getfacl(path):
    return run(["getfacl", "-p", "--absolute-names", fs_path(path)], timeout=15).stdout


def account_uid(account):
    """Resolve the account to a numeric UID using the host passwd database.

    The helper container does not share the host account database, so ACL entries
    must use UIDs instead of names.
    """
    text = str(account or "").strip()
    if text.isdigit():
        return text
    passwd = Path(fs_path("/etc/passwd"))
    try:
        for line in passwd.read_text().splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[0] == text:
                return parts[2]
    except OSError:
        pass
    import pwd

    return str(pwd.getpwnam(text).pw_uid)


def parse_acl(text):
    access = {}
    default = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        target = default
        body = stripped
        if stripped.startswith("default:"):
            body = stripped[len("default:"):]
        else:
            target = access
        parts = body.split(":")
        if len(parts) == 3:
            target[(parts[0], parts[1])] = parts[2]
    return access, default


def account_has(entry, permission):
    return entry is not None and permission in entry


def has_traverse(access, account):
    if account_has(access.get(("other", "")), "x"):
        return True
    entry = access.get(("user", account))
    if not account_has(entry, "x"):
        return False
    mask = access.get(("mask", ""))
    return mask is None or account_has(mask, "x")


def is_docker_volume_data(path):
    parts = path.rstrip("/").split("/")
    return len(parts) == 7 and parts[1:4] == ["var", "lib", "docker"] and parts[4] == "volumes" and parts[6] == "_data"


def validate_target(path):
    target = fs_path(path)
    if not str(path).startswith("/") or str(path).rstrip("/") in ("", "/"):
        raise ValueError("The application directory cannot be the filesystem root")
    resolved = os.path.realpath(target)
    if os.path.normpath(resolved) != os.path.normpath(target):
        raise ValueError("Symbolic links are not supported for application directories")
    host_resolved = host_view(resolved)
    if not is_docker_volume_data(host_resolved):
        for prefix in DENY_PREFIXES:
            if host_resolved == prefix or host_resolved.startswith(prefix + "/"):
                raise ValueError(f"The application directory is inside a protected system path: {prefix}")
    attributes = os.lstat(target)
    if not stat.S_ISDIR(attributes.st_mode):
        raise ValueError("The application directory is not a directory")
    return host_resolved


def setfacl(arguments, timeout=30):
    try:
        return run(["setfacl", *arguments], timeout=timeout)
    except FileNotFoundError as error:
        raise ValueError("The host does not provide the 'acl' utilities (getfacl/setfacl)") from error
    except subprocess.CalledProcessError as error:
        message = (error.stderr or "").strip()
        if "not supported" in message.lower():
            raise ValueError("The filesystem holding the application directory does not support ACL") from error
        raise ValueError(f"setfacl failed: {message or error}") from error


def snapshot_path(path):
    return getfacl(path)


def ancestor_paths(path):
    parents = []
    current = Path(path).parent
    while str(current) != "/":
        parents.append(str(current))
        current = current.parent
    return list(reversed(parents))


def apply_entries(path, account, container_uid, recursive=False):
    entries = [f"u:{account}:rwX", f"d:u:{account}:rwX", "d:m:rwX"]
    if container_uid > 0:
        entries.append(f"d:u:{container_uid}:rwX")
    setfacl(["-m", ",".join(entries), fs_path(path)])

    recorded = []
    truncated = False
    if recursive:
        deadline = time.time() + RECURSIVE_DEADLINE_SECONDS
        count = 0
        for directory, subdirectories, files in os.walk(fs_path(path), followlinks=False):
            if time.time() > deadline or count >= MAX_RECURSIVE_ENTRIES:
                truncated = True
                break
            candidates = [directory, *(os.path.join(directory, name) for name in files)]
            for candidate in candidates:
                if time.time() > deadline or count >= MAX_RECURSIVE_ENTRIES:
                    truncated = True
                    break
                try:
                    attributes = os.lstat(candidate)
                except OSError:
                    continue
                if stat.S_ISLNK(attributes.st_mode):
                    continue
                count += 1
                text = getfacl(candidate)
                access, default = parse_acl(text)
                if account_has(access.get(("user", account)), "rw"):
                    continue
                is_directory = stat.S_ISDIR(attributes.st_mode)
                entries = [f"u:{account}:rwX"]
                if is_directory:
                    entries += [f"d:u:{account}:rwX", "d:m:rwX"]
                    if container_uid > 0:
                        entries.append(f"d:u:{container_uid}:rwX")
                setfacl(["-m", ",".join(entries), candidate])
                recorded.append({
                    "path": host_view(candidate),
                    "is_directory": is_directory,
                    "mask_before": access.get(("mask", "")),
                    "default_mask_before": default.get(("mask", "")),
                    "uid_entry_added": container_uid > 0 and is_directory,
                })
            subdirectories[:] = [name for name in subdirectories if not os.path.islink(os.path.join(directory, name))]
    return recorded, truncated


def grant_directory_entries(path, account, container_uid):
    """Grant the account access to the direct children of one directory.

    Interactive browsing only needs the directory being opened; deeper levels
    are granted when the operator enters them. This keeps the helper bounded
    (at most ``SHALLOW_GRANT_LIMIT`` entries) instead of walking whole trees.
    """
    recorded = []
    truncated = False
    count = 0
    try:
        iterator = os.scandir(fs_path(path))
    except OSError:
        return recorded, False
    with iterator as entries:
        for entry in entries:
            if count >= SHALLOW_GRANT_LIMIT:
                truncated = True
                break
            try:
                if entry.is_symlink():
                    continue
                is_directory = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            count += 1
            candidate = entry.path
            text = getfacl(candidate)
            access, default = parse_acl(text)
            if account_has(access.get(("user", account)), "rw"):
                continue
            entries_to_add = [f"u:{account}:rwX"]
            if is_directory:
                entries_to_add += [f"d:u:{account}:rwX", "d:m:rwX"]
                if container_uid > 0:
                    entries_to_add.append(f"d:u:{container_uid}:rwX")
            setfacl(["-m", ",".join(entries_to_add), candidate])
            recorded.append({
                "path": host_view(candidate),
                "is_directory": is_directory,
                "mask_before": access.get(("mask", "")),
                "default_mask_before": default.get(("mask", "")),
                "uid_entry_added": container_uid > 0 and is_directory,
            })
    return recorded, truncated


def apply(data_root, session_id, path, account, container_uid, recursive=False):
    manifest_dir = Path(fs_path(data_root)) / "config/host-access/sftp-acl"
    manifest_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest_file = manifest_dir / f"{session_id}.json"
    if manifest_file.exists():
        release(data_root, session_id)

    target = validate_target(path)
    uid = account_uid(account)
    snapshots = []
    for ancestor in ancestor_paths(target):
        try:
            text = snapshot_path(ancestor)
        except OSError:
            continue
        access, _ = parse_acl(text)
        if has_traverse(access, uid):
            continue
        setfacl(["-m", f"u:{uid}:x", fs_path(ancestor)])
        snapshots.append({"path": ancestor, "acl": text})

    root_acl = snapshot_path(target)
    recorded, truncated = apply_entries(target, uid, container_uid, recursive=recursive)

    manifest = {
        "version": MANIFEST_VERSION,
        "session_id": session_id,
        "root": target,
        "account": account,
        "account_uid": uid,
        "container_uid": container_uid,
        "snapshots": snapshots,
        "root_acl": root_acl,
        "recursive": recorded,
        "truncated": truncated,
    }
    descriptor, temporary = tempfile.mkstemp(dir=str(manifest_dir))
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(manifest, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, manifest_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"path": target, "ancestors": len(snapshots), "recursive_entries": len(recorded), "truncated": truncated}


def grant(data_root, session_id, subpath):
    manifest_file = Path(fs_path(data_root)) / "config/host-access/sftp-acl" / f"{session_id}.json"
    if not manifest_file.is_file():
        raise ValueError("The application SFTP authorization is no longer active")
    manifest = json.loads(manifest_file.read_text())
    target = host_view(os.path.realpath(fs_path(subpath)))
    root = manifest["root"]
    if not (target == root or target.startswith(root + "/")):
        raise ValueError("The requested path is outside the authorized application directory")
    known = {item.get("path") for item in manifest.get("snapshots") or []}
    uid = str(manifest.get("account_uid") or account_uid(manifest["account"]))
    if target not in known:
        # Remember the exact previous state so ``release`` can restore it.
        manifest.setdefault("snapshots", []).append({"path": target, "acl": snapshot_path(target)})
    apply_entries(target, uid, int(manifest["container_uid"]), recursive=False)
    recorded, truncated = grant_directory_entries(target, uid, int(manifest["container_uid"]))
    manifest["recursive"].extend(recorded)
    manifest["truncated"] = bool(manifest.get("truncated")) or truncated
    descriptor, temporary = tempfile.mkstemp(dir=str(manifest_file.parent))
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(manifest, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, manifest_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"path": target, "recursive_entries": len(recorded), "truncated": truncated}


def restore_acl(path, text):
    mapped = fs_path(path)
    if mapped != str(path):
        text = text.replace(f"# file: {path}", f"# file: {mapped}", 1)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, dir="/tmp") as handle:
        handle.write(text)
        handle.flush()
        temporary = handle.name
    try:
        try:
            setfacl(["-b", mapped], timeout=20)
        except ValueError:
            pass
        run(["setfacl", f"--restore={temporary}"], timeout=30)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def release(data_root, session_id):
    manifest_file = Path(fs_path(data_root)) / "config/host-access/sftp-acl" / f"{session_id}.json"
    if not manifest_file.is_file():
        return {"released": False}
    manifest = json.loads(manifest_file.read_text())
    try:
        account = str(manifest.get("account_uid") or account_uid(manifest.get("account") or "websoft9-sftp"))
    except (KeyError, OSError):
        account = "2001"
    container_uid = int(manifest.get("container_uid") or 0)
    for record in reversed(manifest.get("recursive") or []):
        path = record.get("path")
        if not path or not os.path.exists(fs_path(path)):
            continue
        target = fs_path(path)
        try:
            setfacl(["-x", f"u:{account}", target], timeout=15)
        except ValueError:
            pass
        if record.get("is_directory"):
            targets = [f"d:u:{account}"]
            if record.get("uid_entry_added"):
                targets.append(f"d:u:{container_uid}")
            try:
                setfacl(["-x", ",".join(targets), target], timeout=15)
            except ValueError:
                pass
        if record.get("mask_before"):
            try:
                setfacl(["-m", f"m::{record['mask_before']}", target], timeout=15)
            except ValueError:
                pass
        if record.get("default_mask_before"):
            try:
                setfacl(["-m", f"d:m::{record['default_mask_before']}", target], timeout=15)
            except ValueError:
                pass

    if manifest.get("root_acl"):
        try:
            restore_acl(manifest["root"], manifest["root_acl"])
        except Exception:
            pass
    for snapshot in reversed(manifest.get("snapshots") or []):
        try:
            restore_acl(snapshot["path"], snapshot["acl"])
        except Exception:
            pass

    manifest_file.unlink(missing_ok=True)
    return {"released": True, "root": manifest.get("root")}


if __name__ == "__main__":
    try:
        operation = sys.argv[1]
        if operation == "apply":
            data_root, session_id, path, account, container_uid = sys.argv[2:7]
            recursive = "--recursive" in sys.argv[7:]
            print(json.dumps(apply(data_root, session_id, path, account, int(container_uid), recursive=recursive)))
        elif operation == "grant":
            data_root, session_id, subpath = sys.argv[2:5]
            print(json.dumps(grant(data_root, session_id, subpath)))
        elif operation == "release":
            data_root, session_id = sys.argv[2:4]
            print(json.dumps(release(data_root, session_id)))
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    except Exception as error:
        print(f"Application SFTP authorization failed: {error}", file=sys.stderr)
        sys.exit(1)
