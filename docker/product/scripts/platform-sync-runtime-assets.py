#!/usr/bin/env python3

from __future__ import annotations

import configparser
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


def log(message: str) -> None:
    print(message, flush=True)


def detect_channel() -> str:
    version_file = Path("/websoft9/apphub/src/config/product_metadata.json")
    if not version_file.exists():
        return "release"

    try:
        version = json.loads(version_file.read_text(encoding="utf-8")).get("version", "")
    except Exception:
        return "release"

    return "dev" if "rc" in version else "release"


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


def extract_sync_root(extract_dir: Path, package_type: str) -> Path:
    direct_child = extract_dir / package_type
    if direct_child.exists():
        return direct_child

    children = list(extract_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]

    return extract_dir


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Websoft9-Product-Bootstrap/1.0",
            "Accept": "application/zip,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def sync_package(package_type: str, target_dir: Path, marker_path: Path, channel: str, artifact_base: str) -> None:
    if marker_exists(marker_path, package_type):
        log(f"[platform-assets] {package_type} already present at {marker_path}")
        return

    package_name = resolve_package_name(channel, package_type)
    package_url = f"{artifact_base}/{channel}/websoft9/plugin/{package_type}/{package_name}"
    log(f"[platform-assets] syncing missing {package_type} assets from {package_url}")

    with tempfile.TemporaryDirectory(prefix=f"websoft9-{package_type}-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        zip_path = temp_dir / package_name
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        download_file(package_url, zip_path)

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        source_root = extract_sync_root(extract_dir, package_type)
        sync_tree(source_root, target_dir)

    if not marker_exists(marker_path, package_type):
        raise RuntimeError(f"{package_type} assets are still missing after sync: {marker_path}")

    log(f"[platform-assets] synced {package_type} assets into {target_dir}")


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


def main() -> int:
    channel = detect_channel()
    artifact_base = os.getenv("WEBSOFT9_ARTIFACT_BASE", "https://artifact.websoft9.com")
    config_path = Path(os.getenv("WEBSOFT9_APPHUB_CONFIG", "/websoft9/apphub/src/config/config.ini"))
    library_apps_root = Path(os.getenv("WEBSOFT9_LIBRARY_APPS_ROOT", "/websoft9/library/apps"))
    install_metadata_path = Path(os.getenv("WEBSOFT9_APP_STORE_INSTALL_METADATA", "/websoft9/media/json/app-store-install-metadata.json"))

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

    try:
        for package_type, target_dir, marker_path in packages:
            sync_package(package_type, target_dir, marker_path, channel, artifact_base)

        install_metadata = build_app_store_install_metadata(library_apps_root, config_path)
        write_json_file(install_metadata_path, install_metadata)
        log(f"[platform-assets] wrote app store install metadata to {install_metadata_path}")
    except Exception as exc:
        log(f"[platform-assets] asset bootstrap failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())