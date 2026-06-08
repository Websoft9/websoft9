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

SCHEMA_VERSION="$(jq -r '.schemaVersion // empty' "$MANIFEST_PATH")"
DATASET_VERSION="$(jq -r '.datasetVersion // empty' "$MANIFEST_PATH")"
CHANNEL="$(jq -r '.channel // empty' "$MANIFEST_PATH")"
LIBRARY_PACKAGE="$(jq -r '.libraryPackage // empty' "$MANIFEST_PATH")"
CHECKSUM_FILE="$(jq -r 'if (.checksum | type) == "object" then .checksum.libraryPackage // empty else empty end' "$MANIFEST_PATH")"
INSTALL_METADATA="$(jq -r '.installMetadata // empty' "$MANIFEST_PATH")"
INSTALL_METADATA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.installMetadata // empty else empty end' "$MANIFEST_PATH")"
APPS_INDEX="$(jq -r '.appsIndex // empty' "$MANIFEST_PATH")"
APPS_INDEX_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.appsIndex // empty else empty end' "$MANIFEST_PATH")"
LIBRARY_DELTA="$(jq -r '.deltaFiles.library // empty' "$MANIFEST_PATH")"
APPS_DELTA="$(jq -r '.deltaFiles.apps // empty' "$MANIFEST_PATH")"
LIBRARY_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.libraryDelta // empty else empty end' "$MANIFEST_PATH")"
APPS_DELTA_CHECKSUM="$(jq -r 'if (.checksum | type) == "object" then .checksum.appsDelta // empty else empty end' "$MANIFEST_PATH")"
GENERATED_AT="$(jq -r '.generatedAt // empty' "$MANIFEST_PATH")"
LEGACY_PLUGIN_PATHS="$(jq -r 'if (.compatibility | type) == "object" and (.compatibility | has("legacyPluginPaths")) then .compatibility.legacyPluginPaths | tostring else empty end' "$MANIFEST_PATH")"
APP_LEVEL_ARTIFACTS="$(jq -r 'if (.compatibility | type) == "object" and (.compatibility | has("appLevelArtifacts")) then .compatibility.appLevelArtifacts | tostring else empty end' "$MANIFEST_PATH")"
SCHEMA_VERSION_COMPAT="$(jq -r '.compatibility.schemaVersion // empty' "$MANIFEST_PATH")"

[[ "$SCHEMA_VERSION" == "1" ]] || fail "schemaVersion must be 1"
[[ -n "$DATASET_VERSION" ]] || fail "datasetVersion must not be empty"
[[ "$DATASET_VERSION" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}$ ]] || fail "datasetVersion format is invalid: $DATASET_VERSION"
[[ "$CHANNEL" =~ ^(dev|rc|release)$ ]] || fail "channel must be dev, rc, or release"
[[ -n "$LIBRARY_PACKAGE" ]] || fail "libraryPackage must not be empty"
[[ -n "$CHECKSUM_FILE" ]] || fail "checksum.libraryPackage must not be empty"
[[ -n "$INSTALL_METADATA" ]] || fail "installMetadata must not be empty"
[[ -n "$INSTALL_METADATA_CHECKSUM" ]] || fail "checksum.installMetadata must not be empty"
[[ -n "$GENERATED_AT" ]] || fail "generatedAt must not be empty"
[[ "$GENERATED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || fail "generatedAt format is invalid: $GENERATED_AT"
[[ "$LEGACY_PLUGIN_PATHS" =~ ^(true|false)$ ]] || fail "compatibility.legacyPluginPaths must be boolean"
[[ "$APP_LEVEL_ARTIFACTS" =~ ^(true|false)?$ ]] || fail "compatibility.appLevelArtifacts must be boolean when present"
[[ "$SCHEMA_VERSION_COMPAT" == "1" ]] || fail "compatibility.schemaVersion must be 1"

if [[ -n "$APPS_INDEX" || -n "$APPS_INDEX_CHECKSUM" ]]; then
  [[ -n "$APPS_INDEX" ]] || fail "appsIndex must not be empty when checksum.appsIndex is present"
  [[ -n "$APPS_INDEX_CHECKSUM" ]] || fail "checksum.appsIndex must not be empty when appsIndex is present"
fi

if [[ -n "$LIBRARY_DELTA" || -n "$APPS_DELTA" || -n "$LIBRARY_DELTA_CHECKSUM" || -n "$APPS_DELTA_CHECKSUM" ]]; then
  [[ -n "$LIBRARY_DELTA" ]] || fail "deltaFiles.library must not be empty when delta checksum is present"
  [[ -n "$APPS_DELTA" ]] || fail "deltaFiles.apps must not be empty when delta checksum is present"
  [[ -n "$LIBRARY_DELTA_CHECKSUM" ]] || fail "checksum.libraryDelta must not be empty when deltaFiles.library is present"
  [[ -n "$APPS_DELTA_CHECKSUM" ]] || fail "checksum.appsDelta must not be empty when deltaFiles.apps is present"
fi

PACKAGE_PATH="$OUTPUT_DIR/$LIBRARY_PACKAGE"
CHECKSUM_PATH="$OUTPUT_DIR/$CHECKSUM_FILE"

[[ -f "$PACKAGE_PATH" ]] || fail "library package not found: $LIBRARY_PACKAGE"
[[ -s "$PACKAGE_PATH" ]] || fail "library package is empty: $LIBRARY_PACKAGE"
[[ -f "$CHECKSUM_PATH" ]] || fail "checksum file not found: $CHECKSUM_FILE"

EXPECTED_CHECKSUM="$(tr -d '[:space:]' < "$CHECKSUM_PATH")"
[[ "$EXPECTED_CHECKSUM" =~ ^[0-9a-f]{64}$ ]] || fail "checksum file must contain a raw sha256 hex digest"

ACTUAL_CHECKSUM="$(sha256sum "$PACKAGE_PATH" | awk '{print $1}')"
[[ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]] || fail "checksum mismatch for $LIBRARY_PACKAGE"

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

if [[ -n "$APPS_INDEX" ]]; then
  validate_optional_payload "$APPS_INDEX" "$APPS_INDEX_CHECKSUM"
fi

validate_optional_payload "$INSTALL_METADATA" "$INSTALL_METADATA_CHECKSUM"

if [[ -n "$LIBRARY_DELTA" ]]; then
  validate_optional_payload "$LIBRARY_DELTA" "$LIBRARY_DELTA_CHECKSUM"
fi

if [[ -n "$APPS_DELTA" ]]; then
  validate_optional_payload "$APPS_DELTA" "$APPS_DELTA_CHECKSUM"
fi

echo "Validated app-store library metadata in $OUTPUT_DIR"