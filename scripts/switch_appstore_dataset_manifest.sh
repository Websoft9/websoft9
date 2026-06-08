#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/switch_appstore_dataset_manifest.sh --catalog-dir <dir> --library-dir <dir> --dataset-version <version>

Switch catalog/library latest manifest.json files to the specified historical dataset manifest.
EOF
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

CATALOG_DIR=""
LIBRARY_DIR=""
DATASET_VERSION=""

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
    --dataset-version)
      DATASET_VERSION="$2"
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
[[ -n "$DATASET_VERSION" ]] || fail "--dataset-version is required"

[[ -d "$CATALOG_DIR" ]] || fail "catalog directory not found: $CATALOG_DIR"
[[ -d "$LIBRARY_DIR" ]] || fail "library directory not found: $LIBRARY_DIR"

CATALOG_HISTORY="$CATALOG_DIR/manifest-${DATASET_VERSION}.json"
LIBRARY_HISTORY="$LIBRARY_DIR/manifest-${DATASET_VERSION}.json"
CATALOG_LATEST="$CATALOG_DIR/manifest.json"
LIBRARY_LATEST="$LIBRARY_DIR/manifest.json"

[[ -f "$CATALOG_HISTORY" ]] || fail "catalog historical manifest not found: $CATALOG_HISTORY"
[[ -f "$LIBRARY_HISTORY" ]] || fail "library historical manifest not found: $LIBRARY_HISTORY"

bash scripts/validate_appstore_dataset_manifests.sh "$CATALOG_HISTORY" "$LIBRARY_HISTORY"

tmp_catalog="${CATALOG_LATEST}.tmp"
tmp_library="${LIBRARY_LATEST}.tmp"

cp "$CATALOG_HISTORY" "$tmp_catalog"
cp "$LIBRARY_HISTORY" "$tmp_library"

mv "$tmp_catalog" "$CATALOG_LATEST"
mv "$tmp_library" "$LIBRARY_LATEST"

echo "Switched app-store dataset manifests to ${DATASET_VERSION}"