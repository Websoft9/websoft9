#!/usr/bin/env python3

from __future__ import annotations

import atexit
import configparser
import fcntl
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Appstore synchronization is triggered from several places (runtime bootstrap, daily cron,
# CLI, AppHub API).  The lock file serialises them; the PID marker file only feeds the
# "sync running" status that the console shows.
_APPSTORE_SYNC_LOCK_FILE_DEFAULT = "/opt/websoft9/data/config/appstore_sync.lock"
_APPSTORE_SYNC_PID_FILE_DEFAULT = "/tmp/websoft9-appstore-sync.lock"
_APPSTORE_SYNC_LOCK_POLL_SECONDS = 0.5
# Retries stay aligned with the 60s Cache-Control the publisher sets: retrying sooner would read
# the same inconsistent object again.
_APPSTORE_SYNC_RETRY_DELAY_SECONDS = float(os.getenv("WEBSOFT9_APPSTORE_SYNC_RETRY_DELAY", "60"))
_APPSTORE_SYNC_RETRY_ATTEMPTS = max(1, int(os.getenv("WEBSOFT9_APPSTORE_SYNC_RETRY_ATTEMPTS", "2")))
try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover - bootstrap fallback
    dotenv_values = None

# Library .env files may contain Compose interpolation that python-dotenv does
# not parse. The values we need remain available, so avoid emitting one warning
# per unsupported line during normal Appstore synchronization.
logging.getLogger("dotenv.main").setLevel(logging.ERROR)


ENV_REFERENCE_PATTERN = re.compile(r"\$\{?(\w+)\}?")

# ── external database profile ─────────────────────────────────────────
# The library is retiring ``.env.external-db`` in favour of ``database[]``.
# Keep publishing the profile the install form already consumes.
EXTERNAL_DATABASE_PROFILE = "external-db"
# Shared dictionaries published next to the library manifest: (manifest entry, local file name).
SHARED_DICTIONARIES: tuple[tuple[str, str], ...] = (
    ("databaseTypes", "database-types.json"),
    ("secretRules", "secret-rules.json"),
)
EXTERNAL_DATABASE_SETTING_KEYS = (
    "W9_DB_HOST_SET",
    "W9_DB_PORT_SET",
    "W9_DB_NAME_SET",
    "W9_DB_USER_SET",
    "W9_DB_PASSWORD_SET",
)
EXTERNAL_DATABASE_DRIVERS = ("mysql", "mariadb", "postgresql")
EXTERNAL_DATABASE_PORTS = {"mysql": 3306, "mariadb": 3306, "postgresql": 5432}


# ── v2 manifest URL templates ──────────────────────────────────────────
_V2_APPSTORE_MANIFEST_PATH = "appstore/{channel}/manifests/appstore-manifest.json"
SUPPORTED_APPSTORE_SCHEMAS = {
    "root": frozenset({"1", "2"}),
    "catalog": frozenset({"1"}),
    "library": frozenset({"1", "2"}),
}
LOCAL_MANIFEST_SCHEMA = "1"


class AppStoreCompatibilityError(RuntimeError):
    """Raised when an App Store contract is not implemented by this runtime."""

    def __init__(self, message: str, *, upgrade_required: bool = False) -> None:
        super().__init__(message)
        self.upgrade_required = upgrade_required


class AppStoreManifestNotFoundError(RuntimeError):
    """Raised when a legacy artifact server has no root App Store manifest."""


class AppStoreTransientError(RuntimeError):
    """Raised for failures that another attempt may resolve.

    Publishing uploads with backup and rollback and serves objects with a 60s cache, so a
    mismatched or half-written dataset is usually a short-lived state: retrying after the cache
    window is the correct response, not falling back or aborting permanently.
    """


def _parse_version(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not value.strip():
        raise AppStoreCompatibilityError(f"invalid {label}: {value!r}")

    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?", value.strip())
    if not match:
        raise AppStoreCompatibilityError(f"invalid {label}: {value!r}")
    return tuple(int(part or 0) for part in match.groups())


def get_websoft9_version() -> str:
    version_path = Path(os.getenv("WEBSOFT9_VERSION_FILE", "/websoft9/version.json"))
    try:
        payload = json.loads(version_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppStoreCompatibilityError(f"failed to read Websoft9 version from {version_path}: {exc}") from exc

    version = payload.get("version") if isinstance(payload, dict) else None
    _parse_version(version, "Websoft9 version")
    return version.strip()


def check_appstore_compatibility(
    appstore_manifest: dict[str, object],
    local_schema_version: str | None = None,
    websoft9_version: str | None = None,
) -> None:
    check_schema_version(appstore_manifest.get("schemaVersion"), "root")
    if appstore_manifest["schemaVersion"] == "2":
        if "minWebsoft9Version" in appstore_manifest:
            raise AppStoreTransientError("root protocol 2 must not declare minWebsoft9Version")
        if appstore_manifest.get("channel") not in {"dev", "rc", "release"}:
            raise AppStoreTransientError("invalid root manifest channel")
        if not isinstance(appstore_manifest.get("datasetVersion"), str) or not re.fullmatch(
            r"[a-f0-9]{16}", appstore_manifest["datasetVersion"]
        ):
            raise AppStoreTransientError("invalid root manifest datasetVersion")
        for component in ("catalog", "library"):
            reference = appstore_manifest.get(component)
            if not isinstance(reference, dict):
                raise AppStoreTransientError(f"missing {component} declaration")
            check_schema_version(reference.get("schemaVersion"), component)
            if reference.get("manifest") != f"{component}/manifest.json":
                raise AppStoreTransientError(f"invalid {component} manifest path")
            version = reference.get("datasetVersion")
            if not isinstance(version, str) or not re.fullmatch(r"[a-f0-9]{16}", version):
                raise AppStoreTransientError(f"invalid {component} datasetVersion")
        return

    minimum_version = appstore_manifest.get("minWebsoft9Version")
    if minimum_version is None:
        return

    current_version = websoft9_version or get_websoft9_version()
    if _parse_version(current_version, "Websoft9 version") < _parse_version(minimum_version, "minWebsoft9Version"):
        raise AppStoreCompatibilityError(
            f"appstore requires Websoft9 >= {minimum_version}; current version is {current_version}. "
            "Please upgrade your Websoft9 platform.",
            upgrade_required=True,
        )


def check_schema_version(value: object, component: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        raise AppStoreTransientError(f"invalid {component} schemaVersion: {value!r}")
    if value not in SUPPORTED_APPSTORE_SCHEMAS[component]:
        raise AppStoreCompatibilityError(
            f"unsupported {component} schemaVersion {value!r}; supported: "
            f"{', '.join(sorted(SUPPORTED_APPSTORE_SCHEMAS[component]))}. "
            "The update was not applied. Check the Websoft9 compatibility and release notes."
        )


def log(message: str) -> None:
    print(message, flush=True)


def with_transient_retry(action, *, label: str):
    """Run ``action`` again after a transient App Store failure.

    The publisher backs up and rolls back, and every object is served with a 60 second cache, so
    the same request can succeed a minute later. Retrying is therefore correct, but retrying
    sooner only re-reads the same inconsistent object.
    """
    attempts = _APPSTORE_SYNC_RETRY_ATTEMPTS
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except AppStoreTransientError as exc:
            if attempt >= attempts:
                raise
            log(
                f"[platform-assets] {label} failed ({exc}); retrying in "
                f"{_APPSTORE_SYNC_RETRY_DELAY_SECONDS:g}s ({attempt}/{attempts - 1})"
            )
            time.sleep(_APPSTORE_SYNC_RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable")


def download_verified_json(url: str, checksum_url: str | None = None) -> object:
    """Download a manifest together with its published ``.sha256`` sibling.

    Old artifacts have no checksum sibling; that is not a failure, it just means the payload
    cannot be verified here.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "application/json,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise AppStoreTransientError(f"download failed for {url}: {exc}") from exc

    try:
        checksum_parts = download_text(checksum_url or f"{url}.sha256").split()
    except AppStoreTransientError as exc:
        if checksum_url is not None or not isinstance(exc.__cause__, urllib.error.HTTPError) or exc.__cause__.code != 404:
            raise
        expected = ""
    else:
        if not checksum_parts or not re.fullmatch(r"[0-9a-fA-F]{64}", checksum_parts[0]):
            raise AppStoreTransientError(f"invalid manifest checksum for {url}")
        expected = checksum_parts[0]
    if expected:
        actual = hashlib.sha256(payload).hexdigest()
        if actual.lower() != expected.lower():
            raise AppStoreTransientError(
                f"manifest checksum mismatch for {url}: expected {expected}, got {actual}"
            )

    try:
        result = json.loads(payload)
    except ValueError as exc:
        raise AppStoreTransientError(f"invalid manifest payload: {url}: {exc}") from exc
    if not expected and isinstance(result, dict) and result.get("schemaVersion") == "2":
        raise AppStoreTransientError(f"missing required manifest checksum for {url}")
    return result


def verbose_log(message: str) -> None:
    if (os.getenv("WEBSOFT9_RUNTIME_ASSET_VERBOSE") or "").strip().lower() in {"1", "true", "yes", "on"}:
        log(message)


def detect_channel() -> str:
    explicit_channel = (os.getenv("WEBSOFT9_RUNTIME_ASSET_CHANNEL") or "").strip().lower()
    if explicit_channel in {"release", "dev"}:
        return explicit_channel

    version_file = Path("/websoft9/version.json")
    if not version_file.exists():
        return "release"

    try:
        payload = json.loads(version_file.read_text(encoding="utf-8"))
    except Exception:
        return "release"

    channel = str(payload.get("channel") or "").strip().lower()
    if channel in {"release", "dev"}:
        return channel

    version = payload.get("version", "")

    normalized_version = version.lower()
    if "-dev" in normalized_version:
        return "dev"
    return "release"


def resolve_package_name(channel: str, package_type: str) -> str:
    package_env_map = {
        "media": "WEBSOFT9_MEDIA_PACKAGE",
        "library": "WEBSOFT9_LIBRARY_PACKAGE",
    }
    env_name = package_env_map[package_type]
    default_name = f"{package_type}-dev.zip" if channel == "dev" else f"{package_type}-latest.zip"
    return os.getenv(env_name, default_name)


def marker_exists(marker_path: Path, package_type: str) -> bool:
    if package_type == "library":
        return marker_path.exists() and any(marker_path.iterdir())
    return marker_path.exists()


_UPLOADED_MEDIA_FILENAME_RE = re.compile(r"[0-9a-f]{32}(?:\.[A-Za-z0-9_-]{1,16})?")


def _is_uploaded_media_file(path: Path, root: Path) -> bool:
    """Report whether ``path`` is an operator-uploaded file inside a shared media root."""
    return (
        path.parent == root
        and not path.is_symlink()
        and path.is_file()
        and _UPLOADED_MEDIA_FILENAME_RE.fullmatch(path.name) is not None
    )


def _reset_directory(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def sync_tree(source: Path, target: Path, *, exclude_uploaded_media: bool = False) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if exclude_uploaded_media and _is_uploaded_media_file(item, source):
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


# App Store manifests are generated locally, so they are never part of a downloaded package.
# Replacing a runtime tree would therefore expose a window where /media/json/app-store-manifest_*.json
# does not exist, which makes the App Store look unavailable to the console and the API.
_GENERATED_MANIFEST_FILENAMES = ("app-store-manifest_zh.json", "app-store-manifest_en.json")


def preserve_generated_manifests(root: Path) -> dict[str, bytes]:
    preserved: dict[str, bytes] = {}
    for name in _GENERATED_MANIFEST_FILENAMES:
        try:
            preserved[name] = (root / "json" / name).read_bytes()
        except OSError:
            continue
    return preserved


def preserve_uploaded_media_files(root: Path) -> dict[str, bytes]:
    preserved: dict[str, bytes] = {}
    if not root.is_dir():
        return preserved
    for item in root.iterdir():
        if not _is_uploaded_media_file(item, root):
            continue
        try:
            preserved[item.name] = item.read_bytes()
        except OSError:
            continue
    return preserved


def restore_generated_manifests(root: Path, preserved: dict[str, bytes]) -> None:
    if not preserved:
        return
    json_dir = root / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in preserved.items():
        target = json_dir / name
        if target.exists():
            continue
        temporary_path = json_dir / f".{name}.tmp"
        temporary_path.write_bytes(payload)
        os.replace(temporary_path, target)


def restore_uploaded_media_files(root: Path, preserved: dict[str, bytes]) -> None:
    if not preserved:
        return
    root.mkdir(parents=True, exist_ok=True)
    for name, payload in preserved.items():
        target = root / name
        if target.exists():
            continue
        temporary_path = root / f".{name}.tmp"
        temporary_path.write_bytes(payload)
        os.replace(temporary_path, target)


def replace_tree_preserving_generated_manifests(source: Path, target: Path) -> None:
    """Replace a runtime tree without ever exposing a missing published manifest.

    The previously published manifests are written back before the payload is copied in, so the
    App Store stays readable for the whole replacement instead of failing until the manifests are
    rebuilt at the end of the sync.
    """
    target_dir = target.resolve() if target.is_symlink() else target
    preserved = preserve_generated_manifests(source) or preserve_generated_manifests(target_dir)
    is_media_tree = (source / "json").is_dir() or (target_dir / "json").is_dir()
    uploaded = preserve_uploaded_media_files(target_dir) if is_media_tree else {}

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    restore_generated_manifests(target_dir, preserved)
    restore_uploaded_media_files(target_dir, uploaded)
    sync_tree(source, target_dir)


def _hardlink_or_copy_file(source: str, destination: str, *, follow_symlinks: bool = True) -> str:
    """Hard-link a file when both paths live on the same filesystem, otherwise copy it."""
    try:
        os.link(source, destination, follow_symlinks=follow_symlinks)
        return destination
    except OSError:
        return shutil.copy2(source, destination, follow_symlinks=follow_symlinks)


def link_or_copy_tree(source: Path, target: Path, *, exclude_uploaded_media: bool = False) -> None:
    """Materialise a tree with hard links where possible.

    Snapshot copies inside the App Store root share file contents instead of duplicating
    hundreds of megabytes on every sync.  Cross-device targets (for example the data volume)
    transparently fall back to real copies.
    """
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if exclude_uploaded_media and _is_uploaded_media_file(item, source):
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True, copy_function=_hardlink_or_copy_file)
        else:
            _hardlink_or_copy_file(str(item), str(destination))


def replace_tree_linked(source: Path, target: Path, *, exclude_uploaded_media: bool = False) -> None:
    """Replace a tree, linking file contents instead of copying them when possible."""
    target_dir = target.resolve() if target.is_symlink() else target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    link_or_copy_tree(source, target_dir, exclude_uploaded_media=exclude_uploaded_media)


def replace_tree(source: Path, target: Path) -> None:
    target_dir = target.resolve() if target.is_symlink() else target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    sync_tree(source, target_dir)


def replace_media_tree(source: Path, target: Path) -> None:
    target_dir = target.resolve() if target.is_symlink() else target
    uploaded = preserve_uploaded_media_files(target_dir)
    replace_tree(source, target)
    restore_uploaded_media_files(target_dir, uploaded)


def backup_trees(targets: list[Path], backup_root: Path) -> dict[Path, Path | None]:
    backups: dict[Path, Path | None] = {}
    for index, target in enumerate(targets):
        if target.exists():
            backup_path = backup_root / str(index)
            # Linking the rollback copy keeps the safety net without duplicating hundreds of
            # megabytes; cross-device trees still fall back to a real copy.
            replace_tree_linked(target, backup_path)
            backups[target] = backup_path
        else:
            backups[target] = None
    return backups


def restore_trees(backups: dict[Path, Path | None]) -> None:
    for target, backup_path in backups.items():
        target_dir = target.resolve() if target.is_symlink() else target
        if target_dir.exists():
            shutil.rmtree(target_dir)
        if backup_path is not None:
            replace_tree_preserving_generated_manifests(backup_path, target_dir)


def extract_sync_root(extract_dir: Path, package_type: str) -> Path:
    direct_child = extract_dir / package_type
    if direct_child.exists():
        return direct_child

    children = list(extract_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]

    return extract_dir


def extract_zip_with_permissions(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            extracted_path = Path(archive.extract(member, destination))
            mode = (member.external_attr >> 16) & 0o7777
            if not mode:
                continue

            try:
                os.chmod(extracted_path, mode)
            except OSError:
                continue


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "application/zip,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        # A truncated or proxied artifact is retryable; the caller re-downloads and verifies again.
        raise AppStoreTransientError(f"download failed for {url}: {exc}") from exc


def download_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "application/json,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise AppStoreTransientError(f"download failed for {url}: {exc}") from exc


def download_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "text/plain,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise AppStoreTransientError(f"download failed for {url}: {exc}") from exc


def resolve_json_url(base_url: str, relative_path: str) -> str:
    """Resolve a relative path against a manifest URL.

    urljoin treats base_url as a file when the path does not end with /,
    automatically stripping the last component before resolution.
    """
    return urllib.request.urljoin(base_url, relative_path)


def acquire_appstore_sync_lock(data_root: Path):
    """Take the cross-process Appstore sync lock.

    The caller keeps the returned handle open until its transaction finishes, so two syncs can
    never rewrite the same media/library trees at the same time.  ``None`` means another sync
    holds the lock (the caller should skip this round instead of queueing behind it).
    """
    lock_path = Path(
        os.getenv("WEBSOFT9_APPSTORE_SYNC_LOCK_FILE", str(Path(data_root) / "config" / "appstore_sync.lock"))
    )
    try:
        wait_seconds = float(os.getenv("WEBSOFT9_APPSTORE_SYNC_LOCK_WAIT", "0") or 0)
    except ValueError:
        wait_seconds = 0.0

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    deadline = time.monotonic() + max(wait_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(_APPSTORE_SYNC_LOCK_POLL_SECONDS)


def clear_appstore_sync_pid_marker(pid_file: Path) -> None:
    try:
        if pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pid_file.unlink(missing_ok=True)
    except OSError:
        pass


def write_appstore_sync_pid_marker() -> Path | None:
    """Publish this sync's PID so the console can report a running synchronization."""
    pid_file = Path(os.getenv("WEBSOFT9_APPSTORE_SYNC_PID_FILE", _APPSTORE_SYNC_PID_FILE_DEFAULT))
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return None
    atexit.register(clear_appstore_sync_pid_marker, pid_file)
    return pid_file


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_checksum_value(base_url: str, relative_path: str) -> str:
    checksum_payload = download_text(resolve_json_url(base_url, relative_path)).strip()
    checksum_value = checksum_payload.split()[0] if checksum_payload else ""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum_value):
        raise RuntimeError(f"invalid checksum payload: {relative_path}")
    return checksum_value.lower()


def verify_downloaded_file_checksum(base_url: str, relative_path: str, checksum_relative: str, file_path: Path) -> None:
    expected_checksum = resolve_checksum_value(base_url, checksum_relative)
    actual_checksum = compute_sha256(file_path)
    if actual_checksum.lower() != expected_checksum:
        # A half-written object is exactly what the publisher's rollback repairs; treat it as
        # retryable instead of aborting the whole synchronization.
        raise AppStoreTransientError(
            f"checksum mismatch for {relative_path}: expected {expected_checksum}, got {actual_checksum}"
        )


def load_sync_state(state_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log(f"[platform-assets] cannot read sync state {state_path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        log(f"[platform-assets] sync state is not an object: {state_path}")
        return {}
    return payload


def write_sync_state(state_path: Path, payload: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_name(f".{state_path.name}.tmp")
    try:
        temporary.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")
        os.replace(temporary, state_path)
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_manifest_domains(appstore_manifest: dict[str, object], manifest_url: str) -> tuple[str, str]:
    """Resolve catalog/library manifest paths from appstore manifest.

    Supports both v2 spec format (catalog.manifest / library.manifest) and
    legacy format (domains.catalog / domains.library).
    """
    # v2 spec: { "catalog": { "manifest": "..." }, "library": { "manifest": "..." } }
    catalog = appstore_manifest.get("catalog")
    library = appstore_manifest.get("library")
    if isinstance(catalog, dict) and isinstance(library, dict):
        catalog_rel = catalog.get("manifest")
        library_rel = library.get("manifest")
        for block in (catalog, library):
            if "manifest" in block and (not isinstance(block["manifest"], str) or not block["manifest"].strip()):
                raise AppStoreTransientError(f"invalid component manifest path: {manifest_url}")
        if isinstance(catalog_rel, str) and isinstance(library_rel, str) and catalog_rel and library_rel:
            return catalog_rel, library_rel

    # Legacy: { "domains": { "catalog": "...", "library": "..." } }
    domains = appstore_manifest.get("domains")
    if isinstance(domains, dict):
        catalog_rel = domains.get("catalog")
        library_rel = domains.get("library")
        if isinstance(catalog_rel, str) and isinstance(library_rel, str):
            return catalog_rel, library_rel

    raise AppStoreTransientError(f"appstore manifest has unrecognized structure: {manifest_url}")


def _resolve_sync_state_path() -> Path:
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    return Path(os.getenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(Path(data_root) / "config" / "appstore_sync_state.json")))


def _local_runtime_trees_match_state(previous_state: dict[str, object] | None) -> bool:
    """Verify that the container's runtime trees still match the persisted sync state.

    The sync state file lives on the persistent host volume (/opt/websoft9/data), while
    /websoft9/library lives inside the container rootfs. When a
    container is recreated or upgraded from an image, the container rootfs reverts to the
    image build-time baseline even though the host sync state still records a newer dataset.
    """
    if not isinstance(previous_state, dict) or not previous_state:
        return False
    if "assetDigests" in previous_state:
        digests = previous_state["assetDigests"]
        if not isinstance(digests, dict):
            return False
        try:
            for kind in ("media", "library"):
                root = Path(os.getenv(f"WEBSOFT9_{kind.upper()}_ROOT", f"/websoft9/{kind}"))
                if tree_content_fingerprint(root) != digests.get(kind):
                    return False
        except (OSError, ValueError, RuntimeError):
            return False

    snapshots = previous_state.get("snapshots")
    if isinstance(snapshots, dict) and snapshots:
        for package_snapshots in snapshots.values():
            if not isinstance(package_snapshots, dict):
                continue
            release_dir = package_snapshots.get("release") or package_snapshots.get("current")
            if isinstance(release_dir, str) and release_dir.strip() and not Path(release_dir.strip()).exists():
                return False

    snapshot_root_raw = previous_state.get("snapshotRoot")
    dataset_version_raw = previous_state.get("datasetVersion")
    if (
        isinstance(snapshot_root_raw, str)
        and snapshot_root_raw.strip()
        and isinstance(dataset_version_raw, str)
        and dataset_version_raw.strip()
    ):
        release_root = Path(snapshot_root_raw.strip()) / "releases" / dataset_version_raw.strip()
        if not release_root.exists():
            return False

    library_dsv = previous_state.get("libraryDatasetVersion")
    if isinstance(library_dsv, str) and library_dsv.strip():
        library_root = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
        apps_index_path = library_root / "apps-index.json"
        if apps_index_path.is_file():
            try:
                index_payload = json.loads(apps_index_path.read_text(encoding="utf-8"))
                index_dsv = index_payload.get("datasetVersion") if isinstance(index_payload, dict) else None
                if isinstance(index_dsv, str) and index_dsv.strip() and index_dsv.strip() != library_dsv.strip():
                    return False
            except (OSError, json.JSONDecodeError):
                return False

    return True


def _appstore_dataset_already_active(
    appstore_manifest: dict[str, object],
    previous_state: dict[str, object] | None,
    force_refresh: bool,
    component_manifests: dict[str, object] | None = None,
) -> bool:
    """Report whether the remote dataset is already active locally.

    The root manifest carries the dataset and per-component versions, so an unchanged dataset
    can be detected without downloading the catalog/library manifests at all.
    """
    if force_refresh:
        return False
    if not isinstance(previous_state, dict) or not previous_state:
        return False
    if previous_state.get("partial"):
        return False
    if not _local_runtime_trees_match_state(previous_state):
        return False

    latest_dataset_version = appstore_manifest.get("datasetVersion")
    if not latest_dataset_version or previous_state.get("datasetVersion") != latest_dataset_version:
        return False

    previous_schema_version = previous_state.get("schemaVersion")
    latest_schema_version = appstore_manifest.get("schemaVersion")
    if previous_schema_version and latest_schema_version and previous_schema_version != latest_schema_version:
        return False

    latest_catalog_dsv = _resolve_component_dataset_version(appstore_manifest, "catalog")
    latest_library_dsv = _resolve_component_dataset_version(appstore_manifest, "library")
    cached_manifests = previous_state.get("manifests", {})
    for component in ("catalog", "library"):
        reference = appstore_manifest.get(component, {})
        schema = reference.get("schemaVersion") if isinstance(reference, dict) else None
        if schema is None:
            manifest = (component_manifests or {}).get(f"{component}_manifest")
            if not isinstance(manifest, dict):
                return False
            schema = manifest.get("schemaVersion")
        previous_schema = previous_state.get(f"{component}SchemaVersion")
        if schema != previous_schema:
            return False
        if not isinstance(cached_manifests, dict) or not isinstance(cached_manifests.get(component), dict):
            return False
        _validate_component_version(
            appstore_manifest, component, cached_manifests[component], appstore_manifest.get("channel")
        )
    catalog_unchanged = (not latest_catalog_dsv) or latest_catalog_dsv == previous_state.get("catalogDatasetVersion")
    library_unchanged = (not latest_library_dsv) or latest_library_dsv == previous_state.get("libraryDatasetVersion")
    return bool(catalog_unchanged and library_unchanged)


def fetch_appstore_manifests(
    artifact_base: str,
    channel: str,
    local_schema_version: str | None,
    previous_state: dict[str, object] | None = None,
    force_refresh: bool | None = None,
) -> dict[str, object]:
    """Download the App Store manifests for a channel.

    ``previous_state``/``force_refresh`` default to the runtime sync state and the
    ``WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC`` flag so callers keep the simple three-argument form.
    """
    if previous_state is None:
        previous_state = load_sync_state(_resolve_sync_state_path())
    if force_refresh is None:
        force_refresh = is_force_refresh_enabled()

    appstore_manifest_url = f"{artifact_base}/{_V2_APPSTORE_MANIFEST_PATH.format(channel=channel)}"
    try:
        appstore_manifest = download_verified_json(appstore_manifest_url)
    except AppStoreTransientError as exc:
        if (
            isinstance(exc.__cause__, urllib.error.HTTPError)
            and exc.__cause__.code == 404
            and exc.__cause__.geturl() == appstore_manifest_url
        ):
            raise AppStoreManifestNotFoundError(appstore_manifest_url) from exc
        raise
    if not isinstance(appstore_manifest, dict):
        raise AppStoreTransientError(f"invalid appstore manifest payload: {appstore_manifest_url}")
    if "channel" in appstore_manifest and appstore_manifest["channel"] != channel:
        raise AppStoreTransientError(f"appstore manifest channel does not match {channel}")

    check_appstore_compatibility(appstore_manifest, local_schema_version)

    # Fast path: when the dataset is already active, the component manifests (and the apps
    # index that only feeds the manifest builder) carry no new information.  Each of those
    # requests costs a full round trip to the artifact server, which dominates start-up time.
    if _appstore_dataset_already_active(appstore_manifest, previous_state, force_refresh) and isinstance(
        previous_state["manifests"].get("appsIndex"), dict
    ):
        log(
            "[platform-assets] appstore dataset "
            f"{appstore_manifest.get('datasetVersion')} already active; component manifests not requested"
        )
        catalog_relative, library_relative = _resolve_manifest_domains(appstore_manifest, appstore_manifest_url)
        bundle: dict[str, object] = {
            "appstore_manifest_url": appstore_manifest_url,
            "catalog_manifest_url": f"{artifact_base}/appstore/{channel}/{catalog_relative}",
            "library_manifest_url": f"{artifact_base}/appstore/{channel}/{library_relative}",
            "appstore_manifest": appstore_manifest,
            "catalog_manifest": previous_state["manifests"]["catalog"],
            "library_manifest": previous_state["manifests"]["library"],
            "componentManifestsSkipped": True,
        }
        bundle["_verified_library_json"] = {"appsIndex": previous_state["manifests"]["appsIndex"]}
        # An unchanged dataset can still need dictionary repair.
        library_root = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
        if _dictionary_repair_needed(library_root, previous_state) or _dictionary_repair_needed(
            library_root, previous_state, "secretRules", "secret-rules.json", known_only=True
        ):
            catalog_relative, library_relative = _resolve_manifest_domains(appstore_manifest, appstore_manifest_url)
            for component, relative in (("catalog", catalog_relative), ("library", library_relative)):
                url = f"{artifact_base}/appstore/{channel}/{relative}"
                manifest = download_verified_json(url, f"{url}.sha256") if appstore_manifest["schemaVersion"] == "2" else download_verified_json(url)
                _validate_component_version(appstore_manifest, component, manifest, channel)
                bundle[f"{component}_manifest_url"] = url
                bundle[f"{component}_manifest"] = manifest
            log("[platform-assets] local shared dictionary needs repair; verified component manifests requested")
        return bundle

    catalog_relative, library_relative = _resolve_manifest_domains(appstore_manifest, appstore_manifest_url)

    # Sub-manifest paths (e.g. "catalog/manifest.json") are relative to the
    # appstore channel root, NOT to the root manifest URL (which lives under
    # manifests/).  Construct the absolute URLs from the channel base.
    appstore_base = f"{artifact_base}/appstore/{channel}"
    catalog_manifest_url = f"{appstore_base}/{catalog_relative}"
    library_manifest_url = f"{appstore_base}/{library_relative}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        def fetch_component(url: str) -> object:
            if appstore_manifest["schemaVersion"] == "2":
                return download_verified_json(url, f"{url}.sha256")
            return download_verified_json(url)

        catalog_future = executor.submit(fetch_component, catalog_manifest_url)
        library_future = executor.submit(fetch_component, library_manifest_url)
        catalog_manifest = catalog_future.result()
        library_manifest = library_future.result()
    _validate_component_version(appstore_manifest, "catalog", catalog_manifest, channel)
    _validate_component_version(appstore_manifest, "library", library_manifest, channel)

    bundle = {
        "appstore_manifest_url": appstore_manifest_url,
        "catalog_manifest_url": catalog_manifest_url,
        "library_manifest_url": library_manifest_url,
        "appstore_manifest": appstore_manifest,
        "catalog_manifest": catalog_manifest,
        "library_manifest": library_manifest,
    }
    if appstore_manifest["schemaVersion"] == "2":
        for entry_key, _ in SHARED_DICTIONARIES:
            if library_dictionary_entry(bundle, entry_key) is None:
                raise AppStoreTransientError(f"missing required {entry_key} declaration")
    return bundle


def fetch_delta_payload(base_manifest_url: str, relative_path: str | None) -> dict[str, object] | None:
    if not isinstance(relative_path, str) or not relative_path:
        return None

    payload = download_json(resolve_json_url(base_manifest_url, relative_path))
    return payload if isinstance(payload, dict) else None


def delta_payload_has_changes(payload: dict[str, object] | None, keys: tuple[str, ...]) -> bool:
    if payload is None:
        return True

    mode = payload.get("mode")
    if mode == "bootstrap":
        return True

    for key in keys:
        value = payload.get(key)
        if isinstance(value, list) and len(value) > 0:
            return True

    return False


def delta_payload_matches_version_chain(
    payload: dict[str, object] | None,
    previous_dataset_version: object,
    latest_dataset_version: object,
) -> bool:
    if payload is None:
        return False

    from_version = payload.get("fromVersion")
    to_version = payload.get("toVersion")
    return from_version == previous_dataset_version and to_version == latest_dataset_version


def delta_payload_string_list(payload: dict[str, object] | None, key: str) -> list[str]:
    if payload is None:
        return []

    value = payload.get(key)
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str) and item]


def resolve_library_delta_context(
    manifest_bundle: dict[str, object] | None,
    previous_dataset_version: object,
    latest_dataset_version: object,
) -> dict[str, object] | None:
    if not manifest_bundle:
        return None

    library_manifest = manifest_bundle.get("library_manifest")
    library_manifest_url = str(manifest_bundle.get("library_manifest_url", ""))
    if not isinstance(library_manifest, dict):
        return None

    # ── v2 spec: single appsDelta file with all change lists ─────────
    apps_delta_relative = library_manifest.get("appsDelta")
    if "appsDelta" in library_manifest:
        apps_delta = _fetch_library_json(manifest_bundle, "appsDelta")
        if delta_payload_matches_version_chain(apps_delta, previous_dataset_version, latest_dataset_version):
            return {
                "appsDelta": apps_delta or {},
                "changedApps": sorted(set(delta_payload_string_list(apps_delta, "changedApps"))),
                "addedApps": sorted(set(delta_payload_string_list(apps_delta, "addedApps"))),
                "removedApps": sorted(set(delta_payload_string_list(apps_delta, "removedApps"))),
                "updatedApps": sorted(set(delta_payload_string_list(apps_delta, "changedApps"))),
            }
        # Version chain mismatch – delta can't be applied; caller will fall back to full sync
        return None

    # ── Legacy: deltaFiles.library + deltaFiles.apps ─────────────────
    delta_files = library_manifest.get("deltaFiles")
    if not isinstance(delta_files, dict):
        return None

    library_delta = fetch_delta_payload(library_manifest_url, delta_files.get("library") if isinstance(delta_files.get("library"), str) else None)
    apps_delta = fetch_delta_payload(library_manifest_url, delta_files.get("apps") if isinstance(delta_files.get("apps"), str) else None)

    if not delta_payload_matches_version_chain(library_delta, previous_dataset_version, latest_dataset_version):
        return None
    if not delta_payload_matches_version_chain(apps_delta, previous_dataset_version, latest_dataset_version):
        return None

    return {
        "libraryDelta": library_delta or {},
        "appsDelta": apps_delta or {},
        "changedApps": sorted(set(delta_payload_string_list(library_delta, "changedApps"))),
        "addedApps": sorted(set(delta_payload_string_list(apps_delta, "addedApps"))),
        "removedApps": sorted(set(delta_payload_string_list(apps_delta, "removedApps"))),
        "updatedApps": sorted(set(delta_payload_string_list(apps_delta, "changedApps"))),
    }


def resolve_library_apps_index(manifest_bundle: dict[str, object] | None) -> dict[str, dict[str, object]]:
    if not manifest_bundle:
        return {}

    library_manifest = manifest_bundle.get("library_manifest")
    if not isinstance(library_manifest, dict):
        return {}

    # ── v2 spec: supportsPartialUpdate ──────────────────────────────
    if library_manifest.get("supportsPartialUpdate") is not True:
        # Legacy: compatibility.appLevelArtifacts
        compatibility = library_manifest.get("compatibility")
        if not isinstance(compatibility, dict) or compatibility.get("appLevelArtifacts") is not True:
            return {}

    payload = fetch_library_apps_index_payload(manifest_bundle)
    if payload is None:
        return {}

    apps = payload.get("apps")
    if not isinstance(apps, list):
        return {}

    app_map: dict[str, dict[str, object]] = {}
    for item in apps:
        if not isinstance(item, dict):
            continue
        # v2 spec uses "app" key; legacy may use "key"
        key = item.get("app") or item.get("key")
        if isinstance(key, str) and key:
            # Normalize v2 per-app package/checksum entries into legacy bundle shape
            # so sync_library_app_artifacts_delta can consume both formats.
            normalized = dict(item)
            if "package" in normalized and "bundle" not in normalized:
                pkg = normalized.get("package")
                if isinstance(pkg, dict):
                    normalized["bundle"] = pkg.get("latest")
            if "checksum" in normalized:
                chk = normalized.get("checksum")
                if isinstance(chk, dict) and "bundle" not in chk:
                    normalized["checksum"] = {**chk, "bundle": chk.get("latest")}
            app_map[key] = normalized

    return app_map


def _resolve_component_dataset_version(appstore_manifest: dict[str, object], component: str) -> object:
    """Extract per-component datasetVersion from v2 appstore manifest."""
    block = appstore_manifest.get(component)
    if component in appstore_manifest and not isinstance(block, dict):
        raise AppStoreTransientError(f"invalid {component} declaration")
    if isinstance(block, dict):
        if "datasetVersion" in block:
            value = block["datasetVersion"]
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise AppStoreTransientError(f"invalid {component} datasetVersion: {value!r}")
            return value
    return None


def _validate_component_version(root: dict[str, object], component: str, manifest: object, channel: str | None = None) -> None:
    if not isinstance(manifest, dict):
        raise AppStoreTransientError(f"invalid {component} manifest payload")
    if root.get("schemaVersion") == "2":
        reference = root.get(component, {})
        if manifest.get("schemaVersion") != reference.get("schemaVersion"):
            raise AppStoreTransientError(f"{component} manifest schemaVersion does not match the root declaration")
        for key in ("fullPackage", "appsIndex", "appsDelta") if component == "library" else ("fullPackage",):
            if not isinstance(manifest.get(key), str) or not manifest[key]:
                raise AppStoreTransientError(f"missing {component} {key}")
            checksums = manifest.get("checksum")
            if not isinstance(checksums, dict) or not isinstance(checksums.get(key), str) or not checksums[key].strip():
                raise AppStoreTransientError(f"missing {component} {key} checksum")
        if component == "library" and not isinstance(manifest.get("supportsPartialUpdate"), bool):
            raise AppStoreTransientError("missing library supportsPartialUpdate")
    check_schema_version(manifest.get("schemaVersion"), component)
    expected = _resolve_component_dataset_version(root, component)
    expected_channel = channel or root.get("channel")
    if "channel" in manifest and expected_channel is not None and manifest["channel"] != expected_channel:
        raise AppStoreTransientError(f"{component} manifest channel does not match {expected_channel}")
    if "datasetVersion" not in manifest:
        if expected is not None:
            raise AppStoreTransientError(f"missing {component} manifest datasetVersion")
        return
    actual = manifest["datasetVersion"]
    if not isinstance(actual, str) or not actual.strip() or actual != actual.strip():
        raise AppStoreTransientError(f"invalid {component} manifest datasetVersion: {actual!r}")
    if expected is not None and actual != expected:
        raise AppStoreTransientError(
            f"{component} manifest datasetVersion {actual} does not match the root manifest {expected}"
        )


def determine_package_sync_plan(manifest_bundle: dict[str, object] | None, previous_state: dict[str, object], latest_dataset_version: object) -> dict[str, bool]:
    plan = {
        "media": True,
        "library": True,
    }

    if not manifest_bundle:
        return plan

    if not latest_dataset_version:
        return plan

    previous_root_dsv = previous_state.get("datasetVersion")
    if previous_root_dsv in {None, ""}:
        return plan

    appstore_manifest = manifest_bundle.get("appstore_manifest")
    if not isinstance(appstore_manifest, dict):
        return plan

    # ── v2: use per-component datasetVersions when available ──────
    catalog_dsv = _resolve_component_dataset_version(appstore_manifest, "catalog")
    library_dsv = _resolve_component_dataset_version(appstore_manifest, "library")

    previous_catalog_dsv = previous_state.get("catalogDatasetVersion")
    previous_library_dsv = previous_state.get("libraryDatasetVersion")

    # media / catalog
    if catalog_dsv is not None and previous_catalog_dsv is not None:
        if catalog_dsv == previous_catalog_dsv:
            plan["media"] = False

    # library
    if library_dsv is not None and previous_library_dsv is not None:
        if library_dsv == previous_library_dsv:
            plan["library"] = False
    elif library_dsv is not None and previous_root_dsv == latest_dataset_version:
        # No per-component history yet – root hasn't changed either
        plan["library"] = False

    # If v2 detection couldn't determine no-change, fall through to
    # delta-based detection (legacy or v2 appsDelta).
    if plan["library"]:
        # ``appsDelta`` is expressed in *library* dataset versions, so the chain has to be
        # checked against them. Older state files only record the root Appstore version;
        # fall back to it so those installations keep their previous behaviour.
        previous_library_version = previous_state.get("libraryDatasetVersion") or previous_root_dsv
        latest_library_version = library_dsv if library_dsv is not None else latest_dataset_version
        library_delta_context = resolve_library_delta_context(
            manifest_bundle, previous_library_version, latest_library_version
        )
        if library_delta_context is not None:
            apps_delta = library_delta_context.get("appsDelta", {})
            if isinstance(apps_delta, dict) and not delta_payload_has_changes(apps_delta, ("addedApps", "removedApps", "changedApps")):
                plan["library"] = False

    if plan["media"]:
        # Legacy catalog delta detection
        catalog_manifest = manifest_bundle.get("catalog_manifest")
        catalog_manifest_url = str(manifest_bundle.get("catalog_manifest_url", ""))
        if isinstance(catalog_manifest, dict):
            delta_files = catalog_manifest.get("deltaFiles")
            if isinstance(delta_files, dict):
                catalog_delta_payload = fetch_delta_payload(catalog_manifest_url, delta_files.get("catalog"))
                product_delta_payload = fetch_delta_payload(catalog_manifest_url, delta_files.get("product"))
                if (
                    delta_payload_matches_version_chain(catalog_delta_payload, previous_root_dsv, latest_dataset_version)
                    and delta_payload_matches_version_chain(product_delta_payload, previous_root_dsv, latest_dataset_version)
                    and not delta_payload_has_changes(catalog_delta_payload, ("addedKeys", "removedKeys", "changedKeys"))
                    and not delta_payload_has_changes(product_delta_payload, ("addedKeys", "removedKeys", "changedKeys"))
                ):
                    plan["media"] = False

    return plan


def library_requires_full_sync(
    manifest_bundle: dict[str, object], previous_state: dict[str, object], library_root: Path
) -> bool:
    manifest = manifest_bundle.get("library_manifest", {})
    if not isinstance(manifest, dict):
        return True
    if manifest.get("supportsPartialUpdate") is False:
        return True
    previous_schema = previous_state.get("librarySchemaVersion")
    if previous_schema is None:
        try:
            index = json.loads((library_root / "apps-index.json").read_bytes())
        except (OSError, ValueError):
            return True
        if not isinstance(index, dict) or index.get("datasetVersion") != previous_state.get("libraryDatasetVersion"):
            return True
        previous_schema = index.get("schemaVersion")
    return previous_schema != manifest.get("schemaVersion")


def load_library_apps_index(library_root: Path) -> dict[str, str]:
    """Map each app key to the update time published in the library apps index.

    The index is optional metadata: anything missing or malformed is ignored so it can never
    block a manifest build.
    """
    index_path = library_root / "apps-index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    apps = payload.get("apps") if isinstance(payload, dict) else None
    if not isinstance(apps, list):
        return {}

    updated_at_by_key: dict[str, str] = {}
    for item in apps:
        if not isinstance(item, dict):
            continue
        key = item.get("app") or item.get("key")
        updated_at = item.get("updatedAt")
        if isinstance(key, str) and key.strip() and isinstance(updated_at, str) and updated_at.strip():
            updated_at_by_key[key.strip()] = updated_at.strip()
    return updated_at_by_key


def fetch_library_apps_index_payload(manifest_bundle: dict[str, object] | None) -> dict[str, object] | None:
    """Download the published apps index verbatim so it can be persisted locally."""
    if not manifest_bundle:
        return None
    return _fetch_library_json(manifest_bundle, "appsIndex")


def _valid_app_key(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value) is not None


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _validate_apps_index(payload: dict[str, object], *, strict: bool) -> dict[str, str]:
    apps = payload.get("apps")
    if not isinstance(apps, list):
        raise AppStoreTransientError("invalid appsIndex apps")
    hashes: dict[str, str] = {}
    seen: set[str] = set()
    for item in apps:
        if not isinstance(item, dict):
            raise AppStoreTransientError("invalid appsIndex app metadata")
        key = item.get("app") or item.get("key")
        if not _valid_app_key(key) or key in seen:
            raise AppStoreTransientError(f"invalid or duplicate appsIndex app: {key!r}")
        seen.add(key)
        if strict or "hash" in item:
            if not _valid_hash(item.get("hash")):
                raise AppStoreTransientError(f"invalid appsIndex hash for {key}")
            hashes[key] = item["hash"].lower()
        if strict:
            for field in ("package", "checksum"):
                entry = item.get(field)
                if not isinstance(entry, dict) or not isinstance(entry.get("latest"), str) or not entry["latest"].strip() or entry["latest"] != entry["latest"].strip():
                    raise AppStoreTransientError(f"missing appsIndex {field}.latest for {key}")
    return hashes


def _fetch_library_json(manifest_bundle: dict[str, object], key: str) -> dict[str, object] | None:
    library_manifest = manifest_bundle.get("library_manifest")
    if not isinstance(library_manifest, dict) or key not in library_manifest:
        return None
    cache = manifest_bundle.setdefault("_verified_library_json", {})
    base_url = manifest_bundle.get("library_manifest_url")
    relative = library_manifest[key]
    if not isinstance(base_url, str) or not base_url or not isinstance(relative, str) or not relative:
        raise AppStoreTransientError(f"invalid declared {key} path")
    strict = "supportsPartialUpdate" in library_manifest
    if strict and not isinstance(library_manifest["supportsPartialUpdate"], bool):
        raise AppStoreTransientError("invalid supportsPartialUpdate declaration")
    checksums = library_manifest.get("checksum", {})
    if not isinstance(checksums, dict):
        raise AppStoreTransientError("invalid library checksum declaration")
    checksum_url = None
    if key in checksums:
        checksum = checksums[key]
        if not isinstance(checksum, str) or not checksum:
            raise AppStoreTransientError(f"invalid declared {key} checksum path")
        checksum_url = resolve_json_url(base_url, checksum)
    elif strict:
        raise AppStoreTransientError(f"missing declared {key} checksum")
    url = resolve_json_url(base_url, relative)
    payload = cache.get(key)
    if key not in cache:
        payload = with_transient_retry(
            lambda: download_verified_json(url, checksum_url) if checksum_url is not None else download_verified_json(url),
            label=f"library {key} fetch",
        )
    if not isinstance(payload, dict):
        raise AppStoreTransientError(f"invalid {key} payload")
    root = manifest_bundle.get("appstore_manifest") or {}
    expected_version = library_manifest.get("datasetVersion") or _resolve_component_dataset_version(root, "library")
    channel = root.get("channel") or library_manifest.get("channel")
    if channel is None:
        match = re.search(r"/appstore/(release|dev)/", base_url)
        channel = match.group(1) if match else None
    for field, expected in (("channel", channel), ("datasetVersion" if key == "appsIndex" else "toVersion", expected_version)):
        if field in payload or strict:
            actual = payload.get(field)
            if not isinstance(actual, str) or not actual or (expected is not None and actual != expected):
                raise AppStoreTransientError(f"invalid {key} {field}: {actual!r}; expected {expected!r}")
    if "schemaVersion" in payload or strict:
        if payload.get("schemaVersion") != library_manifest.get("schemaVersion"):
            raise AppStoreTransientError(f"invalid {key} schemaVersion")
        check_schema_version(payload.get("schemaVersion"), "library")
    if (
        key == "appsIndex"
        and library_manifest.get("schemaVersion") == "2"
        and payload.get("metadata") != library_manifest.get("metadata")
    ):
        raise AppStoreTransientError("appsIndex metadata does not match the library manifest")
    if key == "appsIndex":
        _validate_apps_index(payload, strict=strict)
    else:
        bootstrap = payload.get("mode") == "bootstrap" or library_manifest.get("supportsPartialUpdate") is False
        if "fromVersion" in payload or strict:
            from_version = payload.get("fromVersion")
            if not (bootstrap and from_version is None) and (
                not isinstance(from_version, str) or not from_version.strip() or from_version != from_version.strip()
            ):
                raise AppStoreTransientError("invalid appsDelta fromVersion")
        seen: set[str] = set()
        for field in ("addedApps", "changedApps", "removedApps"):
            values = payload.get(field, [] if not strict else None)
            if not isinstance(values, list) or any(not _valid_app_key(value) for value in values):
                raise AppStoreTransientError(f"invalid appsDelta {field}")
            if len(set(values)) != len(values) or seen.intersection(values):
                raise AppStoreTransientError("duplicate appsDelta app")
            seen.update(values)
    cache[key] = payload
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def app_content_fingerprint(app_root: Path, app_key: str) -> str:
    if not _valid_app_key(app_key) or not app_root.is_dir() or app_root.is_symlink():
        raise AppStoreTransientError(f"invalid app tree: {app_key!r}")
    return tree_content_fingerprint(app_root, f"apps/{app_key}/")


def tree_content_fingerprint(app_root: Path, prefix: str = "") -> str:
    if not app_root.is_dir():
        raise AppStoreTransientError(f"missing or unsafe asset tree: {app_root}")
    digest = hashlib.sha256()
    resolved_root = app_root.resolve()
    is_media_root = not prefix and (app_root / "json").is_dir()
    # Sort the path objects, not their relative strings: the publisher hashes
    # ``sorted(Path)``, which compares path parts. String order differs once a
    # directory and a file share a prefix (``hrms/`` vs ``hrms.png``).
    for path in sorted(app_root.rglob("*")):
        if path.is_symlink() and (not path.resolve().is_relative_to(resolved_root) or not path.is_file()):
            raise AppStoreTransientError(f"unsafe app symlink: {path}")
        if path.is_file():
            if is_media_root and _is_uploaded_media_file(path, app_root):
                continue
            canonical = f"{prefix}{path.relative_to(app_root).as_posix()}"
            digest.update(canonical.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_sha256(path).encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def _verify_apps_tree(library_root: Path, payload: dict[str, object]) -> None:
    hashes = _validate_apps_index(payload, strict=False)
    if not hashes:
        if payload.get("apps"):
            return
    apps_root = library_root / "apps"
    if not apps_root.is_dir() or apps_root.is_symlink():
        raise AppStoreTransientError("missing or unsafe library apps tree")
    expected_keys = {item.get("app") or item.get("key") for item in payload["apps"]}
    actual_keys = {path.name for path in apps_root.iterdir()}
    if actual_keys != expected_keys:
        raise AppStoreTransientError("library apps tree does not match appsIndex membership")
    for key, expected in hashes.items():
        actual = app_content_fingerprint(apps_root / key, key)
        if actual != expected:
            raise AppStoreTransientError(f"app fingerprint mismatch for {key}: expected {expected}, got {actual}")


def verify_library_source(
    library_root: Path, manifest_bundle: dict[str, object] | None, *, full_package: bool = False
) -> None:
    payload = fetch_library_apps_index_payload(manifest_bundle)
    if payload is not None:
        _verify_apps_tree(library_root, payload)
    manifest = (manifest_bundle or {}).get("library_manifest", {})
    strict_metadata = (
        isinstance(manifest, dict) and manifest.get("schemaVersion") == "2"
    ) or ((manifest_bundle or {}).get("appstore_manifest") or {}).get("schemaVersion") == "2"
    metadata_path = library_root / "library.json"
    if isinstance(manifest, dict) and (strict_metadata or metadata_path.is_file()):
        try:
            metadata = json.loads(metadata_path.read_bytes())
        except (OSError, ValueError) as exc:
            raise AppStoreTransientError(f"invalid embedded library metadata: {exc}") from exc
        if not isinstance(metadata, dict) or (
            (strict_metadata or "schemaVersion" in metadata) and metadata.get("schemaVersion") != manifest.get("schemaVersion")
        ):
            raise AppStoreTransientError("embedded library schemaVersion does not match its manifest")
        if full_package and strict_metadata:
            for entry_key, file_name in SHARED_DICTIONARIES:
                entry = library_dictionary_entry(manifest_bundle, entry_key)
                dictionary = library_root / "metadata" / file_name
                if entry is None or not dictionary.is_file() or file_sha256(dictionary) != entry["sha256"]:
                    raise AppStoreTransientError(f"embedded {entry_key} does not match the library manifest")


def verify_catalog_source(media_root: Path, manifest_bundle: dict[str, object] | None) -> None:
    if not manifest_bundle or manifest_bundle["appstore_manifest"].get("schemaVersion") != "2":
        return
    names = ("catalog_en.json", "catalog_zh.json", "product_en.json", "product_zh.json")
    try:
        content = ",".join(f"{name}={file_sha256(media_root / 'json' / name)}" for name in names)
    except OSError as exc:
        raise AppStoreTransientError(f"incomplete catalog package: {exc}") from exc
    actual = hashlib.sha256(content.encode("utf-8") + b"\0").hexdigest()[:16]
    if actual != manifest_bundle["catalog_manifest"]["datasetVersion"]:
        raise AppStoreTransientError("catalog package fingerprint does not match its manifest")


def resolve_library_index_delta_context(
    manifest_bundle: dict[str, object], previous_state: dict[str, object], library_root: Path, channel: str,
) -> dict[str, object] | None:
    remote = fetch_library_apps_index_payload(manifest_bundle)
    if remote is None:
        return None
    manifest = manifest_bundle.get("library_manifest", {})
    if manifest.get("supportsPartialUpdate") is False:
        return None
    new_hashes = _validate_apps_index(remote, strict=False)
    if len(new_hashes) != len(remote["apps"]):
        return None
    try:
        local = json.loads((library_root / "apps-index.json").read_bytes())
        if not isinstance(local, dict) or not previous_state.get("libraryDatasetVersion"):
            return None
        if local.get("datasetVersion") != previous_state["libraryDatasetVersion"] or local.get("channel") != channel:
            return None
        if local.get("schemaVersion") != remote.get("schemaVersion"):
            return None
        old_hashes = _validate_apps_index(local, strict=False)
        if len(old_hashes) != len(local["apps"]):
            return None
        _verify_apps_tree(library_root, local)
    except (OSError, ValueError, AppStoreTransientError):
        return None
    added = sorted(new_hashes.keys() - old_hashes.keys())
    removed = sorted(old_hashes.keys() - new_hashes.keys())
    changed = sorted(key for key in new_hashes.keys() & old_hashes.keys() if new_hashes[key] != old_hashes[key])
    return {"addedApps": added, "removedApps": removed, "changedApps": changed, "updatedApps": changed, "indexReconciled": True}


def library_dictionary_entry(
    manifest_bundle: dict[str, object] | None, entry_key: str = "databaseTypes"
) -> dict[str, str] | None:
    """Return the shared-dictionary entry published by the library manifest.

    The library manifest names the dictionary by a content-addressed path plus its SHA-256, so a
    consumer can tell whether its local copy is current without downloading anything.
    """
    if not manifest_bundle:
        return None

    library_manifest = manifest_bundle.get("library_manifest")
    library_manifest_url = str(manifest_bundle.get("library_manifest_url") or "")
    if not isinstance(library_manifest, dict) or not library_manifest_url:
        return None

    metadata = library_manifest.get("metadata")
    if "metadata" in library_manifest and not isinstance(metadata, dict):
        raise AppStoreTransientError("invalid library metadata declaration")
    if not isinstance(metadata, dict):
        return None

    entry = metadata.get(entry_key)
    if entry_key not in metadata:
        return None
    if not isinstance(entry, dict):
        raise AppStoreTransientError(f"invalid {entry_key} declaration")

    relative_path = entry.get("path")
    expected_sha256 = entry.get("sha256")
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise AppStoreTransientError(f"invalid {entry_key} path")
    if not _valid_hash(expected_sha256):
        raise AppStoreTransientError(f"invalid {entry_key} checksum")

    return {
        "path": relative_path.strip(),
        "sha256": expected_sha256.strip().lower(),
        "manifest_url": library_manifest_url,
    }


def _dictionary_state_key(entry_key: str) -> str:
    return f"{entry_key}Sha256"


def _dictionary_repair_needed(
    library_root: Path,
    previous_state: dict[str, object] | None,
    entry_key: str = "databaseTypes",
    filename: str = "database-types.json",
    *,
    known_only: bool = False,
) -> bool:
    """Whether the local dictionary disagrees with the last successful sync.

    A recorded digest that matches means the file is intact; no extra request is needed. An
    unrecorded digest (state written by an older platform) is treated as needing one check so
    the digest gets recorded.

    ``known_only`` dictionaries are optional in older artifacts: without a recorded digest a
    missing file means "not published yet", not "damaged".
    """
    path = library_root / "metadata" / filename
    recorded = (previous_state or {}).get(_dictionary_state_key(entry_key))
    if not path.is_file():
        return not known_only or (isinstance(recorded, str) and bool(recorded))
    if not isinstance(recorded, str) or not recorded:
        # State written before this field existed: keep the fast path as-is and let the next
        # full sync record the digest.
        return False
    try:
        return file_sha256(path) != recorded
    except OSError:
        return True


def library_dictionary_targets(
    library_root: Path,
    package_snapshot_paths: dict[str, object],
    filename: str = "database-types.json",
) -> list[Path]:
    """Where the shared dictionary has to exist: the live library and every library snapshot."""
    targets: list[Path] = [library_root / "metadata" / filename]
    seen = {str(targets[0])}
    library_snapshots = package_snapshot_paths.get("library")
    if isinstance(library_snapshots, dict):
        for snapshot_key in ("staging", "release", "current"):
            snapshot_value = library_snapshots.get(snapshot_key)
            if not isinstance(snapshot_value, str) or not snapshot_value:
                continue
            candidate = Path(snapshot_value) / "metadata" / filename
            if str(candidate) in seen:
                continue
            seen.add(str(candidate))
            targets.append(candidate)
    return targets


def sync_shared_dictionary(
    manifest_bundle: dict[str, object] | None,
    targets: list[Path],
    *,
    entry_key: str = "databaseTypes",
    filename: str = "database-types.json",
    prefetched_source: Path | None = None,
) -> dict[str, str]:
    """Keep a shared dictionary identical to the published one.

    The dictionaries travel inside the full package only, so an installation that keeps taking
    per-app deltas would never see a dictionary-only release. Compare the local SHA-256 with the
    library manifest, download the content-addressed payload when they differ, verify it and only
    then replace the local copies.
    """
    entry = library_dictionary_entry(manifest_bundle, entry_key)
    if entry is None or not targets:
        return {"status": "unavailable"}

    expected_sha256 = entry["sha256"]
    primary = targets[0]
    primary_matches = False
    if primary.is_file():
        try:
            primary_matches = file_sha256(primary) == expected_sha256
        except OSError as exc:
            verbose_log(f"[platform-assets] could not read local {entry_key} dictionary: {exc}")
    if primary_matches:
        for target in targets[1:]:
            _copy_dictionary(primary, target)
        return {"status": "unchanged", "sha256": expected_sha256}

    if prefetched_source is not None:
        if file_sha256(prefetched_source) != expected_sha256:
            raise RuntimeError(f"{entry_key} prefetched dictionary checksum mismatch")
        for target in targets:
            _copy_dictionary(prefetched_source, target)
        return {"status": "updated", "sha256": expected_sha256}

    payload_url = resolve_json_url(entry["manifest_url"], entry["path"])
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        downloaded = Path(tmp_dir_name) / filename
        download_file(payload_url, downloaded)
        actual_sha256 = file_sha256(downloaded)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"{entry_key} dictionary checksum mismatch: expected {expected_sha256}, downloaded {actual_sha256}"
            )
        for target in targets:
            _copy_dictionary(downloaded, target)

    return {"status": "updated", "sha256": expected_sha256}


def sync_shared_database_dictionary(
    manifest_bundle: dict[str, object] | None,
    targets: list[Path],
) -> dict[str, str]:
    """Database type dictionary; kept as the named entry point used by existing callers."""
    return sync_shared_dictionary(manifest_bundle, targets)


def _copy_dictionary(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Replace atomically: a half-written dictionary would break the database panel until the
        # next sync repaired it.
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def publish_library_apps_index(library_root: Path, manifest_bundle: dict[str, object] | None, extra_targets: list[Path] | None = None) -> bool:
    """Persist the apps index beside the library and inside the dataset snapshots.

    Keeping it next to the library lets the manifest builder pick it up, and the snapshot copies
    keep an offline activation able to rebuild the same manifests. Returns whether every target
    could be written; a partial write is reported by the caller instead of being swallowed.
    """
    payload = fetch_library_apps_index_payload(manifest_bundle)
    if payload is None:
        return True

    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    written = True
    for target in [library_root / "apps-index.json", *(extra_targets or [])]:
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(serialized, encoding="utf-8")
            os.replace(temporary, target)
        except OSError as exc:
            written = False
            verbose_log(f"[platform-assets] could not persist apps index at {target}: {exc}")
        finally:
            temporary.unlink(missing_ok=True)
    return written


def _resolve_domain_manifest(package_type: str, manifest_bundle: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    if package_type == "media":
        manifest = manifest_bundle.get("catalog_manifest")
        manifest_url = str(manifest_bundle.get("catalog_manifest_url") or "")
    else:
        manifest = manifest_bundle.get("library_manifest")
        manifest_url = str(manifest_bundle.get("library_manifest_url") or "")
    if not isinstance(manifest, dict):
        return None
    return manifest_url, manifest


def _resolve_full_package_relative(package_type: str, manifest: dict[str, object]) -> str:
    full_pkg = manifest.get("fullPackage")
    if isinstance(full_pkg, str) and full_pkg.strip() and full_pkg == full_pkg.strip():
        return full_pkg
    if isinstance(full_pkg, dict):
        latest = full_pkg.get("latest")
        if isinstance(latest, str) and latest.strip() and latest == latest.strip():
            return latest
    if "fullPackage" in manifest:
        raise AppStoreTransientError(f"invalid {package_type} fullPackage declaration")
    legacy_keys = ("legacyMediaArchive", "catalogArchive") if package_type == "media" else ("libraryPackage",)
    for key in legacy_keys:
        value = manifest.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def resolve_package_artifact(
    package_type: str,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object] | None,
) -> tuple[str, str | None, str | None]:
    """Resolve a package URL together with its manifest base URL and checksum path."""
    if manifest_bundle:
        entry = _resolve_domain_manifest(package_type, manifest_bundle)
        if entry is not None:
            manifest_url, manifest = entry
            relative = _resolve_full_package_relative(package_type, manifest)
            if relative:
                checksum = manifest.get("checksum")
                checksum_relative = ""
                if "checksum" in manifest and not isinstance(checksum, dict):
                    raise AppStoreTransientError(f"invalid {package_type} checksum declaration")
                if isinstance(checksum, dict):
                    if "fullPackage" in checksum:
                        value = checksum["fullPackage"]
                        if not isinstance(value, str) or not value.strip() or value != value.strip():
                            raise AppStoreTransientError(f"invalid {package_type} fullPackage checksum path")
                        checksum_relative = value
                return resolve_json_url(manifest_url, relative), manifest_url, checksum_relative or None

    # Ultimate fallback: legacy flat URL structure
    package_name = resolve_package_name(channel, package_type)
    return f"{artifact_base}/{channel}/websoft9/plugin/{package_type}/{package_name}", None, None


def resolve_package_url(package_type: str, channel: str, artifact_base: str, manifest_bundle: dict[str, object] | None) -> str:
    return resolve_package_artifact(package_type, channel, artifact_base, manifest_bundle)[0]


def stage_snapshot(source_root: Path, snapshot_root: Path, dataset_version: str, package_type: str) -> dict[str, Path]:
    staging_dir = snapshot_root / "staging" / dataset_version / package_type
    release_dir = snapshot_root / "releases" / dataset_version / package_type
    current_dir = snapshot_root / "current" / package_type

    # All three copies live inside the same App Store root, so they reuse the same file
    # contents through hard links instead of copying the payload three times.
    replace_tree_linked(source_root, staging_dir, exclude_uploaded_media=(package_type == "media"))
    replace_tree_linked(staging_dir, release_dir)
    replace_tree_linked(staging_dir, current_dir)

    return {
        "staging": staging_dir,
        "release": release_dir,
        "current": current_dir,
    }


def resolve_reusable_package_source(previous_state: dict[str, object], package_type: str, target_dir: Path, marker_path: Path) -> Path | None:
    snapshots = previous_state.get("snapshots")
    if isinstance(snapshots, dict):
        package_snapshots = snapshots.get(package_type)
        if isinstance(package_snapshots, dict):
            release_path = package_snapshots.get("release")
            if isinstance(release_path, str) and release_path:
                release_dir = Path(release_path)
                if release_dir.exists():
                    return release_dir

    if marker_exists(marker_path, package_type) and target_dir.exists():
        return target_dir

    return None


def promote_existing_package_snapshot(
    source_root: Path,
    target_dir: Path,
    marker_path: Path,
    snapshot_root: Path,
    dataset_version: str,
    package_type: str,
) -> dict[str, str]:
    snapshot_paths = stage_snapshot(source_root, snapshot_root, dataset_version, package_type)
    if not marker_exists(marker_path, package_type):
        sync_tree(snapshot_paths["current"], target_dir)

    if not marker_exists(marker_path, package_type):
        raise RuntimeError(f"{package_type} assets are still missing after snapshot promotion: {marker_path}")

    log(f"[platform-assets] promoted existing {package_type} snapshot into dataset {dataset_version}")
    return {key: str(value) for key, value in snapshot_paths.items()}


def sync_library_delta_target(source_root: Path, target_dir: Path, changed_apps: list[str], removed_apps: list[str], marker_path: Path) -> None:
    _validate_delta_app_keys(changed_apps, removed_apps)
    source_apps_dir = source_root / "apps"

    if not target_dir.exists() or not marker_exists(marker_path, "library"):
        replace_tree(source_root, target_dir)
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source_root.iterdir():
        if item.name == "apps":
            continue
        destination = target_dir / item.name
        if item.is_dir():
            replace_tree(item, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.tmp")
            try:
                shutil.copy2(item, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)

    target_apps_dir = target_dir / "apps"
    target_apps_dir.mkdir(parents=True, exist_ok=True)

    for app_key in removed_apps:
        app_path = target_apps_dir / app_key
        if app_path.is_dir():
            shutil.rmtree(app_path)
        elif app_path.exists():
            app_path.unlink()

    for app_key in changed_apps:
        source_app_path = source_apps_dir / app_key
        if not source_app_path.exists():
            raise RuntimeError(f"library delta references missing app payload: {app_key}")
        destination = target_apps_dir / app_key
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.copytree(source_app_path, destination)


def sync_library_package_delta(
    reusable_source: Path,
    target_dir: Path,
    marker_path: Path,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object],
    snapshot_root: Path,
    dataset_version: str,
    delta_context: dict[str, object],
) -> dict[str, str]:
    changed_apps = sorted(set(delta_context.get("changedApps", [])) | set(delta_context.get("addedApps", [])) | set(delta_context.get("updatedApps", [])))
    removed_apps = sorted(set(delta_context.get("removedApps", [])))
    _validate_delta_app_keys(changed_apps, removed_apps)

    if not changed_apps and not removed_apps:
        verify_library_source(reusable_source, manifest_bundle)
        return promote_existing_package_snapshot(reusable_source, target_dir, marker_path, snapshot_root, dataset_version, "library")

    package_url, package_base_url, package_checksum_relative = resolve_package_artifact("library", channel, artifact_base, manifest_bundle)
    package_name = Path(urllib.request.urlparse(package_url).path).name or resolve_package_name(channel, "library")
    log(f"[platform-assets] applying library app delta from {package_url}; changed={changed_apps or []} removed={removed_apps or []}")

    with tempfile.TemporaryDirectory(prefix="websoft9-library-delta-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        zip_path = temp_dir / package_name
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        download_file(package_url, zip_path)

        if package_base_url and package_checksum_relative:
            verify_downloaded_file_checksum(package_base_url, package_url, package_checksum_relative, zip_path)

        extract_zip_with_permissions(zip_path, extract_dir)

        source_root = extract_sync_root(extract_dir, "library")
        verify_library_source(source_root, manifest_bundle, full_package=True)
        staged_root = temp_dir / "staged-library"
        replace_tree_linked(reusable_source, staged_root)

        staged_apps_dir = staged_root / "apps"
        staged_apps_dir.mkdir(parents=True, exist_ok=True)
        source_apps_dir = source_root / "apps"

        for app_key in removed_apps:
            app_path = staged_apps_dir / app_key
            if app_path.is_dir():
                shutil.rmtree(app_path)
            elif app_path.exists():
                app_path.unlink()

        for app_key in changed_apps:
            source_app_path = source_apps_dir / app_key
            if not source_app_path.exists():
                raise RuntimeError(f"library delta references missing app payload: {app_key}")
            destination = staged_apps_dir / app_key
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            shutil.copytree(source_app_path, destination)

        verify_library_source(staged_root, manifest_bundle)
        snapshot_paths = stage_snapshot(staged_root, snapshot_root, dataset_version, "library")
        sync_library_delta_target(snapshot_paths["current"], target_dir, changed_apps, removed_apps, marker_path)

    if not marker_exists(marker_path, "library"):
        raise RuntimeError(f"library assets are still missing after delta sync: {marker_path}")

    log(f"[platform-assets] applied library app delta into {target_dir}")
    return {key: str(value) for key, value in snapshot_paths.items()}


def extract_app_bundle(bundle_path: Path, apps_root: Path, app_key: str) -> None:
    if not _valid_app_key(app_key):
        raise AppStoreTransientError(f"invalid app key: {app_key!r}")
    extract_dir = bundle_path.parent / f"extract-{app_key}"
    _reset_directory(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    extract_zip_with_permissions(bundle_path, extract_dir)

    extracted_root = extract_dir / app_key
    if not extracted_root.exists():
        children = [item for item in extract_dir.iterdir() if item.is_dir()]
        if len(children) == 1:
            extracted_root = children[0]
        else:
            raise RuntimeError(f"invalid app bundle structure for {app_key}: {bundle_path}")

    destination = apps_root / app_key
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(extracted_root, destination)


def hydrate_app_sidecar(
    base_url: str,
    app_key: str,
    app_root: Path,
    relative_path: object,
    checksum_relative: object,
    local_name: str,
    temp_dir: Path,
) -> None:
    if relative_path in {None, ""}:
        return

    if not isinstance(relative_path, str):
        raise RuntimeError(f"invalid {local_name} artifact entry for app: {app_key}")
    if not isinstance(checksum_relative, str) or not checksum_relative:
        raise RuntimeError(f"missing checksum for {local_name} artifact of app: {app_key}")

    local_path = temp_dir / f"{app_key}-{local_name}"
    download_file(resolve_json_url(base_url, relative_path), local_path)
    verify_downloaded_file_checksum(base_url, relative_path, checksum_relative, local_path)
    # Atomic replace: an in-place copy would corrupt the hard-linked snapshot copies that share
    # this file's inode.
    os.replace(local_path, app_root / local_name)


def _validate_delta_app_keys(changed: list[str], removed: list[str]) -> None:
    if any(not _valid_app_key(key) for key in [*changed, *removed]):
        raise AppStoreTransientError("unsafe library delta app key")


def prepare_library_app_artifacts_source(
    reusable_source: Path,
    manifest_bundle: dict[str, object],
    delta_context: dict[str, object],
    temp_dir: Path,
) -> Path:
    changed_apps = sorted(set(delta_context.get("changedApps", [])) | set(delta_context.get("addedApps", [])) | set(delta_context.get("updatedApps", [])))
    removed_apps = sorted(set(delta_context.get("removedApps", [])))
    _validate_delta_app_keys(changed_apps, removed_apps)

    if not changed_apps and not removed_apps:
        verify_library_source(reusable_source, manifest_bundle)
        return reusable_source

    apps_index = resolve_library_apps_index(manifest_bundle)
    if not apps_index:
        raise RuntimeError("library manifest does not expose app-level artifacts")

    library_manifest_url = str(manifest_bundle.get("library_manifest_url", ""))
    staged_root = temp_dir / "staged-library"
    # Hard links let unchanged apps share bytes without writing through to the active tree.
    replace_tree_linked(reusable_source, staged_root)
    staged_apps_dir = staged_root / "apps"
    staged_apps_dir.mkdir(parents=True, exist_ok=True)

    for app_key in removed_apps:
        app_path = staged_apps_dir / app_key
        if app_path.is_dir():
            shutil.rmtree(app_path)
        elif app_path.exists():
            app_path.unlink()

    def apply_changed_app(app_key: str) -> None:
        app_metadata = apps_index.get(app_key)
        if not isinstance(app_metadata, dict):
            raise RuntimeError(f"appsIndex is missing changed app metadata: {app_key}")
        bundle_relative = app_metadata.get("bundle")
        if not isinstance(bundle_relative, str) or not bundle_relative:
            raise RuntimeError(f"appsIndex bundle entry is missing for app: {app_key}")
        checksum = app_metadata.get("checksum")
        if not isinstance(checksum, dict):
            raise RuntimeError(f"appsIndex checksum entry is missing for app: {app_key}")
        bundle_checksum_relative = checksum.get("bundle")
        if not isinstance(bundle_checksum_relative, str) or not bundle_checksum_relative:
            raise RuntimeError(f"appsIndex bundle checksum entry is missing for app: {app_key}")

        bundle_path = temp_dir / f"{app_key}.zip"
        download_file(resolve_json_url(library_manifest_url, bundle_relative), bundle_path)
        verify_downloaded_file_checksum(library_manifest_url, bundle_relative, bundle_checksum_relative, bundle_path)
        extract_app_bundle(bundle_path, staged_apps_dir, app_key)

        app_root = staged_apps_dir / app_key
        expected_hash = app_metadata.get("hash")
        if expected_hash is not None and app_content_fingerprint(app_root, app_key) != expected_hash.lower():
            raise AppStoreTransientError(f"app fingerprint mismatch for {app_key}")
        hydrate_app_sidecar(
            library_manifest_url, app_key, app_root, app_metadata.get("variables"),
            checksum.get("variables"), "variables.json", temp_dir,
        )
        hydrate_app_sidecar(
            library_manifest_url, app_key, app_root, app_metadata.get("env"),
            checksum.get("env"), ".env", temp_dir,
        )

    if changed_apps:
        max_workers = min(_resolve_app_download_workers(), len(changed_apps))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(apply_changed_app, app_key) for app_key in changed_apps]
            for future in futures:
                future.result()

    verify_library_source(staged_root, manifest_bundle)
    return staged_root


def sync_library_app_artifacts_delta(
    reusable_source: Path,
    target_dir: Path,
    marker_path: Path,
    manifest_bundle: dict[str, object],
    snapshot_root: Path,
    dataset_version: str,
    delta_context: dict[str, object],
    prefetched_source: Path | None = None,
) -> dict[str, str]:
    changed_apps = sorted(set(delta_context.get("changedApps", [])) | set(delta_context.get("addedApps", [])) | set(delta_context.get("updatedApps", [])))
    removed_apps = sorted(set(delta_context.get("removedApps", [])))
    _validate_delta_app_keys(changed_apps, removed_apps)
    if not changed_apps and not removed_apps:
        verify_library_source(reusable_source, manifest_bundle)
        return promote_existing_package_snapshot(reusable_source, target_dir, marker_path, snapshot_root, dataset_version, "library")
    with tempfile.TemporaryDirectory(prefix="websoft9-library-app-artifacts-") as temp_dir_name:
        staged_root = prefetched_source or prepare_library_app_artifacts_source(
            reusable_source, manifest_bundle, delta_context, Path(temp_dir_name),
        )
        snapshot_paths = stage_snapshot(staged_root, snapshot_root, dataset_version, "library")
        sync_library_delta_target(snapshot_paths["current"], target_dir, changed_apps, removed_apps, marker_path)

    if not marker_exists(marker_path, "library"):
        raise RuntimeError(f"library assets are still missing after app-artifact delta sync: {marker_path}")

    log(f"[platform-assets] applied library app artifacts delta into {target_dir}")
    return {key: str(value) for key, value in snapshot_paths.items()}


def package_needs_sync(package_type: str, marker_path: Path, package_sync_plan: dict[str, bool] | None, force_refresh: bool) -> bool:
    """Report whether a package must be downloaded and applied."""
    if force_refresh:
        return True
    if package_sync_plan is not None:
        return package_sync_plan.get(package_type, True)
    return not marker_exists(marker_path, package_type)


def prepare_package_source(
    package_type: str,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object] | None,
    temp_dir: Path,
) -> Path:
    """Download, verify and extract a package; returns the extracted payload root.

    Kept separate from the tree replacement so several packages can be fetched concurrently while
    the runtime trees are still only rewritten one package at a time.
    """
    package_url, package_base_url, package_checksum_relative = resolve_package_artifact(package_type, channel, artifact_base, manifest_bundle)
    package_name = Path(urllib.request.urlparse(package_url).path).name or resolve_package_name(channel, package_type)
    log(f"[platform-assets] downloading {package_type} assets from {package_url}")

    zip_path = temp_dir / package_name
    extract_dir = temp_dir / "extract"
    _reset_directory(extract_dir)
    _reset_directory(temp_dir / "wrapped-media")
    extract_dir.mkdir(parents=True, exist_ok=True)

    download_file(package_url, zip_path)

    if package_base_url and package_checksum_relative:
        # Verify the downloaded archive before it can reach a runtime tree.
        verify_downloaded_file_checksum(package_base_url, package_url, package_checksum_relative, zip_path)

    extract_zip_with_permissions(zip_path, extract_dir)

    source_root = extract_sync_root(extract_dir, package_type)
    if package_type == "library":
        verify_library_source(source_root, manifest_bundle, full_package=True)

    # v2 catalog zip ships JSON files flat; the runtime layout expects
    # them under a json/ subdirectory (matching the legacy media.zip shape).
    if package_type == "media" and not (source_root / "json").is_dir():
        json_files = sorted(source_root.glob("*.json"))
        if json_files:
            json_dir = temp_dir / "wrapped-media"
            nested_json = json_dir / "json"
            nested_json.mkdir(parents=True, exist_ok=True)
            for json_file in json_files:
                shutil.move(str(json_file), str(nested_json / json_file.name))
            # Carry over any non-JSON contents (logos, screenshots, etc.)
            for item in source_root.iterdir():
                if item.is_dir():
                    shutil.copytree(item, json_dir / item.name, dirs_exist_ok=True)
                elif not item.name.endswith(".json"):
                    shutil.copy2(item, json_dir / item.name)
            source_root = json_dir

    if package_type == "media":
        verify_catalog_source(source_root, manifest_bundle)
    return source_root


def apply_package_source(
    package_type: str,
    target_dir: Path,
    marker_path: Path,
    source_root: Path,
    snapshot_root: Path | None,
    dataset_version: str | None,
) -> dict[str, str] | None:
    snapshot_paths = None
    if snapshot_root is not None and dataset_version:
        snapshot_paths = stage_snapshot(source_root, snapshot_root, dataset_version, package_type)
        source_root = snapshot_paths["current"]
    replace_tree_preserving_generated_manifests(source_root, target_dir)

    if not marker_exists(marker_path, package_type):
        raise RuntimeError(f"{package_type} assets are still missing after sync: {marker_path}")

    log(f"[platform-assets] synced {package_type} assets into {target_dir}")
    if snapshot_paths:
        return {key: str(value) for key, value in snapshot_paths.items()}
    return None


def prefetch_pending_packages(
    packages: list[tuple[str, Path, Path]],
    package_sync_plan: dict[str, bool],
    force_refresh: bool,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object] | None,
) -> tuple[dict[str, Path], Path | None]:
    """Download every package that needs updating concurrently.

    Packages are independent, so fetching them in parallel removes one full round of download
    latency (media + library).  The trees themselves are still rewritten one package at a time.
    A failed parallel download is retried serially before any activation begins.
    """
    pending = [
        package
        for package in packages
        if package_needs_sync(package[0], package[2], package_sync_plan, force_refresh)
    ]
    if not pending:
        return {}, None

    prefetch_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-prefetch-"))
    prefetched: dict[str, Path] = {}
    try:
        with ThreadPoolExecutor(max_workers=len(pending)) as executor:
            futures = {}
            for package_type, _target_dir, _marker_path in pending:
                package_temp_dir = prefetch_root / package_type
                package_temp_dir.mkdir(parents=True, exist_ok=True)
                futures[
                    executor.submit(
                        prepare_package_source,
                        package_type,
                        channel,
                        artifact_base,
                        manifest_bundle,
                        package_temp_dir,
                    )
                ] = package_type
            for future, package_type in futures.items():
                try:
                    prefetched[package_type] = future.result()
                except Exception as exc:
                    log(f"[platform-assets] {package_type} prefetch failed; downloading it serially instead: {exc}")
                    prefetched[package_type] = with_transient_retry(
                        lambda: prepare_package_source(
                            package_type, channel, artifact_base, manifest_bundle, prefetch_root / package_type,
                        ),
                        label=f"{package_type} prefetch",
                    )
    except BaseException:
        shutil.rmtree(prefetch_root, ignore_errors=True)
        raise
    return prefetched, prefetch_root


def sync_package(
    package_type: str,
    target_dir: Path,
    marker_path: Path,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object] | None = None,
    snapshot_root: Path | None = None,
    dataset_version: str | None = None,
    force_sync: bool = False,
    prefetched_source: Path | None = None,
) -> dict[str, str] | None:
    force_refresh = is_force_refresh_enabled()

    if marker_exists(marker_path, package_type) and not force_refresh and not force_sync:
        log(f"[platform-assets] {package_type} already present at {marker_path}")
        return None

    if prefetched_source is not None:
        return apply_package_source(package_type, target_dir, marker_path, prefetched_source, snapshot_root, dataset_version)

    with tempfile.TemporaryDirectory(prefix=f"websoft9-{package_type}-") as temp_dir_name:
        source_root = prepare_package_source(package_type, channel, artifact_base, manifest_bundle, Path(temp_dir_name))
        return apply_package_source(package_type, target_dir, marker_path, source_root, snapshot_root, dataset_version)


def load_initial_apps(config_path: Path) -> list[str]:
    if not config_path.exists():
        return []

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    raw_value = parser.get("initial_apps", "keys", fallback="")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def load_env_values(env_path: Path) -> dict[str, str]:
    if dotenv_values is None:
        raise RuntimeError("python-dotenv is required to generate app store install metadata")

    raw_values = dotenv_values(env_path)
    normalized_values = {key: value for key, value in raw_values.items() if key}
    resolved_values: dict[str, str] = {}

    def resolve_value(key: str, stack: set[str]) -> str:
        if key in resolved_values:
            return resolved_values[key]

        if key in stack:
            return ""

        stack.add(key)
        current_value = normalized_values.get(key)
        if not isinstance(current_value, str):
            resolved_values[key] = ""
            stack.remove(key)
            return ""

        resolved = ENV_REFERENCE_PATTERN.sub(lambda match: resolve_value(match.group(1), stack), current_value)
        resolved_values[key] = resolved
        stack.remove(key)
        return resolved

    for key in normalized_values:
        resolve_value(key, set())

    return resolved_values


def get_install_settings(env_values: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in env_values.items()
        if key.startswith("W9_") and key.endswith("_SET")
    }


def get_distribution(edition_metadata: object) -> list[dict[str, object]]:
    if not isinstance(edition_metadata, list):
        return []

    distributions: dict[str, list[str]] = {}
    for edition in edition_metadata:
        if not isinstance(edition, dict):
            continue

        dist = edition.get("dist")
        raw_versions = edition.get("version")
        if isinstance(raw_versions, str):
            versions = [raw_versions.strip()] if raw_versions.strip() else []
        elif isinstance(raw_versions, list):
            versions = [version.strip() for version in raw_versions if isinstance(version, str) and version.strip()]
        else:
            versions = []

        if isinstance(dist, str) and dist.strip() and versions:
            distributions.setdefault(dist.strip(), []).extend(versions)

    return [{"key": dist, "value": versions} for dist, versions in distributions.items()]


def discover_install_profiles(app_dir: Path, skipped: Counter[str] | None = None) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}

    for env_path in sorted(app_dir.glob(".env.*")):
        match = re.match(r"^\.env\.([a-z0-9][a-z0-9-]*)$", env_path.name)
        if not match:
            continue

        profile_name = match.group(1)
        try:
            env_values = load_env_values(env_path)
            profile_metadata: dict[str, object] = {
                "settings": get_install_settings(env_values),
            }
            if env_values.get("W9_DATABASE_MODE") == "external":
                profile_metadata["is_external_database"] = True
            profiles[profile_name] = profile_metadata
        except Exception as exc:
            if skipped is not None:
                skipped["invalid-profile"] += 1
            verbose_log(f"[platform-assets] skipping profile {env_path}: {exc}")

    if EXTERNAL_DATABASE_PROFILE not in profiles:
        profile_metadata = external_database_profile(app_dir)
        if profile_metadata is not None:
            profiles[EXTERNAL_DATABASE_PROFILE] = profile_metadata

    return profiles


def external_database_profile(app_dir: Path) -> dict[str, object] | None:
    """Synthesise the ``external-db`` profile from a ``database[]`` declaration.

    Mirrors ``apphub/src/services/external_database.py``. The library is retiring
    ``.env.external-db`` in favour of the declaration, and the install form keeps
    consuming the same profile shape either way.
    """
    try:
        variables = json.loads((app_dir / "variables.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(variables, dict):
        return None

    for component in variables.get("database") or []:
        if not isinstance(component, dict):
            continue
        providers = [item for item in component.get("providers") or [] if isinstance(item, dict)]
        external = next((item for item in providers if item.get("type") == "external"), None)
        if external is None:
            continue
        datasource = component.get("datasource")
        if not isinstance(datasource, dict) or not datasource:
            continue
        drivers = [
            item.strip().lower() for item in external.get("drivers") or [] if isinstance(item, str) and item.strip()
        ]
        drivers = [item for item in drivers if item in EXTERNAL_DATABASE_DRIVERS]
        if not drivers:
            continue
        settings = {key: "" for key in EXTERNAL_DATABASE_SETTING_KEYS}
        settings["W9_DB_PORT_SET"] = str(EXTERNAL_DATABASE_PORTS.get(drivers[0], ""))
        return {"settings": settings, "is_external_database": True}
    return None


def load_catalog_metadata(library_root: Path) -> dict[str, dict[str, object]]:
    metadata_root = library_root.parent / "metadata" / "catalog"
    metadata: dict[str, dict[str, object]] = {}
    metadata_root.mkdir(parents=True, exist_ok=True)
    if not metadata_root.is_dir():
        return metadata

    for metadata_path in sorted(metadata_root.glob("*.json")):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to read catalog metadata {metadata_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"catalog metadata must be an object: {metadata_path}")

        app_key = metadata_path.stem
        declared_key = payload.get("key")
        if declared_key is not None and declared_key != app_key:
            raise RuntimeError(f"catalog metadata key does not match filename: {metadata_path}")
        metadata[app_key] = payload

    return metadata


def load_catalog_titles(media_json_root: Path, locale: str) -> dict[str, dict[str, object]]:
    catalog_path = media_json_root / f"catalog_{locale}.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read {catalog_path}: {exc}") from exc
    if not isinstance(catalog, list):
        raise RuntimeError(f"catalog metadata must be an array: {catalog_path}")

    titles: dict[str, dict[str, object]] = {}
    for parent in catalog:
        if not isinstance(parent, dict) or not isinstance(parent.get("key"), str):
            continue
        children = parent.get("linkedFrom", {}).get("catalogCollection", {}).get("items", [])
        child_titles = {
            child["key"]: child
            for child in children
            if isinstance(child, dict) and isinstance(child.get("key"), str)
        }
        titles[parent["key"]] = {"parent": parent, "children": child_titles}
    return titles


def build_catalog_collection(bindings: object, catalog_titles: dict[str, dict[str, object]]) -> dict[str, object]:
    if not isinstance(bindings, list):
        raise ValueError("catalogBindings must be an array")

    parents: dict[str, dict[str, object]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError("catalogBindings entries must be objects")
        parent_key = binding.get("parentKey")
        child_key = binding.get("childKey")
        if not isinstance(parent_key, str) or not isinstance(child_key, str):
            raise ValueError("catalogBindings entries require parentKey and childKey")
        catalog_entry = catalog_titles.get(parent_key)
        if catalog_entry is None:
            raise ValueError(f"catalog parent does not exist: {parent_key}")
        child = catalog_entry["children"].get(child_key)
        if not isinstance(child, dict):
            raise ValueError(f"catalog child does not exist: {parent_key}/{child_key}")

        parent = catalog_entry["parent"]
        parent_item = parents.setdefault(
            parent_key,
            {
                "key": parent_key,
                "title": parent.get("title", parent_key),
                "catalogCollection": {"items": []},
            },
        )
        parent_item["catalogCollection"]["items"].append(
            {"key": child_key, "title": child.get("title", child_key), "position": child.get("position")}
        )

    return {"items": list(parents.values())}


def resolve_catalog_product(metadata: dict[str, object], app_key: str, locale: str, catalog_titles: dict[str, dict[str, object]]) -> dict[str, object]:
    product = {key: value for key, value in metadata.items() if key not in {"key", "translations", "catalogBindings"}}
    translations = metadata.get("translations")
    if isinstance(translations, dict) and isinstance(translations.get(locale), dict):
        product.update(translations[locale])
    product["key"] = app_key
    product["app_origin"] = "development"
    product["catalogCollection"] = build_catalog_collection(metadata.get("catalogBindings"), catalog_titles)
    return product


def build_app_store_manifest(media_json_root: Path, library_root: Path, locale: str) -> dict[str, object]:
    product_path = media_json_root / f"product_{locale}.json"
    try:
        products = json.loads(product_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read {product_path}: {exc}") from exc
    if not isinstance(products, list):
        raise RuntimeError(f"product media must be an array: {product_path}")

    # Per-app update times travel with the library apps index; the manifest only exposes the field
    # when the published dataset provides it.
    updated_at_by_key = load_library_apps_index(library_root.parent)

    catalog_metadata = load_catalog_metadata(library_root)
    catalog_titles = load_catalog_titles(media_json_root, locale) if catalog_metadata else {}
    legacy_products: dict[str, dict[str, object]] = {}
    product_order: list[str] = []
    skipped: Counter[str] = Counter()
    for product in products:
        if not isinstance(product, dict):
            skipped["invalid-media"] += 1
            verbose_log(f"[platform-assets] skipping non-object media entry in product_{locale}.json")
            continue
        app_key = product.get("key")
        if not isinstance(app_key, str) or not app_key.strip():
            skipped["invalid-media"] += 1
            verbose_log("[platform-assets] skipping media entry with missing app key")
            continue
        app_key = app_key.strip()
        if app_key in legacy_products:
            raise RuntimeError(f"duplicate app key in {product_path}: {app_key}")
        legacy_products[app_key] = product
        product_order.append(app_key)

    product_keys = set(legacy_products) | set(catalog_metadata)
    metadata_only_keys = sorted(set(catalog_metadata) - set(legacy_products))
    for app_key in sorted(set(catalog_metadata) & set(legacy_products)):
        skipped["duplicate-catalog-metadata"] += 1
        verbose_log(f"[platform-assets] ignoring local catalog metadata for {app_key}: standard product entry already exists")
    product_order.extend(metadata_only_keys)
    apps: list[dict[str, object]] = []
    for app_key in product_order:
        product = legacy_products.get(app_key)
        if app_key in metadata_only_keys:
            try:
                product = resolve_catalog_product(catalog_metadata[app_key], app_key, locale, catalog_titles)
            except ValueError as exc:
                skipped["invalid-catalog-metadata"] += 1
                verbose_log(f"[platform-assets] skipping {app_key}: invalid catalog metadata: {exc}")
                continue
        if product is None:
            continue
        app_dir = library_root / app_key
        variables_path = app_dir / "variables.json"
        env_path = app_dir / ".env"
        if not app_dir.is_dir() or not variables_path.exists() or not env_path.exists():
            skipped["missing-library-metadata"] += 1
            verbose_log(f"[platform-assets] skipping {app_key}: missing Library template, variables.json, or .env")
            continue
        try:
            variables_metadata = json.loads(variables_path.read_text(encoding="utf-8"))
            if not isinstance(variables_metadata, dict):
                raise ValueError("variables.json must be an object")
            distribution = get_distribution(variables_metadata.get("edition"))
            if not distribution:
                raise ValueError("variables.json has no valid edition")
            env_values = load_env_values(env_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            skipped["invalid-library-metadata"] += 1
            verbose_log(f"[platform-assets] skipping {app_key}: invalid Library metadata: {exc}")
            continue
        app_manifest = dict(product)
        access_metadata = variables_metadata.get("access")
        raw_default_scheme = access_metadata.get("defaultScheme") if isinstance(access_metadata, dict) else None
        if isinstance(raw_default_scheme, str) and raw_default_scheme.strip().lower() in {"http", "https"}:
            default_scheme = raw_default_scheme.strip().lower()
        elif "W9_HTTPS_PORT" in env_values and "W9_HTTP_PORT" not in env_values:
            default_scheme = "https"
        else:
            default_scheme = "http"
        app_manifest.update({
            "distribution": distribution,
            "settings": get_install_settings(env_values),
            "is_web_app": "W9_URL" in env_values,
            "default_scheme": default_scheme,
        })
        updated_at = updated_at_by_key.get(app_key)
        if updated_at:
            app_manifest["updatedAt"] = updated_at
        normalize_display_logo(app_manifest, skipped)
        profiles = discover_install_profiles(app_dir, skipped)
        if profiles:
            app_manifest["profiles"] = profiles
        help_metadata = variables_metadata.get("help")
        if isinstance(help_metadata, dict):
            app_manifest["help"] = help_metadata
        apps.append(app_manifest)

    if library_root.is_dir():
        for app_dir in sorted(library_root.iterdir()):
            if app_dir.is_dir() and app_dir.name not in product_keys:
                skipped["missing-media-entry"] += 1
                verbose_log(f"[platform-assets] skipping {app_dir.name}: missing media entry in product_{locale}.json")
    if product_keys and not apps:
        raise RuntimeError(f"no valid app entries generated from non-empty {product_path}")

    if skipped:
        summary = " ".join(f"{reason}={count}" for reason, count in sorted(skipped.items()))
        log(f"[platform-assets] manifest locale={locale} apps={len(apps)} skipped {summary}")

    manifest: dict[str, object] = {"schemaVersion": LOCAL_MANIFEST_SCHEMA, "locale": locale, "apps": apps}
    validate_app_store_manifest(manifest, product_path)
    return manifest


def normalize_display_logo(app: dict[str, object], skipped: dict[str, int]) -> None:
    """Drop a missing or malformed display logo.

    The logo is presentation only: the console falls back to a bundled default icon when it is
    absent. A single upstream catalog entry with ``"logo": null`` must therefore never stop an
    image build or an asset sync, so the field is removed and reported instead.
    """
    if "logo" not in app:
        return
    logo = app.get("logo")
    if logo is None:
        del app["logo"]
        skipped["missing-logo"] += 1
        verbose_log(f"[platform-assets] {app.get('key')}: no display logo, the default icon is used")
        return
    if not isinstance(logo, dict):
        # A plain string is what some catalog entries carry: keep the image, wrap it properly.
        if isinstance(logo, str) and logo.strip():
            app["logo"] = {"imageurl": logo.strip()}
            skipped["normalized-logo"] += 1
            verbose_log(f"[platform-assets] {app.get('key')}: normalized a plain display logo")
            return
        del app["logo"]
        skipped["malformed-logo"] += 1
        verbose_log(f"[platform-assets] {app.get('key')}: malformed display logo, the default icon is used")


def validate_app_store_manifest(manifest: object, source_path: Path) -> None:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("apps"), list):
        raise RuntimeError(f"invalid app store manifest generated from {source_path}")
    for app in manifest["apps"]:
        if not isinstance(app, dict) or not isinstance(app.get("key"), str) or not app["key"].strip():
            raise RuntimeError(f"invalid app entry generated from {source_path}")
        if "title" in app and (not isinstance(app["title"], str) or not app["title"].strip()):
            raise RuntimeError(f"app entry has invalid display title: {app.get('key')}")
        # The display logo is optional on purpose: a missing icon is rendered with the default one.
        if app.get("logo") is not None and not isinstance(app["logo"], dict):
            raise RuntimeError(f"app entry has invalid display logo: {app.get('key')}")
        if "screenshots" in app and app["screenshots"] is not None and not isinstance(app["screenshots"], list):
            raise RuntimeError(f"app entry has invalid display screenshots: {app.get('key')}")
        if "catalogBindings" in app and not isinstance(app["catalogBindings"], dict):
            raise RuntimeError(f"app entry has invalid catalog bindings: {app.get('key')}")
        if not isinstance(app.get("distribution"), list) or not isinstance(app.get("settings"), dict):
            raise RuntimeError(f"app entry lacks installation metadata: {app.get('key')}")
        if not isinstance(app.get("is_web_app"), bool):
            raise RuntimeError(f"app entry has invalid web flag: {app.get('key')}")
        if "default_scheme" in app and app["default_scheme"] not in {"http", "https"}:
            raise RuntimeError(f"app entry has invalid default_scheme: {app.get('key')}")
        if "profiles" in app and not isinstance(app["profiles"], dict):
            raise RuntimeError(f"app entry has invalid profiles: {app.get('key')}")
        if "help" in app and not isinstance(app["help"], dict):
            raise RuntimeError(f"app entry has invalid help: {app.get('key')}")


def get_published_app_store_schema_version(media_root: Path) -> str | None:
    schemas: set[str] = set()
    for locale in ("zh", "en"):
        manifest_path = media_root / "json" / f"app-store-manifest_{locale}.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AppStoreCompatibilityError(f"failed to read active appstore manifest {manifest_path}: {exc}") from exc
        schema_version = manifest.get("schemaVersion") if isinstance(manifest, dict) else None
        if not isinstance(schema_version, str) or not schema_version.strip():
            raise AppStoreCompatibilityError(f"active appstore manifest has no schemaVersion: {manifest_path}")
        schemas.add(schema_version)

    if not schemas:
        return None
    if len(schemas) != 1:
        raise AppStoreCompatibilityError("active appstore manifests use different schemaVersions")
    return schemas.pop()


def has_valid_published_app_store_manifests(media_root: Path, library_root: Path | None = None) -> bool:
    media_json_root = media_root / "json"
    resolved_library_root = library_root or Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
    library_apps_root = resolved_library_root / "apps"
    has_library_apps = bool(library_apps_root.is_dir() and any(library_apps_root.iterdir()))
    try:
        for locale in ("zh", "en"):
            manifest_path = media_json_root / f"app-store-manifest_{locale}.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                not isinstance(manifest, dict)
                or not isinstance(manifest.get("schemaVersion"), str)
                or not manifest["schemaVersion"].strip()
                or manifest.get("locale") != locale
            ):
                return False
            validate_app_store_manifest(manifest, manifest_path)
            manifest_apps = manifest.get("apps", [])
            if manifest_apps:
                if has_library_apps and library_apps_root is not None:
                    for app in manifest_apps:
                        app_key = app.get("key") if isinstance(app, dict) else None
                        if not isinstance(app_key, str) or not (library_apps_root / app_key / "variables.json").is_file():
                            return False
                product_path = media_json_root / f"product_{locale}.json"
                if product_path.is_file():
                    products = json.loads(product_path.read_text(encoding="utf-8"))
                    if isinstance(products, list):
                        product_keys = {
                            item.get("key").strip()
                            for item in products
                            if isinstance(item, dict) and isinstance(item.get("key"), str) and item.get("key").strip()
                        }
                        for app in manifest_apps:
                            if not isinstance(app, dict) or app.get("app_origin") == "development":
                                continue
                            if app.get("key") not in product_keys:
                                return False
        return True
    except (OSError, json.JSONDecodeError, RuntimeError):
        return False


def write_json_file(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n")
        return Path(handle.name)


def publish_json_files(payloads: dict[Path, object]) -> None:
    temporary_files: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    published_paths: list[Path] = []
    try:
        for path, payload in payloads.items():
            temporary_files[path] = write_json_file(path, payload)
        for path in payloads:
            if path.exists():
                backup_fd, backup_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".backup", dir=path.parent)
                os.close(backup_fd)
                backup_path = Path(backup_name)
                backup_path.unlink()
                path.replace(backup_path)
                backups[path] = backup_path
            temporary_files[path].replace(path)
            published_paths.append(path)
    except Exception:
        for path in published_paths:
            if path.exists():
                path.unlink()
        for path, backup_path in backups.items():
            if backup_path.exists():
                backup_path.replace(path)
        raise
    finally:
        for temporary_path in temporary_files.values():
            temporary_path.unlink(missing_ok=True)
        for backup_path in backups.values():
            backup_path.unlink(missing_ok=True)


def build_and_publish_app_store_manifests(media_root: Path, library_root: Path) -> None:
    media_json_root = media_root / "json"
    library_apps_root = library_root / "apps"
    manifests = {locale: build_app_store_manifest(media_json_root, library_apps_root, locale) for locale in ("zh", "en")}
    publish_json_files({media_json_root / f"app-store-manifest_{locale}.json": manifest for locale, manifest in manifests.items()})
    log(f"[platform-assets] published app store manifests in {media_json_root}")


def is_force_refresh_enabled() -> bool:
    return (os.getenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC") or "0").strip().lower() in {"1", "true", "yes", "on"}


def resolve_env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not str(raw_value).strip():
        return default
    try:
        return int(str(raw_value).strip())
    except ValueError:
        return default


def _resolve_app_download_workers() -> int:
    """Concurrency for per-app artifact downloads (bounded to stay polite to the artifact server)."""
    return max(1, min(resolve_env_int("WEBSOFT9_APPSTORE_APP_DOWNLOAD_WORKERS", 4), 16))


def _tree_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def prune_stale_appstore_datasets(snapshot_root: Path, active_dataset_version: str | None) -> list[str]:
    """Delete every staged/released App Store dataset except the active one.

    This runtime does not roll back to older App Store datasets, so keeping them only wastes
    disk: each historical dataset is a full media + library payload.  Best effort, and it never
    runs when no dataset version is known.
    """
    active_version = (active_dataset_version or "").strip()
    if not active_version:
        return []

    removed: list[str] = []
    for dataset_root in (snapshot_root / "releases", snapshot_root / "staging"):
        if not dataset_root.is_dir():
            continue
        for dataset_dir in dataset_root.iterdir():
            if not dataset_dir.is_dir() or dataset_dir.name == active_version:
                continue
            try:
                shutil.rmtree(dataset_dir)
            except OSError as exc:
                verbose_log(f"[platform-assets] could not remove App Store dataset {dataset_dir}: {exc}")
                continue
            removed.append(f"{dataset_root.name}/{dataset_dir.name}")
    return removed


def runtime_assets_status_path() -> Path:
    runtime_root = Path(os.getenv("WEBSOFT9_RUNTIME_STATE_DIR", "/run/websoft9"))
    return Path(os.getenv("WEBSOFT9_APPSTORE_RUNTIME_STATE_FILE", str(runtime_root / "appstore-assets.json")))


def write_runtime_assets_status(status: str, message: str = "", dataset_version: object = None) -> None:
    write_sync_state(runtime_assets_status_path(), {
        "status": status, "message": message, "datasetVersion": dataset_version,
    })


def restore_runtime_assets_status(previous: dict[str, object], rollback_ok: bool) -> None:
    try:
        write_sync_state(runtime_assets_status_path(), previous if rollback_ok else {
            "status": "unavailable", "message": "Appstore rollback failed",
        })
    except OSError as exc:
        log(f"[platform-assets] failed to restore runtime availability: {exc}")
        try:
            runtime_assets_status_path().unlink(missing_ok=True)
        except OSError as unlink_exc:
            log(f"[platform-assets] failed to invalidate runtime availability: {unlink_exc}")


def validate_runtime_asset_roots(media_root: Path, library_root: Path) -> None:
    if not has_valid_published_app_store_manifests(media_root, library_root):
        raise AppStoreTransientError("missing or invalid generated Appstore manifests")
    if get_published_app_store_schema_version(media_root) != "1":
        raise AppStoreTransientError("unsupported generated Appstore manifest schema")
    if not all((media_root / "json" / f"product_{locale}.json").is_file() for locale in ("en", "zh")):
        raise AppStoreTransientError("missing Appstore product catalogs")
    if not (library_root / "apps").is_dir():
        raise AppStoreTransientError("missing Appstore library")


def runtime_metadata_matches(
    media: Path, library: Path, state: dict[str, object], bundle: dict[str, object]
) -> bool:
    if not isinstance(state.get("assetDigests"), dict):
        return False
    snapshots = state.get("snapshots")
    if not isinstance(snapshots, dict):
        return False
    try:
        for kind, active in (("media", media), ("library", library)):
            paths = snapshots.get(kind)
            if not isinstance(paths, dict) or any(not paths.get(key) for key in ("staging", "release", "current")):
                return False
            roots = [active, *(Path(paths[key]) for key in ("staging", "release", "current"))]
            if kind == "media":
                for root in roots[1:]:
                    for name in _GENERATED_MANIFEST_FILENAMES:
                        if (root / "json" / name).read_bytes() != (active / "json" / name).read_bytes():
                            return False
            else:
                index = fetch_library_apps_index_payload(bundle)
                for root in roots:
                    if index is not None and json.loads((root / "apps-index.json").read_bytes()) != index:
                        return False
                    for entry_key, filename in SHARED_DICTIONARIES:
                        entry = library_dictionary_entry(bundle, entry_key)
                        if entry is not None and file_sha256(root / "metadata" / filename) != entry["sha256"]:
                            return False
    except (OSError, ValueError):
        return False
    return True


def validate_saved_asset_snapshot(state: dict[str, object], media: Path, library: Path) -> None:
    version = state.get("datasetVersion")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", version):
        raise AppStoreTransientError("snapshot has no valid dataset identity")
    manifests = state.get("manifests")
    digests = state.get("assetDigests")
    if not isinstance(manifests, dict) or not isinstance(digests, dict):
        raise AppStoreTransientError("snapshot has no verified contract and content record")
    root = manifests.get("root")
    if not isinstance(root, dict):
        raise AppStoreTransientError("snapshot has no root manifest")
    check_appstore_compatibility(root)
    if state.get("datasetVersion") != root.get("datasetVersion") or state.get("schemaVersion") != root.get("schemaVersion"):
        raise AppStoreTransientError("snapshot root identity does not match saved state")
    if "channel" in root and root["channel"] != state.get("channel"):
        raise AppStoreTransientError("snapshot root channel does not match saved state")
    for component in ("catalog", "library"):
        manifest = manifests.get(component)
        _validate_component_version(root, component, manifest, state.get("channel"))
        if manifest.get("schemaVersion") != state.get(f"{component}SchemaVersion"):
            raise AppStoreTransientError(f"snapshot {component} contract does not match saved state")
        if manifest.get("datasetVersion") != state.get(f"{component}DatasetVersion"):
            raise AppStoreTransientError(f"snapshot {component} version does not match saved state")
    for kind, source in (("media", media), ("library", library)):
        if not isinstance(digests.get(kind), str) or tree_content_fingerprint(source) != digests[kind]:
            raise AppStoreTransientError(f"snapshot {kind} content does not match saved state")
    validate_runtime_asset_roots(media, library)
    index = manifests.get("appsIndex")
    if "appsIndex" in manifests["library"] and not isinstance(index, dict):
        raise AppStoreTransientError("snapshot has no verified library index")
    bundle = {
        "appstore_manifest": root,
        "catalog_manifest": manifests["catalog"],
        "library_manifest": manifests["library"],
        "library_manifest_url": (library.resolve() / "manifest.json").as_uri(),
        "_verified_library_json": {"appsIndex": index} if isinstance(index, dict) else {},
    }
    verify_catalog_source(media, bundle)
    verify_library_source(library, bundle, full_package=True)
    for entry_key, filename in SHARED_DICTIONARIES:
        entry = library_dictionary_entry(bundle, entry_key)
        if entry is not None and file_sha256(library / "metadata" / filename) != entry["sha256"]:
            raise AppStoreTransientError(f"snapshot {entry_key} checksum mismatch")


def reload_runtime_app_store_manifests() -> dict[str, object]:
    lock = acquire_appstore_sync_lock(Path(os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")))
    if lock is None:
        raise AppStoreTransientError("Appstore synchronization is running; retry the catalog refresh later")
    with lock, tempfile.TemporaryDirectory(prefix="websoft9-appstore-reload-") as directory:
        state_path = _resolve_sync_state_path()
        state = load_sync_state(state_path)
        availability = load_sync_state(runtime_assets_status_path())
        if availability.get("status") != "ready" or availability.get("datasetVersion") != state.get("datasetVersion"):
            raise AppStoreTransientError("Official Appstore assets are not ready; synchronize before refreshing")
        media = Path(os.getenv("WEBSOFT9_MEDIA_ROOT", "/websoft9/media"))
        library = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
        try:
            validate_saved_asset_snapshot(state, media, library)
        except (OSError, ValueError, RuntimeError) as exc:
            write_runtime_assets_status("unavailable", f"Official Appstore assets failed validation: {exc}")
            raise
        work = Path(directory)
        staged_media = work / "media"
        sync_tree(media, staged_media, exclude_uploaded_media=True)
        build_and_publish_app_store_manifests(staged_media, library)
        validate_runtime_asset_roots(staged_media, library)
        digest = tree_content_fingerprint(staged_media)
        loaded = {
            locale: len(json.loads((staged_media / "json" / f"app-store-manifest_{locale}.json").read_bytes())["apps"])
            for locale in ("zh", "en")
        }
        if digest == state["assetDigests"]["media"]:
            return {"loaded": loaded, "errors": []}
        snapshot_root = Path(state["snapshotRoot"])
        targets = [
            media,
            snapshot_root / "staging" / state["datasetVersion"] / "media",
            snapshot_root / "releases" / state["datasetVersion"] / "media",
            snapshot_root / "current" / "media",
        ]
        backups = backup_trees(targets, work / "backup")
        write_runtime_assets_status("updating", "Appstore browsing manifests are being refreshed")
        try:
            replace_media_tree(staged_media, media)
            paths = stage_snapshot(staged_media, snapshot_root, state["datasetVersion"], "media")
            refreshed = {
                **state,
                "assetDigests": {**state["assetDigests"], "media": digest},
                "snapshots": {**state["snapshots"], "media": {key: str(value) for key, value in paths.items()}},
            }
            validate_saved_asset_snapshot(refreshed, media, library)
            write_sync_state(state_path, refreshed)
            write_runtime_assets_status("ready", dataset_version=state["datasetVersion"])
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            rollback_ok = True
            try:
                restore_trees(backups)
                write_sync_state(state_path, state)
            except OSError as rollback_exc:
                rollback_ok = False
                log(f"[platform-assets] catalog refresh rollback failed: {rollback_exc}")
            restore_runtime_assets_status(availability, rollback_ok)
            log(f"[platform-assets] catalog refresh failed: {exc}")
            raise
        return {"loaded": loaded, "errors": []}


def _intact_persistent_recovery_paths(
    state: dict[str, object], media: Path, library: Path, snapshot_root: Path
) -> dict[str, dict[str, str]] | None:
    version = state.get("datasetVersion")
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", version)
        or state.get("snapshotRoot") != str(snapshot_root)
    ):
        return None
    try:
        validate_saved_asset_snapshot(state, media, library)
        digests = state["assetDigests"]
        paths: dict[str, dict[str, str]] = {}
        for kind in ("media", "library"):
            kind_paths = {
                "staging": snapshot_root / "staging" / version / kind,
                "release": snapshot_root / "releases" / version / kind,
                "current": snapshot_root / "current" / kind,
            }
            if any(tree_content_fingerprint(path) != digests[kind] for path in kind_paths.values()):
                return None
            paths[kind] = {key: str(value) for key, value in kind_paths.items()}
        return paths
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        return None


def recover_runtime_assets() -> int:
    """Restore a complete locally verified dataset without contacting the publisher."""
    write_runtime_assets_status("unavailable", "Appstore assets have not been verified in this container")
    state_path = _resolve_sync_state_path()
    previous = load_sync_state(state_path)
    media = Path(os.getenv("WEBSOFT9_MEDIA_ROOT", "/websoft9/media"))
    library = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
    snapshot_root = Path(os.getenv(
        "WEBSOFT9_APP_STORE_SNAPSHOT_ROOT",
        str(Path(os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")) / "appstore"),
    ))
    intact_paths = _intact_persistent_recovery_paths(previous, media, library, snapshot_root)
    if intact_paths is not None:
        try:
            restored = dict(previous)
            restored.update(snapshotRoot=str(snapshot_root), snapshots=intact_paths, recovery={"source": "active-assets"})
            write_sync_state(state_path, restored)
            write_runtime_assets_status("ready", "Verified active-assets", previous["datasetVersion"])
            log(f"[platform-assets] verified intact active dataset {previous['datasetVersion']}; no recovery copy required")
            return 0
        except (OSError, ValueError, RuntimeError) as exc:
            try:
                write_sync_state(state_path, previous)
            except OSError as state_exc:
                log(f"[platform-assets] failed to restore recovery state: {state_exc}")
            log(f"[platform-assets] recovery activation failed: {exc}")
            write_runtime_assets_status("unavailable", f"Appstore recovery failed: {exc}")
            return 1

    image_state_path = Path(os.getenv("WEBSOFT9_APPSTORE_IMAGE_STATE", "/websoft9/appstore/image-state.json"))
    image = load_sync_state(image_state_path)
    candidates = []
    for label, state in (("persistent-snapshot", previous), ("image-baseline", image)):
        version = state.get("datasetVersion")
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", version):
            continue
        root = state.get("snapshotRoot")
        if not isinstance(root, str) or not root:
            continue
        release = Path(root) / "releases" / version
        candidates.append((label, state, release / "media", release / "library"))
    candidates.insert(1 if candidates and candidates[0][0] == "persistent-snapshot" else 0,
                      ("active-assets", previous, media, library))
    for label, state, source_media, source_library in candidates:
        try:
            validate_saved_asset_snapshot(state, source_media, source_library)
        except (OSError, ValueError, RuntimeError) as exc:
            log(f"[platform-assets] cannot recover {label}: {exc}")
            continue
        with tempfile.TemporaryDirectory(prefix="websoft9-appstore-recover-") as directory:
            work = Path(directory)
            backups = {}
            try:
                # Stage both before touching either live tree, including when adopting active assets.
                for kind, source in (("media", source_media), ("library", source_library)):
                    sync_tree(source, work / kind, exclude_uploaded_media=(kind == "media"))
                validate_saved_asset_snapshot(state, work / "media", work / "library")
                targets = [media, library]
                for kind in ("media", "library"):
                    targets.extend([
                        snapshot_root / "staging" / state["datasetVersion"] / kind,
                        snapshot_root / "releases" / state["datasetVersion"] / kind,
                        snapshot_root / "current" / kind,
                    ])
                backups = backup_trees(targets, work / "backup")
                paths = {}
                for kind, target in (("media", media), ("library", library)):
                    if kind == "media":
                        replace_media_tree(work / kind, target)
                    else:
                        replace_tree(work / kind, target)
                    paths[kind] = {
                        key: str(value) for key, value in stage_snapshot(
                            work / kind, snapshot_root, state["datasetVersion"], kind
                        ).items()
                    }
                validate_saved_asset_snapshot(state, media, library)
                restored = dict(state)
                restored.update(snapshotRoot=str(snapshot_root), snapshots=paths, recovery={"source": label})
                write_sync_state(state_path, restored)
                write_runtime_assets_status("ready", f"Restored verified {label}", state["datasetVersion"])
                log(f"[platform-assets] restored complete verified dataset {state['datasetVersion']} from {label}")
                return 0
            except (OSError, ValueError, RuntimeError) as exc:
                if backups:
                    try:
                        restore_trees(backups)
                    except OSError as rollback_exc:
                        log(f"[platform-assets] recovery rollback failed: {rollback_exc}")
                try:
                    write_sync_state(state_path, previous)
                except OSError as state_exc:
                    log(f"[platform-assets] failed to restore recovery state: {state_exc}")
                log(f"[platform-assets] recovery activation failed: {exc}")
                write_runtime_assets_status("unavailable", f"Appstore recovery failed: {exc}")
                return 1
    write_runtime_assets_status("unavailable", "No complete verified Appstore snapshot is available; synchronize before installing")
    return 1


def main() -> int:
    channel = detect_channel()
    artifact_base = os.getenv("WEBSOFT9_ARTIFACT_BASE", "https://artifact.websoft9.com")
    sync_mode = (os.getenv("WEBSOFT9_RUNTIME_ASSET_SYNC_MODE") or "runtime").strip().lower()
    config_path = Path(
        os.getenv("WEBSOFT9_APPHUB_CONFIG_PATH")
        or os.getenv("WEBSOFT9_APPHUB_CONFIG", "/websoft9/apphub/src/config/config.ini")
    )
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    sync_state_path = _resolve_sync_state_path()
    snapshot_root = Path(os.getenv(
        "WEBSOFT9_APP_STORE_SNAPSHOT_ROOT",
        "/websoft9/appstore" if sync_mode == "build" else str(Path(data_root) / "appstore"),
    ))

    packages = [
        (
            "media",
            Path(os.getenv("WEBSOFT9_MEDIA_ROOT", "/websoft9/media")),
            Path(os.getenv("WEBSOFT9_MEDIA_MARKER", "/websoft9/media/json/product_en.json")),
        ),
        (
            "library",
            Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library")),
            Path(os.getenv("WEBSOFT9_LIBRARY_MARKER", "/websoft9/library/apps")),
        ),
    ]

    requested_package_types = {
        item.strip()
        for item in (os.getenv("WEBSOFT9_RUNTIME_ASSET_TYPES", "media,library")).split(",")
        if item.strip()
    }

    if requested_package_types != {"media", "library"}:
        raise RuntimeError("app store sync requires both media and library packages")

    if requested_package_types:
        packages = [package for package in packages if package[0] in requested_package_types]

    # Serialise every sync trigger.  Runtime bootstrap, daily cron, CLI and the API all funnel
    # through this lock, so concurrent runs can never rewrite the same trees.  Image builds run
    # alone and must not create runtime state, so they skip locking entirely.
    sync_lock = None
    if sync_mode != "build":
        try:
            sync_lock = acquire_appstore_sync_lock(Path(data_root))
        except OSError as exc:
            log(f"[platform-assets] Appstore sync lock unavailable; refusing an unlocked update: {exc}")
            return 1
        if sync_lock is None:
            log("[platform-assets] another Appstore sync is already running; skipping this round")
            return 0
        write_appstore_sync_pid_marker()

    rollback_backups: dict[Path, Path | None] = {}
    rollback_root: Path | None = None
    prefetch_root: Path | None = None
    previous_availability = load_sync_state(runtime_assets_status_path())
    updating_assets = False
    previous_state: dict[str, object] = {}
    try:
        previous_state = load_sync_state(sync_state_path)
        baseline_untrusted = bool(previous_state.get("partial")) or bool(
            previous_state and not _local_runtime_trees_match_state(previous_state)
        ) or (sync_mode != "build" and previous_availability.get("status") != "ready")
        if baseline_untrusted:
            log("[platform-assets] local runtime assets do not match recorded sync state; forcing full synchronization")
            if sync_mode != "build":
                previous_availability = {
                    "status": "unavailable", "message": "Appstore assets require a complete verified synchronization",
                }
                write_sync_state(runtime_assets_status_path(), previous_availability)
        force_refresh = is_force_refresh_enabled() or baseline_untrusted
        manifest_bundle = None
        latest_dataset_version = None
        latest_generated_at = None
        latest_schema_version = None
        latest_catalog_dsv = None
        latest_library_dsv = None
        should_skip_package_sync = False
        applied_dataset_version = None
        package_snapshot_paths: dict[str, dict[str, str]] = {}
        library_delta_context = None
        package_sync_plan = {
            "media": True,
            "library": True,
        }

        media_root = Path(os.getenv("WEBSOFT9_MEDIA_ROOT", "/websoft9/media"))
        library_root = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
        try:
            manifest_bundle = with_transient_retry(
                lambda: fetch_appstore_manifests(artifact_base, channel, None),
                label="appstore manifest fetch",
            )
            appstore_manifest = manifest_bundle["appstore_manifest"]
            if isinstance(appstore_manifest, dict):
                latest_schema_version = appstore_manifest.get("schemaVersion")
                latest_dataset_version = appstore_manifest.get("datasetVersion")
                latest_generated_at = appstore_manifest.get("generatedAt")
                # Resolve per-component datasetVersions (v2) for state tracking
                latest_catalog_dsv = _resolve_component_dataset_version(appstore_manifest, "catalog")
                latest_library_dsv = _resolve_component_dataset_version(appstore_manifest, "library")
                if not force_refresh and _appstore_dataset_already_active(
                    appstore_manifest, previous_state, force_refresh, manifest_bundle
                ):
                    catalog_unchanged = (not latest_catalog_dsv
                                         or latest_catalog_dsv == previous_state.get("catalogDatasetVersion"))
                    library_unchanged = (not latest_library_dsv
                                         or latest_library_dsv == previous_state.get("libraryDatasetVersion"))
                    if catalog_unchanged and library_unchanged:
                        should_skip_package_sync = True
                        log(f"[platform-assets] appstore dataset {latest_dataset_version} already active for channel {channel}")
                if not should_skip_package_sync:
                    full_library_sync = library_requires_full_sync(manifest_bundle, previous_state, library_root)
                    package_sync_plan = (
                        {
                            "media": (
                                not latest_catalog_dsv
                                or latest_catalog_dsv != previous_state.get("catalogDatasetVersion")
                                or (manifest_bundle.get("catalog_manifest") or {}).get("schemaVersion")
                                != previous_state.get("catalogSchemaVersion")
                            ),
                            "library": True,
                        }
                        if full_library_sync
                        else determine_package_sync_plan(manifest_bundle, previous_state, latest_dataset_version)
                    )
                    library_delta_context = None if full_library_sync else resolve_library_delta_context(
                        manifest_bundle,
                        # ``appsDelta`` chains library dataset versions, not the root Appstore one.
                        previous_state.get("libraryDatasetVersion") or previous_state.get("datasetVersion"),
                        latest_library_dsv if latest_library_dsv is not None else latest_dataset_version,
                    )
                    if not full_library_sync and not force_refresh and fetch_library_apps_index_payload(manifest_bundle) is not None:
                        reconciled = resolve_library_index_delta_context(
                            manifest_bundle, previous_state,
                            Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library")), channel,
                        )
                        if reconciled is None:
                            library_delta_context = None
                            package_sync_plan["library"] = True
                        else:
                            if library_delta_context is None or any(
                                library_delta_context.get(key, []) != reconciled[key]
                                for key in ("addedApps", "changedApps", "removedApps", "updatedApps")
                            ):
                                library_delta_context = reconciled
                            else:
                                library_delta_context["indexReconciled"] = True
                            package_sync_plan["library"] = any(
                                reconciled[key] for key in ("addedApps", "changedApps", "removedApps")
                            )
                    if full_library_sync:
                        library_delta_context = None
                        package_sync_plan["library"] = True
        except AppStoreCompatibilityError:
            raise
        except AppStoreManifestNotFoundError as exc:
            raise AppStoreTransientError(f"Appstore root manifest is unavailable: {exc}") from exc
        except AppStoreTransientError:
            # Exhausted the retries: fail with the dataset untouched instead of silently falling
            # back to legacy package resolution, which would install unrelated artifacts.
            raise

        applied_dataset_version = latest_dataset_version or previous_state.get("datasetVersion") or datetime.datetime.utcnow().strftime("%Y.%m.%d.%H%M%S")
        should_rebuild_manifests = not (
            should_skip_package_sync and has_valid_published_app_store_manifests(media_root)
        )

        if should_skip_package_sync and isinstance(previous_state.get("snapshots"), dict):
            package_snapshot_paths = dict(previous_state["snapshots"])
        if (
            should_skip_package_sync
            and not should_rebuild_manifests
            and runtime_metadata_matches(media_root, library_root, previous_state, manifest_bundle)
        ):
            unchanged_state = dict(previous_state)
            unchanged_state.pop("lastSyncError", None)
            unchanged_state.pop("incompatibility", None)
            unchanged_state.update(
                syncStatus="ready",
                lastSyncedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                syncMode=sync_mode,
                updated=False,
                packageSyncPlan={"media": False, "library": False},
            )
            unchanged_state["manifests"] = {
                "root": manifest_bundle["appstore_manifest"],
                "catalog": manifest_bundle["catalog_manifest"],
                "library": manifest_bundle["library_manifest"],
                "appsIndex": (manifest_bundle.get("_verified_library_json") or {}).get("appsIndex"),
            }
            write_sync_state(sync_state_path, unchanged_state)
            log(f"[platform-assets] verified unchanged dataset {applied_dataset_version}; no asset writes required")
            return 0

        prefetched_sources = {}
        prefetched_dictionaries = {}
        if not should_skip_package_sync:
            prefetch_packages = [
                package for package in packages
                if not (package[0] == "library" and not force_refresh and library_delta_context is not None)
            ]
            prefetched_sources, prefetch_root = prefetch_pending_packages(
                prefetch_packages, package_sync_plan, force_refresh, channel, artifact_base, manifest_bundle,
            )
            if not force_refresh and library_delta_context is not None:
                if prefetch_root is None:
                    prefetch_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-prefetch-"))
                reusable_library = library_root if library_delta_context.get("indexReconciled") else resolve_reusable_package_source(
                    previous_state, "library", library_root, packages[1][2],
                )
                if reusable_library is not None:
                    try:
                        prefetched_sources["library"] = with_transient_retry(
                            lambda: prepare_library_app_artifacts_source(
                                reusable_library, manifest_bundle, library_delta_context, prefetch_root / "app-artifacts",
                            ),
                            label="library app artifacts prefetch",
                        )
                    except AppStoreTransientError:
                        raise
                    except (OSError, ValueError, RuntimeError) as exc:
                        log(f"[platform-assets] app-level prefetch unavailable; preparing the full library: {exc}")
                        library_delta_context = None
                        prefetched_sources["library"] = with_transient_retry(
                            lambda: prepare_package_source(
                                "library", channel, artifact_base, manifest_bundle, prefetch_root / "library-fallback",
                            ),
                            label="library fallback prefetch",
                        )

        for entry_key, filename in SHARED_DICTIONARIES:
            entry = library_dictionary_entry(manifest_bundle, entry_key)
            if entry is None:
                continue
            source = prefetched_sources.get("library", library_root) / "metadata" / filename
            if source.is_file() and file_sha256(source) == entry["sha256"]:
                prefetched_dictionaries[entry_key] = source
                continue
            if prefetch_root is None:
                prefetch_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-prefetch-"))
            source = prefetch_root / "dictionaries" / filename
            with_transient_retry(
                lambda entry_key=entry_key, filename=filename, source=source: sync_shared_dictionary(
                    manifest_bundle, [source], entry_key=entry_key, filename=filename,
                ),
                label=f"{entry_key} dictionary prefetch",
            )
            prefetched_dictionaries[entry_key] = source

        if sync_mode != "build":
            write_runtime_assets_status("updating", "Appstore assets are being updated")
            updating_assets = True
        rollback_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-sync-rollback-"))
        rollback_targets = [
            target
            for package_type, target_dir, _ in packages
            for target in (target_dir, snapshot_root / "current" / package_type)
        ]
        for package_type, _, _ in packages:
            for area in ("staging", "releases"):
                rollback_targets.append(snapshot_root / area / str(applied_dataset_version) / package_type)
            old_paths = (previous_state.get("snapshots") or {}).get(package_type, {})
            if isinstance(old_paths, dict):
                rollback_targets.extend(Path(value) for value in old_paths.values() if isinstance(value, str) and value)
        rollback_targets = list({target.resolve(): target for target in rollback_targets}.values())
        rollback_backups = backup_trees(rollback_targets, rollback_root)

        if not should_skip_package_sync:
            for package_type, target_dir, marker_path in packages:
                reusable_source = resolve_reusable_package_source(previous_state, package_type, target_dir, marker_path)
                if package_type == "library" and isinstance(library_delta_context, dict) and library_delta_context.get("indexReconciled"):
                    reusable_source = library_root
                if not force_refresh and not package_sync_plan.get(package_type, True):
                    if reusable_source is not None:
                        if package_type == "library":
                            verify_library_source(reusable_source, manifest_bundle)
                        log(f"[platform-assets] skipping {package_type} package sync because manifest deltas report no changes; reusing {reusable_source}")
                        package_snapshot_paths[package_type] = promote_existing_package_snapshot(
                            reusable_source,
                            target_dir,
                            marker_path,
                            snapshot_root,
                            str(applied_dataset_version),
                            package_type,
                        )
                        continue

                    log(f"[platform-assets] manifest deltas report no {package_type} changes but no reusable source was found; falling back to full sync")
                if (
                    package_type == "library"
                    and not force_refresh
                    and reusable_source is not None
                    and isinstance(library_delta_context, dict)
                ):
                    package_snapshot_paths[package_type] = sync_library_app_artifacts_delta(
                        reusable_source,
                        target_dir,
                        marker_path,
                        manifest_bundle,
                        snapshot_root,
                        str(applied_dataset_version),
                        library_delta_context,
                        prefetched_source=prefetched_sources.get("library"),
                    )
                    continue
                snapshot_paths = with_transient_retry(
                    lambda: sync_package(
                        package_type,
                        target_dir,
                        marker_path,
                        channel,
                        artifact_base,
                        manifest_bundle,
                        snapshot_root,
                        str(applied_dataset_version),
                        force_sync=force_refresh or package_sync_plan.get(package_type, True),
                        prefetched_source=prefetched_sources.get(package_type),
                    ),
                    label=f"{package_type} package sync",
                )
                if snapshot_paths:
                    package_snapshot_paths[package_type] = snapshot_paths

        # Keep the shared dictionaries current. They ship inside the full package only, so an
        # installation that keeps taking per-app deltas would otherwise freeze the dictionaries
        # at whatever version its last full sync carried — including dictionary-only releases
        # where the app delta is empty. Runs even when no package was synced.
        dictionary_reports: dict[str, dict[str, str]] = {}
        if should_skip_package_sync:
            verify_library_source(library_root, manifest_bundle)
        verify_catalog_source(media_root, manifest_bundle)
        for dictionary_entry_key, dictionary_filename in SHARED_DICTIONARIES:
            report = with_transient_retry(
                lambda entry_key=dictionary_entry_key, filename=dictionary_filename: sync_shared_dictionary(
                    manifest_bundle,
                    library_dictionary_targets(library_root, package_snapshot_paths, filename),
                    entry_key=entry_key,
                    filename=filename,
                    prefetched_source=prefetched_dictionaries.get(entry_key),
                ),
                label=f"{dictionary_entry_key} dictionary sync",
            )
            dictionary_reports[dictionary_entry_key] = report
            if report.get("status") == "updated":
                log(f"[platform-assets] synced shared {dictionary_entry_key} dictionary {report.get('sha256')}")

        # Persist the library apps index next to the active library and inside this dataset's
        # snapshots, so the manifest build and a later offline activation both see the per-app
        # update times. A declared index must be verified and published before state advances.
        library_snapshot_paths = package_snapshot_paths.get("library")
        apps_index_targets: list[Path] = []
        if isinstance(library_snapshot_paths, dict):
            for snapshot_key in ("staging", "release", "current"):
                snapshot_value = library_snapshot_paths.get(snapshot_key)
                if isinstance(snapshot_value, str) and snapshot_value:
                    apps_index_targets.append(Path(snapshot_value) / "apps-index.json")
        apps_index_written = publish_library_apps_index(library_root, manifest_bundle, apps_index_targets)
        if not apps_index_written:
            raise RuntimeError("apps index: not every target could be written")

        if not should_rebuild_manifests:
            log(f"[platform-assets] skipping manifest rebuild for unchanged dataset {applied_dataset_version}")
        else:
            build_and_publish_app_store_manifests(media_root, library_root)

        if not package_snapshot_paths and isinstance(previous_state.get("snapshots"), dict):
            package_snapshot_paths = dict(previous_state["snapshots"])

        validate_runtime_asset_roots(media_root, library_root)
        media_snapshots = package_snapshot_paths.get("media", {})
        generated = {
            f"app-store-manifest_{locale}.json": json.loads(
                (media_root / "json" / f"app-store-manifest_{locale}.json").read_bytes()
            )
            for locale in ("en", "zh")
        }
        publish_json_files({
            Path(path) / "json" / name: payload
            for path in media_snapshots.values()
            for name, payload in generated.items()
        })
        state_payload: dict[str, object] = {
            "syncStatus": "ready",
            "channel": channel,
            "schemaVersion": latest_schema_version,
            "datasetVersion": applied_dataset_version,
            "generatedAt": latest_generated_at,
            "lastSyncedAt": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "syncMode": sync_mode,
            "updated": not should_skip_package_sync,
            "snapshotRoot": str(snapshot_root),
            "snapshots": package_snapshot_paths,
            "packageSyncPlan": package_sync_plan,
            "assetDigests": {
                "media": tree_content_fingerprint(media_root),
                "library": tree_content_fingerprint(library_root),
            },
            "manifests": {
                "root": manifest_bundle["appstore_manifest"],
                "catalog": manifest_bundle["catalog_manifest"],
                "library": manifest_bundle["library_manifest"],
                "appsIndex": (manifest_bundle.get("_verified_library_json") or {}).get("appsIndex"),
            },
        }
        for component in ("catalog", "library"):
            component_manifest = manifest_bundle.get(f"{component}_manifest")
            if isinstance(component_manifest, dict) and component_manifest.get("schemaVersion"):
                state_payload[f"{component}SchemaVersion"] = component_manifest["schemaVersion"]
        if latest_catalog_dsv is not None:
            state_payload["catalogDatasetVersion"] = latest_catalog_dsv
        if latest_library_dsv is not None:
            state_payload["libraryDatasetVersion"] = latest_library_dsv
        for dictionary_entry_key, _ in SHARED_DICTIONARIES:
            state_key = _dictionary_state_key(dictionary_entry_key)
            digest = dictionary_reports.get(dictionary_entry_key, {}).get("sha256") or previous_state.get(state_key)
            if isinstance(digest, str) and digest:
                state_payload[state_key] = digest
        write_sync_state(sync_state_path, state_payload)
        if sync_mode != "build":
            write_runtime_assets_status("ready", dataset_version=applied_dataset_version)
        log(f"[platform-assets] completed app store manifest build (mode={sync_mode})")

        try:
            removed_datasets = prune_stale_appstore_datasets(
                snapshot_root,
                str(applied_dataset_version) if applied_dataset_version else None,
            )
            if removed_datasets:
                log(f"[platform-assets] removed stale App Store datasets: {', '.join(sorted(removed_datasets))}")
        except OSError as exc:
            log(f"[platform-assets] dataset committed; stale dataset cleanup failed: {exc}")
    except AppStoreCompatibilityError as exc:
        rollback_ok = True
        if rollback_backups:
            try:
                restore_trees(rollback_backups)
                log("[platform-assets] restored active assets after incompatible appstore update")
            except Exception as rollback_exc:
                rollback_ok = False
                log(f"[platform-assets] failed to restore active assets after incompatible update: {rollback_exc}")
        if updating_assets:
            restore_runtime_assets_status(previous_availability, rollback_ok)
        incompatible_state = dict(previous_state)
        incompatible_state.pop("lastSyncError", None)
        incompatible_state.update(
            {
                "syncStatus": "incompatible",
                "lastSyncAttemptAt": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "incompatibility": {"message": str(exc), "upgradeRequired": exc.upgrade_required},
            }
        )
        write_sync_state(sync_state_path, incompatible_state)
        log(f"[platform-assets] app store update is incompatible: {exc}")
        return 1
    except Exception as exc:
        rollback_ok = True
        if rollback_backups:
            try:
                restore_trees(rollback_backups)
                log("[platform-assets] restored active assets after failed sync")
            except Exception as rollback_exc:
                rollback_ok = False
                log(f"[platform-assets] failed to restore active assets after sync failure: {rollback_exc}")
        if updating_assets:
            restore_runtime_assets_status(previous_availability, rollback_ok)
        log(f"[platform-assets] asset sync failed (mode={sync_mode}): {exc}")
        failure_state = dict(previous_state)
        failure_state.pop("incompatibility", None)
        failure_state.update(
            syncStatus="failed",
            lastSyncAttemptAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            lastSyncError=str(exc),
        )
        try:
            write_sync_state(sync_state_path, failure_state)
        except OSError as state_exc:
            log(f"[platform-assets] failed to persist sync failure: {state_exc}")
        return 1
    finally:
        if prefetch_root is not None:
            shutil.rmtree(prefetch_root, ignore_errors=True)
        if rollback_root is not None:
            shutil.rmtree(rollback_root, ignore_errors=True)
        if sync_lock is not None:
            sync_lock.close()

    return 0


if __name__ == "__main__":
    sys.exit(recover_runtime_assets() if sys.argv[1:] == ["--recover-only"] else main())