#!/usr/bin/env python3

from __future__ import annotations

import configparser
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover - bootstrap fallback
    dotenv_values = None


ENV_REFERENCE_PATTERN = re.compile(r"\$\{?(\w+)\}?")

SUPPORTED_SCHEMA_VERSIONS = {"1"}

# ── v2 manifest URL templates ──────────────────────────────────────────
_V2_APPSTORE_MANIFEST_PATH = "appstore/{channel}/manifests/appstore-manifest.json"


def log(message: str) -> None:
    print(message, flush=True)


def detect_channel() -> str:
    explicit_channel = (os.getenv("WEBSOFT9_RUNTIME_ASSET_CHANNEL") or "").strip().lower()
    if explicit_channel in {"release", "rc", "dev"}:
        return explicit_channel

    version_file = Path("/websoft9/version.json")
    if not version_file.exists():
        return "release"

    try:
        payload = json.loads(version_file.read_text(encoding="utf-8"))
    except Exception:
        return "release"

    channel = str(payload.get("channel") or "").strip().lower()
    if channel in {"release", "rc", "dev"}:
        return channel

    version = payload.get("version", "")

    normalized_version = version.lower()
    if "rc" in normalized_version:
        return "rc"
    if "dev" in normalized_version:
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


def replace_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    sync_tree(source, target)


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


def _resolve_appstore_manifest_url(artifact_base: str, channel: str) -> str:
    """Resolve the current appstore v2 manifest URL for the requested channel."""
    v2_url = f"{artifact_base}/{_V2_APPSTORE_MANIFEST_PATH.format(channel=channel)}"
    download_json(v2_url)
    return v2_url


def _check_schema_version(manifest: dict[str, object], manifest_url: str, label: str = "appstore") -> None:
    schema_version = manifest.get("schemaVersion")
    if schema_version is not None and schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise RuntimeError(
            f"unsupported {label} schemaVersion: {schema_version}. "
            f"Supported versions: {', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))}. "
            f"Please upgrade your Websoft9 platform."
        )


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


def fetch_appstore_manifests(artifact_base: str, channel: str) -> dict[str, object]:
    appstore_manifest_url = _resolve_appstore_manifest_url(artifact_base, channel)
    appstore_manifest = download_json(appstore_manifest_url)
    if not isinstance(appstore_manifest, dict):
        raise RuntimeError(f"invalid appstore manifest payload: {appstore_manifest_url}")

    _check_schema_version(appstore_manifest, appstore_manifest_url, "appstore")

    catalog_relative, library_relative = _resolve_manifest_domains(appstore_manifest, appstore_manifest_url)

    # Sub-manifest paths (e.g. "catalog/manifest.json") are relative to the
    # appstore channel root, NOT to the root manifest URL (which lives under
    # manifests/).  Construct the absolute URLs from the channel base.
    appstore_base = f"{artifact_base}/appstore/{channel}"
    catalog_manifest_url = f"{appstore_base}/{catalog_relative}"
    library_manifest_url = f"{appstore_base}/{library_relative}"
    catalog_manifest = download_json(catalog_manifest_url)
    library_manifest = download_json(library_manifest_url)
    if not isinstance(catalog_manifest, dict) or not isinstance(library_manifest, dict):
        raise RuntimeError("catalog or library manifest payload is invalid")

    _check_schema_version(catalog_manifest, catalog_manifest_url, "catalog")
    _check_schema_version(library_manifest, library_manifest_url, "library")

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


def resolve_package_url(package_type: str, channel: str, artifact_base: str, manifest_bundle: dict[str, object] | None) -> str:
    if manifest_bundle:
        if package_type == "media":
            catalog_manifest_url = str(manifest_bundle["catalog_manifest_url"])
            catalog_manifest = manifest_bundle["catalog_manifest"]
            if isinstance(catalog_manifest, dict):
                # v2 spec: fullPackage points to the catalog zip
                full_pkg = catalog_manifest.get("fullPackage")
                if isinstance(full_pkg, str) and full_pkg:
                    return resolve_json_url(catalog_manifest_url, full_pkg)
                # Legacy field names
                package_name = catalog_manifest.get("legacyMediaArchive") or catalog_manifest.get("catalogArchive")
                if isinstance(package_name, str) and package_name:
                    return resolve_json_url(catalog_manifest_url, package_name)

        if package_type == "library":
            library_manifest_url = str(manifest_bundle["library_manifest_url"])
            library_manifest = manifest_bundle["library_manifest"]
            if isinstance(library_manifest, dict):
                # v2 spec: fullPackage as string (e.g. "full/latest.zip")
                full_pkg = library_manifest.get("fullPackage")
                if isinstance(full_pkg, str) and full_pkg:
                    return resolve_json_url(library_manifest_url, full_pkg)
                # v2 spec (alt): fullPackage.latest for the channel-tagged full zip
                if isinstance(full_pkg, dict):
                    latest = full_pkg.get("latest")
                    if isinstance(latest, str) and latest:
                        return resolve_json_url(library_manifest_url, latest)
                # Legacy field name
                package_name = library_manifest.get("libraryPackage")
                if isinstance(package_name, str) and package_name:
                    return resolve_json_url(library_manifest_url, package_name)

    # Ultimate fallback: legacy flat URL structure
    package_name = resolve_package_name(channel, package_type)
    return f"{artifact_base}/{channel}/websoft9/plugin/{package_type}/{package_name}"


def stage_snapshot(source_root: Path, snapshot_root: Path, dataset_version: str, package_type: str) -> dict[str, Path]:
    staging_dir = snapshot_root / "staging" / dataset_version / package_type
    release_dir = snapshot_root / "releases" / dataset_version / package_type
    current_dir = snapshot_root / "current" / package_type

    replace_tree(source_root, staging_dir)
    replace_tree(staging_dir, release_dir)
    replace_tree(staging_dir, current_dir)

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

    package_url = resolve_package_url("library", channel, artifact_base, manifest_bundle)
    package_name = Path(urllib.request.urlparse(package_url).path).name or resolve_package_name(channel, "library")
    log(f"[platform-assets] applying library app delta from {package_url}; changed={changed_apps or []} removed={removed_apps or []}")

    with tempfile.TemporaryDirectory(prefix="websoft9-library-delta-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        zip_path = temp_dir / package_name
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        download_file(package_url, zip_path)

        extract_zip_with_permissions(zip_path, extract_dir)

        source_root = extract_sync_root(extract_dir, "library")
        staged_root = temp_dir / "staged-library"
        replace_tree(reusable_source, staged_root)

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
    shutil.copy2(local_path, app_root / local_name)


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
        replace_tree(reusable_source, staged_root)
        staged_apps_dir = staged_root / "apps"
        staged_apps_dir.mkdir(parents=True, exist_ok=True)

        for app_key in removed_apps:
            app_path = staged_apps_dir / app_key
            if app_path.is_dir():
                shutil.rmtree(app_path)
            elif app_path.exists():
                app_path.unlink()

        for app_key in changed_apps:
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

        snapshot_paths = stage_snapshot(staged_root, snapshot_root, dataset_version, "library")
        sync_library_delta_target(snapshot_paths["current"], target_dir, changed_apps, removed_apps, marker_path)

    if not marker_exists(marker_path, "library"):
        raise RuntimeError(f"library assets are still missing after app-artifact delta sync: {marker_path}")

    log(f"[platform-assets] applied library app artifacts delta into {target_dir}")
    return {key: str(value) for key, value in snapshot_paths.items()}


def sync_package(
    package_type: str,
    target_dir: Path,
    marker_path: Path,
    channel: str,
    artifact_base: str,
    manifest_bundle: dict[str, object] | None = None,
    snapshot_root: Path | None = None,
    dataset_version: str | None = None,
) -> dict[str, str] | None:
    force_refresh = (os.getenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC") or "0").strip().lower() in {"1", "true", "yes", "on"}

    if marker_exists(marker_path, package_type) and not force_refresh:
        log(f"[platform-assets] {package_type} already present at {marker_path}")
        return None

    package_url = resolve_package_url(package_type, channel, artifact_base, manifest_bundle)
    package_name = Path(urllib.request.urlparse(package_url).path).name or resolve_package_name(channel, package_type)
    action = "refreshing" if force_refresh else "syncing missing"
    log(f"[platform-assets] {action} {package_type} assets from {package_url}")

    with tempfile.TemporaryDirectory(prefix=f"websoft9-{package_type}-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        zip_path = temp_dir / package_name
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        download_file(package_url, zip_path)

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

        snapshot_paths = None
        if snapshot_root is not None and dataset_version:
            snapshot_paths = stage_snapshot(source_root, snapshot_root, dataset_version, package_type)
            source_root = snapshot_paths["current"]
        sync_tree(source_root, target_dir)

    if not marker_exists(marker_path, package_type):
        raise RuntimeError(f"{package_type} assets are still missing after sync: {marker_path}")

    log(f"[platform-assets] synced {package_type} assets into {target_dir}")
    if snapshot_paths:
        return {key: str(value) for key, value in snapshot_paths.items()}
    return None


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


def build_app_store_install_metadata(library_root: Path, config_path: Path) -> dict[str, object]:
    manifest: dict[str, object] = {
        "initial_apps": load_initial_apps(config_path),
        "apps": {},
    }
    apps_metadata: dict[str, dict[str, object]] = {}

    if not library_root.exists():
        manifest["apps"] = apps_metadata
        return manifest

    for app_dir in sorted(library_root.iterdir()):
        if not app_dir.is_dir():
            continue

        app_key = app_dir.name
        env_path = app_dir / ".env"
        app_metadata: dict[str, object] = {
            "settings": {},
            "is_web_app": False,
        }

        if env_path.exists():
            try:
                env_values = load_env_values(env_path)
                app_metadata["settings"] = {
                    key: value
                    for key, value in env_values.items()
                    if key.startswith("W9_") and key.endswith("_SET")
                }
                app_metadata["is_web_app"] = "W9_URL" in env_values
            except Exception as exc:
                log(f"[platform-assets] failed to read {env_path}: {exc}")

        apps_metadata[app_key] = app_metadata

    manifest["apps"] = apps_metadata
    return manifest


def write_json_file(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


def is_force_refresh_enabled() -> bool:
    return (os.getenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC") or "0").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    channel = detect_channel()
    artifact_base = os.getenv("WEBSOFT9_ARTIFACT_BASE", "https://artifact.websoft9.com")
    sync_mode = (os.getenv("WEBSOFT9_RUNTIME_ASSET_SYNC_MODE") or "runtime").strip().lower()
    config_path = Path(
        os.getenv("WEBSOFT9_APPHUB_CONFIG_PATH")
        or os.getenv("WEBSOFT9_APPHUB_CONFIG", "/websoft9/apphub/src/config/config.ini")
    )
    library_apps_root = Path(os.getenv("WEBSOFT9_LIBRARY_APPS_ROOT", "/websoft9/library/apps"))
    install_metadata_path = Path(os.getenv("WEBSOFT9_APP_STORE_INSTALL_METADATA", "/websoft9/media/json/app-store-install-metadata.json"))
    sync_state_path = Path(os.getenv("WEBSOFT9_APP_STORE_SYNC_STATE", "/websoft9/apphub/src/config/appstore_sync_state.json"))
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

    if requested_package_types:
        packages = [package for package in packages if package[0] in requested_package_types]

    try:
        previous_state = load_sync_state(sync_state_path)
        force_refresh = is_force_refresh_enabled()
        manifest_bundle = None
        latest_dataset_version = None
        latest_generated_at = None
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

        try:
            manifest_bundle = fetch_appstore_manifests(artifact_base, channel)
            appstore_manifest = manifest_bundle["appstore_manifest"]
            if isinstance(appstore_manifest, dict):
                latest_dataset_version = appstore_manifest.get("datasetVersion")
                latest_generated_at = appstore_manifest.get("generatedAt")
                # Resolve per-component datasetVersions (v2) for state tracking
                latest_catalog_dsv = _resolve_component_dataset_version(appstore_manifest, "catalog")
                latest_library_dsv = _resolve_component_dataset_version(appstore_manifest, "library")
                if not force_refresh and previous_state.get("datasetVersion") == latest_dataset_version:
                    should_skip_package_sync = True
                    log(f"[platform-assets] appstore dataset {latest_dataset_version} already active for channel {channel}")
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
        except Exception as exc:
            log(f"[platform-assets] appstore manifests unavailable, falling back to legacy package resolution: {exc}")

        applied_dataset_version = latest_dataset_version or previous_state.get("datasetVersion") or datetime.datetime.utcnow().strftime("%Y.%m.%d.%H%M%S")

        if not should_skip_package_sync:
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
                )
                if snapshot_paths:
                    package_snapshot_paths[package_type] = snapshot_paths

        # ── install metadata ──────────────────────────────────────────
        # Only consume remote install metadata when the active manifest declares it.
        install_metadata = None
        if manifest_bundle:
            library_manifest_url = str(manifest_bundle["library_manifest_url"])
            library_manifest = manifest_bundle["library_manifest"]
            if isinstance(library_manifest, dict):
                install_metadata_relative = library_manifest.get("installMetadata")
                if isinstance(install_metadata_relative, str) and install_metadata_relative:
                    install_metadata_url = resolve_json_url(library_manifest_url, install_metadata_relative)
                    try:
                        install_metadata = download_json(install_metadata_url)
                        log(f"[platform-assets] downloaded app store install metadata from {install_metadata_url}")
                    except Exception as exc:
                        log(f"[platform-assets] declared install metadata unavailable, falling back to local generation: {exc}")

        if install_metadata is None:
            install_metadata = build_app_store_install_metadata(library_apps_root, config_path)

        write_json_file(install_metadata_path, install_metadata)

        state_payload: dict[str, object] = {
            "channel": channel,
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
        log(f"[platform-assets] wrote app store install metadata to {install_metadata_path} (mode={sync_mode})")
    except Exception as exc:
        log(f"[platform-assets] asset sync failed (mode={sync_mode}): {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())