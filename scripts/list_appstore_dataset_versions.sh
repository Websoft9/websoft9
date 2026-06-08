#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/list_appstore_dataset_versions.sh --catalog-dir <dir> --library-dir <dir>

List dataset versions that have matching historical manifests in both catalog and library directories.
EOF
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

CATALOG_DIR=""
LIBRARY_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --catalog-dir)
      CATALOG_DIR="$2"
      shift 2
      ;;
    --library-dir)
      LIBRARY_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$CATALOG_DIR" ]] || fail "--catalog-dir is required"
[[ -n "$LIBRARY_DIR" ]] || fail "--library-dir is required"
[[ -d "$CATALOG_DIR" ]] || fail "catalog directory not found: $CATALOG_DIR"
[[ -d "$LIBRARY_DIR" ]] || fail "library directory not found: $LIBRARY_DIR"

catalog_versions=$(find "$CATALOG_DIR" -maxdepth 1 -type f -name 'manifest-*.json' -printf '%f\n' | sed -E 's/^manifest-(.+)\.json$/\1/' | sort)
library_versions=$(find "$LIBRARY_DIR" -maxdepth 1 -type f -name 'manifest-*.json' -printf '%f\n' | sed -E 's/^manifest-(.+)\.json$/\1/' | sort)

[[ -n "$catalog_versions" ]] || fail "no historical catalog manifests found in $CATALOG_DIR"
[[ -n "$library_versions" ]] || fail "no historical library manifests found in $LIBRARY_DIR"

matches=$(comm -12 <(printf '%s\n' "$catalog_versions") <(printf '%s\n' "$library_versions"))
[[ -n "$matches" ]] || fail "no shared dataset versions found between catalog and library"

printf '%s\n' "$matches"