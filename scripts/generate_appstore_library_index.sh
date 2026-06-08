#!/usr/bin/env bash

set -euo pipefail

LIBRARY_ROOT=""
OUTPUT_DIR=""
DATASET_VERSION=""
GENERATED_AT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --library-root) LIBRARY_ROOT="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --dataset-version) DATASET_VERSION="$2"; shift 2 ;;
    --generated-at) GENERATED_AT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$LIBRARY_ROOT" ]] || { echo "--library-root is required" >&2; exit 1; }
[[ -n "$OUTPUT_DIR" ]] || { echo "--output-dir is required" >&2; exit 1; }
[[ -n "$DATASET_VERSION" ]] || { echo "--dataset-version is required" >&2; exit 1; }
[[ -d "$LIBRARY_ROOT/apps" ]] || { echo "library apps directory not found: $LIBRARY_ROOT/apps" >&2; exit 1; }

command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "zip is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 1; }

if [[ -z "$GENERATED_AT" ]]; then
  GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/apps"

tmp_json_dir=$(mktemp -d)

cleanup() {
  rm -rf "$tmp_json_dir"
}
trap cleanup EXIT

found_app=false

while IFS= read -r -d '' app_dir; do
  found_app=true
  app_name="$(basename "$app_dir")"
  app_output_dir="$OUTPUT_DIR/apps/$app_name"
  mkdir -p "$app_output_dir"

  bundle_name="bundle-${DATASET_VERSION}.zip"
  bundle_path="$app_output_dir/$bundle_name"
  (
    cd "$LIBRARY_ROOT/apps"
    zip -rq "$bundle_path" "$app_name"
  )
  sha256sum "$bundle_path" | awk '{print $1}' > "$bundle_path.sha256"

  variables_rel=""
  env_rel=""
  editions='[]'

  if [[ -f "$app_dir/variables.json" ]]; then
    variables_name="variables-${DATASET_VERSION}.json"
    cp "$app_dir/variables.json" "$app_output_dir/$variables_name"
    sha256sum "$app_output_dir/$variables_name" | awk '{print $1}' > "$app_output_dir/$variables_name.sha256"
    variables_rel="apps/${app_name}/${variables_name}"
    editions="$(jq -c '.edition // []' "$app_dir/variables.json")"
  fi

  if [[ -f "$app_dir/.env" ]]; then
    env_name="env-${DATASET_VERSION}.env"
    cp "$app_dir/.env" "$app_output_dir/$env_name"
    sha256sum "$app_output_dir/$env_name" | awk '{print $1}' > "$app_output_dir/$env_name.sha256"
    env_rel="apps/${app_name}/${env_name}"
  fi

  jq -n \
    --arg key "$app_name" \
    --arg bundle "apps/${app_name}/${bundle_name}" \
    --arg bundleChecksum "apps/${app_name}/${bundle_name}.sha256" \
    --arg variables "$variables_rel" \
    --arg variablesChecksum "${variables_rel:+${variables_rel}.sha256}" \
    --arg env "$env_rel" \
    --arg envChecksum "${env_rel:+${env_rel}.sha256}" \
    --argjson editions "$editions" \
    '{
      key: $key,
      bundle: $bundle,
      checksum: ({
        bundle: $bundleChecksum
      } + (if $variables != "" then {variables: $variablesChecksum} else {} end) + (if $env != "" then {env: $envChecksum} else {} end)),
      variables: (if $variables != "" then $variables else null end),
      env: (if $env != "" then $env else null end),
      editions: $editions
    }' > "$tmp_json_dir/${app_name}.json"
done < <(find "$LIBRARY_ROOT/apps" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

[[ "$found_app" == true ]] || { echo "no app directories found under $LIBRARY_ROOT/apps" >&2; exit 1; }

jq -s \
  --arg datasetVersion "$DATASET_VERSION" \
  --arg generatedAt "$GENERATED_AT" \
  '{
    schemaVersion: "1",
    datasetVersion: $datasetVersion,
    generatedAt: $generatedAt,
    apps: .
  }' "$tmp_json_dir"/*.json > "$OUTPUT_DIR/apps-index-${DATASET_VERSION}.json"

cp "$OUTPUT_DIR/apps-index-${DATASET_VERSION}.json" "$OUTPUT_DIR/apps-index.json"
sha256sum "$OUTPUT_DIR/apps-index-${DATASET_VERSION}.json" | awk '{print $1}' > "$OUTPUT_DIR/apps-index-${DATASET_VERSION}.json.sha256"
sha256sum "$OUTPUT_DIR/apps-index.json" | awk '{print $1}' > "$OUTPUT_DIR/apps-index.json.sha256"