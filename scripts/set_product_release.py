#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
APPHUB_DIR = ROOT_DIR / "apphub"
if str(APPHUB_DIR) not in sys.path:
    sys.path.insert(0, str(APPHUB_DIR))

from src.core.product_catalog import PRODUCT_EDITION_ALIASES, PRODUCT_EDITIONS  # noqa: E402


PRODUCT_METADATA_PATH = ROOT_DIR / "apphub" / "src" / "config" / "product_metadata.json"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def normalize_edition_key(value: str) -> str:
    normalized = value.strip()
    canonical = PRODUCT_EDITION_ALIASES.get(normalized, normalized)
    if canonical not in PRODUCT_EDITIONS:
        supported = ", ".join(sorted(PRODUCT_EDITIONS))
        raise ValueError(f"Unsupported edition_key: {value}. Supported keys: {supported}")
    return canonical


def validate_version(value: str) -> str:
    normalized = value.strip()
    if not SEMVER_PATTERN.match(normalized):
        raise ValueError(f"Invalid version: {value}. Expected semantic version such as 2.2.17 or 2.2.18-rc1")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the active Websoft9 product release version and edition.")
    parser.add_argument("--edition-key", required=True, help="Edition key to activate, for example free, starter, standard, or enterprise")
    parser.add_argument("--version", required=True, help="Semantic version to publish, for example 2.2.17")
    args = parser.parse_args()

    edition_key = normalize_edition_key(args.edition_key)
    version = validate_version(args.version)

    payload = {
        "version": version,
        "edition_key": edition_key,
    }
    PRODUCT_METADATA_PATH.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())