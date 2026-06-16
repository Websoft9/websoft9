#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APPHUB_CANDIDATES = (
    Path("/websoft9/apphub"),
    Path(__file__).resolve().parents[2] / "apphub",
)

for apphub_root in APPHUB_CANDIDATES:
    if apphub_root.exists():
        if str(apphub_root) not in sys.path:
            sys.path.insert(0, str(apphub_root))
        break

from src.services.product_runtime_state import migrate_product_runtime_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure runtime product edition state is consistent after install or upgrade.")
    parser.add_argument("--version", help="Target runtime product version to persist")
    parser.add_argument("--edition-key", default="free", help="Fallback edition key when no source metadata or legacy mapping is available")
    parser.add_argument("--source-metadata", help="Previous runtime state snapshot to replay during modern upgrade")
    parser.add_argument("--legacy-system-ini", help="Legacy system.ini to migrate during legacy upgrade")
    args = parser.parse_args()

    source_state = None
    if args.source_metadata:
        source_path = Path(args.source_metadata)
        if source_path.exists():
            source_state = json.loads(source_path.read_text(encoding="utf-8"))

    edition = migrate_product_runtime_state(
        version=args.version,
        source_state=source_state,
        legacy_system_ini_file=args.legacy_system_ini,
        fallback_edition_key=args.edition_key,
    )
    print(
        json.dumps(
            {
                "edition_key": edition.key,
                "edition_name": edition.name,
                "max_apps": edition.max_apps,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())