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
import urllib.request
import zipfile
from pathlib import Path

# Appstore synchronization is triggered from several places (runtime bootstrap, daily cron,
# CLI, AppHub API).  The lock file serialises them; the PID marker file only feeds the
# "sync running" status that the console shows.
_APPSTORE_SYNC_LOCK_FILE_DEFAULT = "/opt/websoft9/data/config/appstore_sync.lock"
_APPSTORE_SYNC_PID_FILE_DEFAULT = "/tmp/websoft9-appstore-sync.lock"
_APPSTORE_SYNC_LOCK_POLL_SECONDS = 0.5
# Sentinel for "the platform cannot host a lock file"; a sync still runs, it just is not serialised.
_APPSTORE_SYNC_LOCK_UNAVAILABLE = object()

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover - bootstrap fallback
    dotenv_values = None

# Library .env files may contain Compose interpolation that python-dotenv does
# not parse. The values we need remain available, so avoid emitting one warning
# per unsupported line during normal Appstore synchronization.
logging.getLogger("dotenv.main").setLevel(logging.ERROR)


ENV_REFERENCE_PATTERN = re.compile(r"\$\{?(\w+)\}?")

# ── v2 manifest URL templates ──────────────────────────────────────────
_V2_APPSTORE_MANIFEST_PATH = "appstore/{channel}/manifests/appstore-manifest.json"


class AppStoreCompatibilityError(RuntimeError):
    """Raised when an App Store dataset requires a newer Websoft9 runtime."""


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
    local_schema_version: str | None,
    websoft9_version: str | None = None,
) -> None:
    schema_version = appstore_manifest.get("schemaVersion")
    if local_schema_version is not None and schema_version != local_schema_version:
        raise AppStoreCompatibilityError(
            f"appstore schemaVersion {schema_version!r} does not match the active local schemaVersion "
            f"{local_schema_version!r}. "
            "Please upgrade your Websoft9 platform."
        )

    minimum_version = appstore_manifest.get("minWebsoft9Version")
    if minimum_version is None:
        return

    current_version = websoft9_version or get_websoft9_version()
    if _parse_version(current_version, "Websoft9 version") < _parse_version(minimum_version, "minWebsoft9Version"):
        raise AppStoreCompatibilityError(
            f"appstore requires Websoft9 >= {minimum_version}; current version is {current_version}. "
            "Please upgrade your Websoft9 platform."
        )


def log(message: str) -> None:
    print(message, flush=True)


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


def sync_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
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


def replace_tree_preserving_generated_manifests(source: Path, target: Path) -> None:
    """Replace a runtime tree without ever exposing a missing published manifest.

    The previously published manifests are written back before the payload is copied in, so the
    App Store stays readable for the whole replacement instead of failing until the manifests are
    rebuilt at the end of the sync.
    """
    target_dir = target.resolve() if target.is_symlink() else target
    preserved = preserve_generated_manifests(source) or preserve_generated_manifests(target_dir)

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    restore_generated_manifests(target_dir, preserved)
    sync_tree(source, target_dir)


def _hardlink_or_copy_file(source: str, destination: str, *, follow_symlinks: bool = True) -> str:
    """Hard-link a file when both paths live on the same filesystem, otherwise copy it."""
    try:
        os.link(source, destination, follow_symlinks=follow_symlinks)
        return destination
    except OSError:
        return shutil.copy2(source, destination, follow_symlinks=follow_symlinks)


def link_or_copy_tree(source: Path, target: Path) -> None:
    """Materialise a tree with hard links where possible.

    Snapshot copies inside the App Store root share file contents instead of duplicating
    hundreds of megabytes on every sync.  Cross-device targets (for example the data volume)
    transparently fall back to real copies.
    """
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True, copy_function=_hardlink_or_copy_file)
        else:
            _hardlink_or_copy_file(str(item), str(destination))


def replace_tree_linked(source: Path, target: Path) -> None:
    """Replace a tree, linking file contents instead of copying them when possible."""
    target_dir = target.resolve() if target.is_symlink() else target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    link_or_copy_tree(source, target_dir)


def replace_tree(source: Path, target: Path) -> None:
    target_dir = target.resolve() if target.is_symlink() else target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    sync_tree(source, target_dir)


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

    with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def download_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "application/json,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "text/plain,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def resolve_json_url(base_url: str, relative_path: str) -> str:
    """Resolve a relative path against a manifest URL.

    urljoin treats base_url as a file when the path does not end with /,
    automatically stripping the last component before resolution.
    """
    return urllib.request.urljoin(base_url, relative_path)


def acquire_appstore_sync_lock(data_root: Path):
    """Take the cross-process Appstore sync lock.

    The process that owns the returned handle keeps the lock until it exits, so two syncs can
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
        raise RuntimeError(f"checksum mismatch for {relative_path}: expected {expected_checksum}, got {actual_checksum}")


def load_sync_state(state_path: Path) -> dict[str, object]:
    if not state_path.exists():
        return {}

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def write_sync_state(state_path: Path, payload: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


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
        if isinstance(catalog_rel, str) and isinstance(library_rel, str):
            return catalog_rel, library_rel

    # Legacy: { "domains": { "catalog": "...", "library": "..." } }
    domains = appstore_manifest.get("domains")
    if isinstance(domains, dict):
        catalog_rel = domains.get("catalog")
        library_rel = domains.get("library")
        if isinstance(catalog_rel, str) and isinstance(library_rel, str):
            return catalog_rel, library_rel

    raise RuntimeError(f"appstore manifest has unrecognized structure: {manifest_url}")


def _resolve_sync_state_path() -> Path:
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    return Path(os.getenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(Path(data_root) / "config" / "appstore_sync_state.json")))


def _appstore_dataset_already_active(
    appstore_manifest: dict[str, object],
    previous_state: dict[str, object] | None,
    force_refresh: bool,
) -> bool:
    """Report whether the remote dataset is already active locally.

    The root manifest carries the dataset and per-component versions, so an unchanged dataset
    can be detected without downloading the catalog/library manifests at all.
    """
    if force_refresh:
        return False
    if not isinstance(previous_state, dict) or not previous_state:
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
    appstore_manifest = download_json(appstore_manifest_url)
    if not isinstance(appstore_manifest, dict):
        raise RuntimeError(f"invalid appstore manifest payload: {appstore_manifest_url}")

    check_appstore_compatibility(appstore_manifest, local_schema_version)

    # Fast path: when the dataset is already active, the component manifests (and the apps
    # index that only feeds the manifest builder) carry no new information.  Each of those
    # requests costs a full round trip to the artifact server, which dominates start-up time.
    if _appstore_dataset_already_active(appstore_manifest, previous_state, force_refresh):
        log(
            "[platform-assets] appstore dataset "
            f"{appstore_manifest.get('datasetVersion')} already active; component manifests not requested"
        )
        return {
            "appstore_manifest_url": appstore_manifest_url,
            "catalog_manifest_url": None,
            "library_manifest_url": None,
            "appstore_manifest": appstore_manifest,
            "catalog_manifest": None,
            "library_manifest": None,
            "componentManifestsSkipped": True,
        }

    catalog_relative, library_relative = _resolve_manifest_domains(appstore_manifest, appstore_manifest_url)

    # Sub-manifest paths (e.g. "catalog/manifest.json") are relative to the
    # appstore channel root, NOT to the root manifest URL (which lives under
    # manifests/).  Construct the absolute URLs from the channel base.
    appstore_base = f"{artifact_base}/appstore/{channel}"
    catalog_manifest_url = f"{appstore_base}/{catalog_relative}"
    library_manifest_url = f"{appstore_base}/{library_relative}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        catalog_future = executor.submit(download_json, catalog_manifest_url)
        library_future = executor.submit(download_json, library_manifest_url)
        catalog_manifest = catalog_future.result()
        library_manifest = library_future.result()
    if not isinstance(catalog_manifest, dict) or not isinstance(library_manifest, dict):
        raise RuntimeError("catalog or library manifest payload is invalid")

    return {
        "appstore_manifest_url": appstore_manifest_url,
        "catalog_manifest_url": catalog_manifest_url,
        "library_manifest_url": library_manifest_url,
        "appstore_manifest": appstore_manifest,
        "catalog_manifest": catalog_manifest,
        "library_manifest": library_manifest,
    }


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
    if isinstance(apps_delta_relative, str) and apps_delta_relative:
        apps_delta = fetch_delta_payload(library_manifest_url, apps_delta_relative)
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
    library_manifest_url = str(manifest_bundle.get("library_manifest_url", ""))
    if not isinstance(library_manifest, dict):
        return {}

    # ── v2 spec: supportsPartialUpdate ──────────────────────────────
    if library_manifest.get("supportsPartialUpdate") is not True:
        # Legacy: compatibility.appLevelArtifacts
        compatibility = library_manifest.get("compatibility")
        if not isinstance(compatibility, dict) or compatibility.get("appLevelArtifacts") is not True:
            return {}

    apps_index_relative = library_manifest.get("appsIndex")
    if not isinstance(apps_index_relative, str) or not apps_index_relative:
        return {}

    payload = download_json(resolve_json_url(library_manifest_url, apps_index_relative))
    if not isinstance(payload, dict):
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
                    chk["bundle"] = chk.get("latest")
            app_map[key] = normalized

    return app_map


def _resolve_component_dataset_version(appstore_manifest: dict[str, object], component: str) -> object:
    """Extract per-component datasetVersion from v2 appstore manifest."""
    block = appstore_manifest.get(component)
    if isinstance(block, dict):
        return block.get("datasetVersion")
    return None


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
        library_delta_context = resolve_library_delta_context(manifest_bundle, previous_root_dsv, latest_dataset_version)
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

    library_manifest = manifest_bundle.get("library_manifest")
    library_manifest_url = str(manifest_bundle.get("library_manifest_url", ""))
    if not isinstance(library_manifest, dict) or not library_manifest_url:
        return None

    apps_index_relative = library_manifest.get("appsIndex")
    if not isinstance(apps_index_relative, str) or not apps_index_relative:
        return None

    try:
        payload = download_json(resolve_json_url(library_manifest_url, apps_index_relative))
    except Exception as exc:
        verbose_log(f"[platform-assets] apps index unavailable: {exc}")
        return None

    return payload if isinstance(payload, dict) else None


def publish_library_apps_index(library_root: Path, manifest_bundle: dict[str, object] | None, extra_targets: list[Path] | None = None) -> None:
    """Persist the apps index beside the library and inside the dataset snapshots.

    Keeping it next to the library lets the manifest builder pick it up, and the snapshot copies
    keep an offline activation able to rebuild the same manifests.
    """
    payload = fetch_library_apps_index_payload(manifest_bundle)
    if payload is None:
        return

    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for target in [library_root / "apps-index.json", *(extra_targets or [])]:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            verbose_log(f"[platform-assets] could not persist apps index at {target}: {exc}")


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
    if isinstance(full_pkg, str) and full_pkg:
        return full_pkg
    if isinstance(full_pkg, dict):
        latest = full_pkg.get("latest")
        if isinstance(latest, str) and latest:
            return latest
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
                if isinstance(checksum, dict):
                    checksum_relative = str(checksum.get("fullPackage") or "").strip()
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
    replace_tree_linked(source_root, staging_dir)
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
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)

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

    if not changed_apps and not removed_apps:
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

        snapshot_paths = stage_snapshot(staged_root, snapshot_root, dataset_version, "library")
        sync_library_delta_target(snapshot_paths["current"], target_dir, changed_apps, removed_apps, marker_path)

    if not marker_exists(marker_path, "library"):
        raise RuntimeError(f"library assets are still missing after delta sync: {marker_path}")

    log(f"[platform-assets] applied library app delta into {target_dir}")
    return {key: str(value) for key, value in snapshot_paths.items()}


def extract_app_bundle(bundle_path: Path, apps_root: Path, app_key: str) -> None:
    extract_dir = bundle_path.parent / f"extract-{app_key}"
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


def sync_library_app_artifacts_delta(
    reusable_source: Path,
    target_dir: Path,
    marker_path: Path,
    manifest_bundle: dict[str, object],
    snapshot_root: Path,
    dataset_version: str,
    delta_context: dict[str, object],
) -> dict[str, str]:
    changed_apps = sorted(set(delta_context.get("changedApps", [])) | set(delta_context.get("addedApps", [])) | set(delta_context.get("updatedApps", [])))
    removed_apps = sorted(set(delta_context.get("removedApps", [])))

    if not changed_apps and not removed_apps:
        return promote_existing_package_snapshot(reusable_source, target_dir, marker_path, snapshot_root, dataset_version, "library")

    apps_index = resolve_library_apps_index(manifest_bundle)
    if not apps_index:
        raise RuntimeError("library manifest does not expose app-level artifacts")

    library_manifest_url = str(manifest_bundle.get("library_manifest_url", ""))
    log(f"[platform-assets] applying library app artifacts delta; changed={changed_apps or []} removed={removed_apps or []}")

    with tempfile.TemporaryDirectory(prefix="websoft9-library-app-artifacts-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        staged_root = temp_dir / "staged-library"
        # Reuse the current library payload through hard links: only the changed apps are
        # rewritten, so the untouched 60+ MB does not need to be copied for a few KB of updates.
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
            hydrate_app_sidecar(
                library_manifest_url,
                app_key,
                app_root,
                app_metadata.get("variables"),
                checksum.get("variables"),
                "variables.json",
                temp_dir,
            )
            hydrate_app_sidecar(
                library_manifest_url,
                app_key,
                app_root,
                app_metadata.get("env"),
                checksum.get("env"),
                ".env",
                temp_dir,
            )

        # Each app owns its own bundle, extraction and sidecar paths, so the per-app artifact
        # downloads overlap instead of paying one round trip after another.
        if changed_apps:
            max_workers = min(_resolve_app_download_workers(), len(changed_apps))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(apply_changed_app, app_key) for app_key in changed_apps]
                for future in futures:
                    future.result()

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
    if package_sync_plan and not package_sync_plan.get(package_type, True):
        return False
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
    extract_dir.mkdir(parents=True, exist_ok=True)

    download_file(package_url, zip_path)

    if package_base_url and package_checksum_relative:
        # Verify the downloaded archive before it can reach a runtime tree.
        verify_downloaded_file_checksum(package_base_url, package_url, package_checksum_relative, zip_path)

    extract_zip_with_permissions(zip_path, extract_dir)

    source_root = extract_sync_root(extract_dir, package_type)

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
                    shutil.copytree(item, json_dir / item.name)
                elif not item.name.endswith(".json"):
                    shutil.copy2(item, json_dir / item.name)
            source_root = json_dir

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
    A failed prefetch is not fatal: the caller falls back to a serial download for that package.
    """
    pending = [
        package
        for package in packages
        if package_needs_sync(package[0], package[2], package_sync_plan, force_refresh)
    ]
    if len(pending) < 2:
        return {}, None

    prefetch_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-prefetch-"))
    prefetched: dict[str, Path] = {}
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

    return profiles


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
        app_manifest.update({"distribution": distribution, "settings": get_install_settings(env_values), "is_web_app": "W9_URL" in env_values})
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

    manifest: dict[str, object] = {"schemaVersion": "1", "locale": locale, "apps": apps}
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


def has_valid_published_app_store_manifests(media_root: Path) -> bool:
    media_json_root = media_root / "json"
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
    snapshot_root = Path(os.getenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", "/websoft9/appstore"))

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
    if sync_mode != "build":
        try:
            sync_lock = acquire_appstore_sync_lock(Path(data_root))
        except OSError as exc:
            log(f"[platform-assets] Appstore sync lock unavailable ({exc}); continuing without cross-process serialisation")
            sync_lock = _APPSTORE_SYNC_LOCK_UNAVAILABLE
        if sync_lock is None:
            log("[platform-assets] another Appstore sync is already running; skipping this round")
            return 0
        # Keep the handle alive for the process lifetime; closing it would release the lock.
        _ = sync_lock
        write_appstore_sync_pid_marker()

    rollback_backups: dict[Path, Path | None] = {}
    rollback_root: Path | None = None
    previous_state: dict[str, object] = {}
    try:
        previous_state = load_sync_state(sync_state_path)
        force_refresh = is_force_refresh_enabled()
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
        local_schema_version = get_published_app_store_schema_version(media_root)
        if local_schema_version is None:
            state_schema_version = previous_state.get("schemaVersion")
            if isinstance(state_schema_version, str) and state_schema_version.strip():
                local_schema_version = state_schema_version
        if local_schema_version is None and sync_mode != "build":
            raise AppStoreCompatibilityError(
                "active appstore schemaVersion is unavailable. Please upgrade your Websoft9 platform before updating Appstore."
            )
        try:
            manifest_bundle = fetch_appstore_manifests(artifact_base, channel, local_schema_version)
            appstore_manifest = manifest_bundle["appstore_manifest"]
            if isinstance(appstore_manifest, dict):
                latest_schema_version = appstore_manifest.get("schemaVersion")
                latest_dataset_version = appstore_manifest.get("datasetVersion")
                latest_generated_at = appstore_manifest.get("generatedAt")
                # Resolve per-component datasetVersions (v2) for state tracking
                latest_catalog_dsv = _resolve_component_dataset_version(appstore_manifest, "catalog")
                latest_library_dsv = _resolve_component_dataset_version(appstore_manifest, "library")
                if not force_refresh and previous_state.get("datasetVersion") == latest_dataset_version:
                    catalog_unchanged = (not latest_catalog_dsv
                                         or latest_catalog_dsv == previous_state.get("catalogDatasetVersion"))
                    library_unchanged = (not latest_library_dsv
                                         or latest_library_dsv == previous_state.get("libraryDatasetVersion"))
                    if catalog_unchanged and library_unchanged:
                        should_skip_package_sync = True
                        log(f"[platform-assets] appstore dataset {latest_dataset_version} already active for channel {channel}")
                if not should_skip_package_sync:
                    package_sync_plan = determine_package_sync_plan(
                        manifest_bundle,
                        previous_state,
                        latest_dataset_version,
                    )
                    library_delta_context = resolve_library_delta_context(
                        manifest_bundle,
                        previous_state.get("datasetVersion"),
                        latest_dataset_version,
                    )
        except AppStoreCompatibilityError:
            raise
        except Exception as exc:
            log(f"[platform-assets] appstore manifests unavailable, falling back to legacy package resolution: {exc}")

        applied_dataset_version = latest_dataset_version or previous_state.get("datasetVersion") or datetime.datetime.utcnow().strftime("%Y.%m.%d.%H%M%S")
        library_root = Path(os.getenv("WEBSOFT9_LIBRARY_ROOT", "/websoft9/library"))
        should_rebuild_manifests = not (
            should_skip_package_sync and has_valid_published_app_store_manifests(media_root)
        )

        if not should_skip_package_sync or should_rebuild_manifests:
            rollback_root = Path(tempfile.mkdtemp(prefix="websoft9-appstore-sync-rollback-"))
            rollback_targets = [
                target
                for package_type, target_dir, _ in packages
                for target in (target_dir, snapshot_root / "current" / package_type)
            ]
            rollback_backups = backup_trees(rollback_targets, rollback_root)

        if not should_skip_package_sync:
            prefetched_sources, prefetch_root = prefetch_pending_packages(
                packages,
                package_sync_plan,
                force_refresh,
                channel,
                artifact_base,
                manifest_bundle,
            )
            for package_type, target_dir, marker_path in packages:
                reusable_source = resolve_reusable_package_source(previous_state, package_type, target_dir, marker_path)
                if not force_refresh and not package_sync_plan.get(package_type, True):
                    if reusable_source is not None:
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
                    try:
                        package_snapshot_paths[package_type] = sync_library_app_artifacts_delta(
                            reusable_source,
                            target_dir,
                            marker_path,
                            manifest_bundle,
                            snapshot_root,
                            str(applied_dataset_version),
                            library_delta_context,
                        )
                    except Exception as exc:
                        log(f"[platform-assets] app-level library delta unavailable, falling back to library package delta: {exc}")
                        package_snapshot_paths[package_type] = sync_library_package_delta(
                            reusable_source,
                            target_dir,
                            marker_path,
                            channel,
                            artifact_base,
                            manifest_bundle,
                            snapshot_root,
                            str(applied_dataset_version),
                            library_delta_context,
                        )
                    continue
                snapshot_paths = sync_package(
                    package_type,
                    target_dir,
                    marker_path,
                    channel,
                    artifact_base,
                    manifest_bundle,
                    snapshot_root,
                    str(applied_dataset_version),
                    force_sync=package_sync_plan.get(package_type, True),
                    prefetched_source=prefetched_sources.get(package_type),
                )
                if snapshot_paths:
                    package_snapshot_paths[package_type] = snapshot_paths

            if prefetch_root is not None:
                shutil.rmtree(prefetch_root, ignore_errors=True)

        # Persist the library apps index next to the active library and inside this dataset's
        # snapshots, so the manifest build and a later offline activation both see the per-app
        # update times. Publishing is best effort: a missing index only drops the field.
        library_snapshot_paths = package_snapshot_paths.get("library")
        apps_index_targets: list[Path] = []
        if isinstance(library_snapshot_paths, dict):
            for snapshot_key in ("staging", "release", "current"):
                snapshot_value = library_snapshot_paths.get(snapshot_key)
                if isinstance(snapshot_value, str) and snapshot_value:
                    apps_index_targets.append(Path(snapshot_value) / "apps-index.json")
        publish_library_apps_index(library_root, manifest_bundle, apps_index_targets)

        if not should_rebuild_manifests:
            log(f"[platform-assets] skipping manifest rebuild for unchanged dataset {applied_dataset_version}")
        else:
            build_and_publish_app_store_manifests(media_root, library_root)

        state_payload: dict[str, object] = {
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
        }
        if latest_catalog_dsv is not None:
            state_payload["catalogDatasetVersion"] = latest_catalog_dsv
        if latest_library_dsv is not None:
            state_payload["libraryDatasetVersion"] = latest_library_dsv
        write_sync_state(sync_state_path, state_payload)
        log(f"[platform-assets] completed app store manifest build (mode={sync_mode})")

        removed_datasets = prune_stale_appstore_datasets(
            snapshot_root,
            str(applied_dataset_version) if applied_dataset_version else None,
        )
        if removed_datasets:
            log(f"[platform-assets] removed stale App Store datasets: {', '.join(sorted(removed_datasets))}")
    except AppStoreCompatibilityError as exc:
        if rollback_backups:
            try:
                restore_trees(rollback_backups)
                log("[platform-assets] restored active assets after incompatible appstore update")
            except Exception as rollback_exc:
                log(f"[platform-assets] failed to restore active assets after incompatible update: {rollback_exc}")
        incompatible_state = dict(previous_state)
        incompatible_state.update(
            {
                "syncStatus": "incompatible",
                "lastSyncAttemptAt": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "incompatibility": {"message": str(exc)},
            }
        )
        write_sync_state(sync_state_path, incompatible_state)
        log(f"[platform-assets] app store update requires a Websoft9 upgrade: {exc}")
        return 1
    except Exception as exc:
        if rollback_backups:
            try:
                restore_trees(rollback_backups)
                log("[platform-assets] restored active assets after failed sync")
            except Exception as rollback_exc:
                log(f"[platform-assets] failed to restore active assets after sync failure: {rollback_exc}")
        log(f"[platform-assets] asset sync failed (mode={sync_mode}): {exc}")
        return 1
    finally:
        if rollback_root is not None:
            shutil.rmtree(rollback_root, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())