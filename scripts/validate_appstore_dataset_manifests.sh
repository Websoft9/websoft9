#!/usr/bin/env bash

set -euo pipefail

CATALOG_MANIFEST_PATH="${1:-}"
LIBRARY_MANIFEST_PATH="${2:-}"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

[[ -n "$CATALOG_MANIFEST_PATH" ]] || fail "catalog manifest path is required"
[[ -n "$LIBRARY_MANIFEST_PATH" ]] || fail "library manifest path is required"
[[ -f "$CATALOG_MANIFEST_PATH" ]] || fail "catalog manifest not found: $CATALOG_MANIFEST_PATH"
[[ -f "$LIBRARY_MANIFEST_PATH" ]] || fail "library manifest not found: $LIBRARY_MANIFEST_PATH"

command -v jq >/dev/null 2>&1 || fail "jq is required"

catalog_basename() {
  basename "$1"
}

catalog_dataset_version="$(jq -r '.datasetVersion // empty' "$CATALOG_MANIFEST_PATH")"
catalog_channel="$(jq -r '.channel // empty' "$CATALOG_MANIFEST_PATH")"
catalog_generated_at="$(jq -r '.generatedAt // empty' "$CATALOG_MANIFEST_PATH")"
catalog_library_package="$(jq -r '.libraryPackage // empty' "$CATALOG_MANIFEST_PATH")"
catalog_library_checksum="$(jq -r '.checksum.libraryPackage // empty' "$CATALOG_MANIFEST_PATH")"
catalog_install_metadata="$(jq -r '.installMetadata // empty' "$CATALOG_MANIFEST_PATH")"
catalog_install_metadata_checksum="$(jq -r '.checksum.installMetadata // empty' "$CATALOG_MANIFEST_PATH")"
catalog_apps_index="$(jq -r '.appsIndex // empty' "$CATALOG_MANIFEST_PATH")"
catalog_apps_index_checksum="$(jq -r '.checksum.appsIndex // empty' "$CATALOG_MANIFEST_PATH")"
catalog_library_delta="$(jq -r '.libraryDeltaFiles.library // empty' "$CATALOG_MANIFEST_PATH")"
catalog_apps_delta="$(jq -r '.libraryDeltaFiles.apps // empty' "$CATALOG_MANIFEST_PATH")"
catalog_library_delta_checksum="$(jq -r '.checksum.libraryDelta // empty' "$CATALOG_MANIFEST_PATH")"
catalog_apps_delta_checksum="$(jq -r '.checksum.appsDelta // empty' "$CATALOG_MANIFEST_PATH")"

library_dataset_version="$(jq -r '.datasetVersion // empty' "$LIBRARY_MANIFEST_PATH")"
library_channel="$(jq -r '.channel // empty' "$LIBRARY_MANIFEST_PATH")"
library_generated_at="$(jq -r '.generatedAt // empty' "$LIBRARY_MANIFEST_PATH")"
library_package="$(jq -r '.libraryPackage // empty' "$LIBRARY_MANIFEST_PATH")"
library_package_checksum="$(jq -r '.checksum.libraryPackage // empty' "$LIBRARY_MANIFEST_PATH")"
library_install_metadata="$(jq -r '.installMetadata // empty' "$LIBRARY_MANIFEST_PATH")"
library_install_metadata_checksum="$(jq -r '.checksum.installMetadata // empty' "$LIBRARY_MANIFEST_PATH")"
library_apps_index="$(jq -r '.appsIndex // empty' "$LIBRARY_MANIFEST_PATH")"
library_apps_index_checksum="$(jq -r '.checksum.appsIndex // empty' "$LIBRARY_MANIFEST_PATH")"
library_delta_file="$(jq -r '.deltaFiles.library // empty' "$LIBRARY_MANIFEST_PATH")"
library_apps_delta_file="$(jq -r '.deltaFiles.apps // empty' "$LIBRARY_MANIFEST_PATH")"
library_delta_checksum="$(jq -r '.checksum.libraryDelta // empty' "$LIBRARY_MANIFEST_PATH")"
library_apps_delta_checksum="$(jq -r '.checksum.appsDelta // empty' "$LIBRARY_MANIFEST_PATH")"

[[ -n "$catalog_dataset_version" ]] || fail "catalog manifest datasetVersion must not be empty"
[[ -n "$library_dataset_version" ]] || fail "library manifest datasetVersion must not be empty"
[[ "$catalog_dataset_version" == "$library_dataset_version" ]] || fail "datasetVersion mismatch between catalog and library manifests"

[[ -n "$catalog_channel" ]] || fail "catalog manifest channel must not be empty"
[[ -n "$library_channel" ]] || fail "library manifest channel must not be empty"
[[ "$catalog_channel" == "$library_channel" ]] || fail "channel mismatch between catalog and library manifests"

[[ -n "$catalog_generated_at" ]] || fail "catalog manifest generatedAt must not be empty"
[[ -n "$library_generated_at" ]] || fail "library manifest generatedAt must not be empty"
[[ "$catalog_generated_at" == "$library_generated_at" ]] || fail "generatedAt mismatch between catalog and library manifests"

[[ -n "$catalog_library_package" ]] || fail "catalog manifest libraryPackage must not be empty"
[[ -n "$catalog_library_checksum" ]] || fail "catalog manifest checksum.libraryPackage must not be empty"
[[ -n "$catalog_install_metadata" ]] || fail "catalog manifest installMetadata must not be empty"
[[ -n "$catalog_install_metadata_checksum" ]] || fail "catalog manifest checksum.installMetadata must not be empty"
[[ -n "$catalog_apps_index" ]] || fail "catalog manifest appsIndex must not be empty"
[[ -n "$catalog_apps_index_checksum" ]] || fail "catalog manifest checksum.appsIndex must not be empty"
[[ -n "$catalog_library_delta" ]] || fail "catalog manifest libraryDeltaFiles.library must not be empty"
[[ -n "$catalog_apps_delta" ]] || fail "catalog manifest libraryDeltaFiles.apps must not be empty"
[[ -n "$catalog_library_delta_checksum" ]] || fail "catalog manifest checksum.libraryDelta must not be empty"
[[ -n "$catalog_apps_delta_checksum" ]] || fail "catalog manifest checksum.appsDelta must not be empty"

[[ -n "$library_package" ]] || fail "library manifest libraryPackage must not be empty"
[[ -n "$library_package_checksum" ]] || fail "library manifest checksum.libraryPackage must not be empty"
[[ -n "$library_install_metadata" ]] || fail "library manifest installMetadata must not be empty"
[[ -n "$library_install_metadata_checksum" ]] || fail "library manifest checksum.installMetadata must not be empty"
[[ -n "$library_apps_index" ]] || fail "library manifest appsIndex must not be empty"
[[ -n "$library_apps_index_checksum" ]] || fail "library manifest checksum.appsIndex must not be empty"
[[ -n "$library_delta_file" ]] || fail "library manifest deltaFiles.library must not be empty"
[[ -n "$library_apps_delta_file" ]] || fail "library manifest deltaFiles.apps must not be empty"
[[ -n "$library_delta_checksum" ]] || fail "library manifest checksum.libraryDelta must not be empty"
[[ -n "$library_apps_delta_checksum" ]] || fail "library manifest checksum.appsDelta must not be empty"

[[ "$(catalog_basename "$catalog_library_package")" == "$library_package" ]] || fail "libraryPackage mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_library_checksum")" == "$library_package_checksum" ]] || fail "checksum.libraryPackage mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_install_metadata")" == "$library_install_metadata" ]] || fail "installMetadata mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_install_metadata_checksum")" == "$library_install_metadata_checksum" ]] || fail "checksum.installMetadata mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_apps_index")" == "$library_apps_index" ]] || fail "appsIndex mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_apps_index_checksum")" == "$library_apps_index_checksum" ]] || fail "checksum.appsIndex mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_library_delta")" == "$library_delta_file" ]] || fail "library delta file mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_apps_delta")" == "$library_apps_delta_file" ]] || fail "apps delta file mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_library_delta_checksum")" == "$library_delta_checksum" ]] || fail "checksum.libraryDelta mismatch between catalog and library manifests"
[[ "$(catalog_basename "$catalog_apps_delta_checksum")" == "$library_apps_delta_checksum" ]] || fail "checksum.appsDelta mismatch between catalog and library manifests"

echo "Validated shared app-store dataset manifests"