#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

VERSION_METADATA_PATH = ROOT_DIR / "version.json"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SUPPORTED_CHANNELS = {"release", "rc", "dev"}


def validate_version(value: str) -> str:
    normalized = value.strip()
    if not SEMVER_PATTERN.match(normalized):
        raise ValueError(f"Invalid version: {value}. Expected semantic version such as 2.2.17 or 2.2.18-rc1")
    return normalized


def normalize_channel(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_CHANNELS:
        supported = ", ".join(sorted(SUPPORTED_CHANNELS))
        raise ValueError(f"Unsupported channel: {value}. Supported channels: {supported}")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the active Websoft9 product release version.")
    parser.add_argument("--version", required=True, help="Semantic version to publish, for example 2.2.17")
    parser.add_argument("--channel", default="release", help="Release channel to publish, for example release, rc, or dev")
    args = parser.parse_args()

    version = validate_version(args.version)
    channel = normalize_channel(args.channel)

    payload = {
        "version": version,
        "channel": channel,
    }
    VERSION_METADATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())