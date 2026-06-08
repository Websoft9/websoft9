#!/usr/bin/env python3

from __future__ import annotations

import argparse
import configparser
import json
import re
from pathlib import Path


ENV_REFERENCE_PATTERN = re.compile(r"\$\{?(\w+)\}?")


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
            app_metadata["settings"] = {
                key: value
                for key, value in env_values.items()
                if key.startswith("W9_") and key.endswith("_SET")
            }
            app_metadata["is_web_app"] = "W9_URL" in env_values

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