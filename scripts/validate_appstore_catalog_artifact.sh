#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${1:-output}"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

[[ -d "$OUTPUT_DIR" ]] || fail "output directory not found: $OUTPUT_DIR"

MANIFEST_PATH="$OUTPUT_DIR/manifest.json"
[[ -f "$MANIFEST_PATH" ]] || fail "manifest.json is missing"

command -v jq >/dev/null 2>&1 || fail "jq is required"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"

DATASET_VERSION="$(jq -r '.datasetVersion // empty' "$MANIFEST_PATH")"
CHANNEL="$(jq -r '.channel // empty' "$MANIFEST_PATH")"
CATALOG_ARCHIVE="$(jq -r '.catalogArchive // empty' "$MANIFEST_PATH")"
SCHEMA_VERSION="$(jq -r '.schemaVersion // empty' "$MANIFEST_PATH")"
CHECKSUM_FILE="$(jq -r 'if (.checksum | type) == "object" then .checksum.catalogArchive // empty else .checksum // empty end' "$MANIFEST_PATH")"
LIBRARY_PACKAGE="$(jq -r '.libraryPackage // empty' "$MANIFEST_PATH")"
LIBRARY_CHECKSUM_FILE="$(jq -r 'if (.checksum | type) == "object" then .checksum.libraryPackage // empty else empty end' "$MANIFEST_PATH")"
APPS_INDEX="$(jq -r '.appsIndex // empty' "$MANIFEST_PATH")"
APPS_INDEX_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.appsIndex // empty else empty end' "$MANIFEST_PATH")"
LIBRARY_DELTA_FILE="$(jq -r '.libraryDeltaFiles.library // empty' "$MANIFEST_PATH")"
APPS_DELTA_FILE="$(jq -r '.libraryDeltaFiles.apps // empty' "$MANIFEST_PATH")"
LIBRARY_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.libraryDelta // empty else empty end' "$MANIFEST_PATH")"
APPS_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.appsDelta // empty else empty end' "$MANIFEST_PATH")"
LEGACY_MEDIA_ARCHIVE="$(jq -r '.legacyMediaArchive // empty' "$MANIFEST_PATH")"
LEGACY_MEDIA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.legacyMediaArchive // empty else empty end' "$MANIFEST_PATH")"
CATALOG_DELTA_FILE="$(jq -r '.deltaFiles.catalog // empty' "$MANIFEST_PATH")"
PRODUCT_DELTA_FILE="$(jq -r '.deltaFiles.product // empty' "$MANIFEST_PATH")"
CATALOG_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.catalogDelta // empty else empty end' "$MANIFEST_PATH")"
PRODUCT_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.productDelta // empty else empty end' "$MANIFEST_PATH")"
GENERATED_AT="$(jq -r '.generatedAt // empty' "$MANIFEST_PATH")"
LEGACY_PLUGIN_PATHS="$(jq -r 'if (.compatibility | type) == "object" and (.compatibility | has("legacyPluginPaths")) then .compatibility.legacyPluginPaths | tostring else empty end' "$MANIFEST_PATH")"
LEGACY_MEDIA_PACKAGE="$(jq -r 'if (.compatibility | type) == "object" and (.compatibility | has("legacyMediaPackage")) then .compatibility.legacyMediaPackage | tostring else empty end' "$MANIFEST_PATH")"
EMBEDDED_MEDIA_REQUIRED="$(jq -r 'if (.compatibility | type) == "object" and (.compatibility | has("embeddedMediaRequired")) then .compatibility.embeddedMediaRequired | tostring else empty end' "$MANIFEST_PATH")"
COMPATIBILITY_SCHEMA_VERSION="$(jq -r '.compatibility.schemaVersion // empty' "$MANIFEST_PATH")"

[[ -n "$DATASET_VERSION" ]] || fail "datasetVersion must not be empty"
[[ "$DATASET_VERSION" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}$ ]] || fail "datasetVersion format is invalid: $DATASET_VERSION"
[[ "$CHANNEL" =~ ^(dev|rc|release)$ ]] || fail "channel must be dev, rc, or release"
[[ "$SCHEMA_VERSION" == "1" ]] || fail "schemaVersion must be 1"
[[ -n "$CATALOG_ARCHIVE" ]] || fail "catalogArchive must not be empty"
[[ -n "$CHECKSUM_FILE" ]] || fail "checksum must not be empty"
[[ -n "$GENERATED_AT" ]] || fail "generatedAt must not be empty"
[[ "$GENERATED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || fail "generatedAt format is invalid: $GENERATED_AT"
[[ "$LEGACY_PLUGIN_PATHS" =~ ^(true|false)$ ]] || fail "legacyPluginPaths must be boolean"
[[ "$LEGACY_MEDIA_PACKAGE" =~ ^(true|false)$ ]] || fail "legacyMediaPackage must be boolean"
[[ "$EMBEDDED_MEDIA_REQUIRED" =~ ^(true|false)$ ]] || fail "embeddedMediaRequired must be boolean"
[[ "$COMPATIBILITY_SCHEMA_VERSION" == "1" ]] || fail "compatibility.schemaVersion must be 1"

if [[ -n "$LIBRARY_PACKAGE" || -n "$LIBRARY_CHECKSUM_FILE" ]]; then
  [[ -n "$LIBRARY_PACKAGE" ]] || fail "libraryPackage must not be empty when checksum.libraryPackage is present"
  [[ -n "$LIBRARY_CHECKSUM_FILE" ]] || fail "checksum.libraryPackage must not be empty when libraryPackage is present"
fi

if [[ -n "$APPS_INDEX" || -n "$APPS_INDEX_CHECKSUM" ]]; then
  [[ -n "$APPS_INDEX" ]] || fail "appsIndex must not be empty when checksum.appsIndex is present"
  [[ -n "$APPS_INDEX_CHECKSUM" ]] || fail "checksum.appsIndex must not be empty when appsIndex is present"
fi

if [[ -n "$LIBRARY_DELTA_FILE" || -n "$APPS_DELTA_FILE" || -n "$LIBRARY_DELTA_CHECKSUM" || -n "$APPS_DELTA_CHECKSUM" ]]; then
  [[ -n "$LIBRARY_DELTA_FILE" ]] || fail "libraryDeltaFiles.library must not be empty when checksum.libraryDelta is present"
  [[ -n "$APPS_DELTA_FILE" ]] || fail "libraryDeltaFiles.apps must not be empty when checksum.appsDelta is present"
  [[ -n "$LIBRARY_DELTA_CHECKSUM" ]] || fail "checksum.libraryDelta must not be empty when libraryDeltaFiles.library is present"
  [[ -n "$APPS_DELTA_CHECKSUM" ]] || fail "checksum.appsDelta must not be empty when libraryDeltaFiles.apps is present"
fi

if [[ -n "$LEGACY_MEDIA_ARCHIVE" || -n "$LEGACY_MEDIA_CHECKSUM" ]]; then
  [[ -n "$LEGACY_MEDIA_ARCHIVE" ]] || fail "legacyMediaArchive must not be empty when checksum.legacyMediaArchive is present"
  [[ -n "$LEGACY_MEDIA_CHECKSUM" ]] || fail "checksum.legacyMediaArchive must not be empty when legacyMediaArchive is present"
fi

if [[ -n "$CATALOG_DELTA_FILE" || -n "$PRODUCT_DELTA_FILE" || -n "$CATALOG_DELTA_CHECKSUM" || -n "$PRODUCT_DELTA_CHECKSUM" ]]; then
  [[ -n "$CATALOG_DELTA_FILE" ]] || fail "deltaFiles.catalog must not be empty when checksum.catalogDelta is present"
  [[ -n "$PRODUCT_DELTA_FILE" ]] || fail "deltaFiles.product must not be empty when checksum.productDelta is present"
  [[ -n "$CATALOG_DELTA_CHECKSUM" ]] || fail "checksum.catalogDelta must not be empty when deltaFiles.catalog is present"
  [[ -n "$PRODUCT_DELTA_CHECKSUM" ]] || fail "checksum.productDelta must not be empty when deltaFiles.product is present"
fi

ARCHIVE_PATH="$OUTPUT_DIR/$CATALOG_ARCHIVE"
CHECKSUM_PATH="$OUTPUT_DIR/$CHECKSUM_FILE"

[[ -f "$ARCHIVE_PATH" ]] || fail "catalog archive not found: $CATALOG_ARCHIVE"
[[ -s "$ARCHIVE_PATH" ]] || fail "catalog archive is empty: $CATALOG_ARCHIVE"
[[ -f "$CHECKSUM_PATH" ]] || fail "checksum file not found: $CHECKSUM_FILE"

EXPECTED_CHECKSUM="$(tr -d '[:space:]' < "$CHECKSUM_PATH")"
[[ "$EXPECTED_CHECKSUM" =~ ^[0-9a-f]{64}$ ]] || fail "checksum file must contain a raw sha256 hex digest"

ACTUAL_CHECKSUM="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
[[ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]] || fail "checksum mismatch for $CATALOG_ARCHIVE"

validate_optional_payload() {
  local payload_file="$1"
  local checksum_file="$2"
  [[ -f "$OUTPUT_DIR/$payload_file" ]] || fail "optional payload not found: $payload_file"
  [[ -f "$OUTPUT_DIR/$checksum_file" ]] || fail "optional checksum not found: $checksum_file"
  local expected actual
  expected="$(tr -d '[:space:]' < "$OUTPUT_DIR/$checksum_file")"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail "optional checksum file must contain a raw sha256 hex digest: $checksum_file"
  actual="$(sha256sum "$OUTPUT_DIR/$payload_file" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || fail "checksum mismatch for $payload_file"
}

if [[ -n "$LIBRARY_PACKAGE" ]]; then
  validate_optional_payload "$LIBRARY_PACKAGE" "$LIBRARY_CHECKSUM_FILE"
fi

if [[ -n "$APPS_INDEX" ]]; then
  validate_optional_payload "$APPS_INDEX" "$APPS_INDEX_CHECKSUM"
fi

if [[ -n "$LIBRARY_DELTA_FILE" ]]; then
  validate_optional_payload "$LIBRARY_DELTA_FILE" "$LIBRARY_DELTA_CHECKSUM"
fi

if [[ -n "$APPS_DELTA_FILE" ]]; then
  validate_optional_payload "$APPS_DELTA_FILE" "$APPS_DELTA_CHECKSUM"
fi

if [[ -n "$LEGACY_MEDIA_ARCHIVE" ]]; then
  validate_optional_payload "$LEGACY_MEDIA_ARCHIVE" "$LEGACY_MEDIA_CHECKSUM"
fi

if [[ -n "$CATALOG_DELTA_FILE" ]]; then
  validate_optional_payload "$CATALOG_DELTA_FILE" "$CATALOG_DELTA_CHECKSUM"
fi

if [[ -n "$PRODUCT_DELTA_FILE" ]]; then
  validate_optional_payload "$PRODUCT_DELTA_FILE" "$PRODUCT_DELTA_CHECKSUM"
fi

echo "Validated app-store catalog artifact in $OUTPUT_DIR"