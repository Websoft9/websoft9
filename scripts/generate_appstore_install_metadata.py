#!/usr/bin/env python3

from __future__ import annotations

import argparse
import configparser
import json
import re
from pathlib import Path


ENV_REFERENCE_PATTERN = re.compile(r"\$\{?(\w+)\}?")
PROFILE_COMPOSE_PATTERN = re.compile(r"^docker-compose\.([a-z0-9][a-z0-9-]*)\.yml$")


def load_initial_apps(config_path: Path) -> list[str]:
    if not config_path.exists():
        return []

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    raw_value = parser.get("initial_apps", "keys", fallback="")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def load_env_values(env_path: Path) -> dict[str, str]:
    normalized_values: dict[str, str] = {}

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        normalized_value = value.strip()
        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1] and normalized_value[0] in {'"', "'"}:
            normalized_value = normalized_value[1:-1]

        normalized_values[key] = normalized_value

    resolved_values: dict[str, str] = {}

    def resolve_value(key: str, stack: set[str]) -> str:
        if key in resolved_values:
            return resolved_values[key]

        if key in stack:
            return ""

        stack.add(key)
        current_value = normalized_values.get(key, "")
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


def discover_install_profiles(app_dir: Path) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}

    for env_path in sorted(app_dir.glob(".env.*")):
        match = re.match(r"^\.env\.([a-z0-9][a-z0-9-]*)$", env_path.name)
        if not match:
            continue

        profile_name = match.group(1)
        env_values = load_env_values(env_path)
        profile_metadata: dict[str, object] = {
            "settings": get_install_settings(env_values),
        }
        if env_values.get("W9_DATABASE_MODE") == "external":
            profile_metadata["is_external_database"] = True
        profiles[profile_name] = profile_metadata

    return profiles


def build_install_metadata(library_root: Path, config_path: Path) -> dict[str, object]:
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
            env_values = load_env_values(env_path)
            app_metadata["settings"] = get_install_settings(env_values)
            app_metadata["is_web_app"] = "W9_URL" in env_values

        variables_path = app_dir / "variables.json"
        if variables_path.exists():
            try:
                variables_metadata = json.loads(variables_path.read_text(encoding="utf-8"))
                help_metadata = variables_metadata.get("help")
                if isinstance(help_metadata, dict):
                    app_metadata["help"] = help_metadata
                distribution = get_distribution(variables_metadata.get("edition"))
                if distribution:
                    app_metadata["distribution"] = distribution
            except (json.JSONDecodeError, OSError):
                pass

        profiles = discover_install_profiles(app_dir)
        if profiles:
            app_metadata["profiles"] = profiles

        apps_metadata[app_key] = app_metadata

    manifest["apps"] = apps_metadata
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate app store install metadata from a library apps root")
    parser.add_argument("--library-root", required=True, help="Path to the library apps root")
    parser.add_argument("--config-path", required=True, help="Path to config.ini used for initial_apps")
    parser.add_argument("--output", required=True, help="Path to the output JSON file")
    args = parser.parse_args()

    payload = build_install_metadata(Path(args.library_root), Path(args.config_path))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())