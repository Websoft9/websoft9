#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/appstore_dataset_hotfix_helper.sh --mode list --channel <dev|rc|release> [--local-root <dir>]
  scripts/appstore_dataset_hotfix_helper.sh --mode plan --channel <dev|rc|release> --dataset-version <version> [--local-root <dir>]
  scripts/appstore_dataset_hotfix_helper.sh --mode switch --channel <dev|rc|release> --dataset-version <version> [--local-root <dir>] [--apply]

Default behavior is dry-run. Use --apply to write latest manifest.json files.

Optional layout selection:
  --layout legacy   => artifact/<channel>/websoft9/plugin/{catalog,library}
  --layout v2       => artifact/websoft9/v2/<channel>/appstore/{catalog,library}

Remote mode requirements:
  export AWS_ACCESS_KEY_ID=...
  export AWS_SECRET_ACCESS_KEY=...
  export CLOUDFLARE_ACCOUNT_ID=...
EOF
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

dataset_version_of() {
  local manifest_path="$1"
  jq -r '.datasetVersion // empty' "$manifest_path"
}

generated_at_of() {
  local manifest_path="$1"
  jq -r '.generatedAt // empty' "$manifest_path"
}

print_summary() {
  local label="$1"
  local manifest_path="$2"
  local dataset_version generated_at

  dataset_version=$(dataset_version_of "$manifest_path")
  generated_at=$(generated_at_of "$manifest_path")

  echo "$label datasetVersion: ${dataset_version:-unknown}"
  echo "$label generatedAt: ${generated_at:-unknown}"
}

print_switch_plan() {
  local current_catalog_manifest="$1"
  local current_library_manifest="$2"
  local target_catalog_manifest="$3"
  local target_library_manifest="$4"

  echo "Current state:"
  print_summary "Catalog" "$current_catalog_manifest"
  print_summary "Library" "$current_library_manifest"
  echo "Target state:"
  print_summary "Catalog" "$target_catalog_manifest"
  print_summary "Library" "$target_library_manifest"
}

MODE=""
CHANNEL=""
DATASET_VERSION=""
LOCAL_ROOT=""
APPLY=false
BUCKET="artifact"
LAYOUT="legacy"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --channel)
      CHANNEL="$2"
      shift 2
      ;;
    --dataset-version)
      DATASET_VERSION="$2"
      shift 2
      ;;
    --local-root)
      LOCAL_ROOT="$2"
      shift 2
      ;;
    --bucket)
      BUCKET="$2"
      shift 2
      ;;
    --layout)
      LAYOUT="$2"
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
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

[[ "$MODE" =~ ^(list|plan|switch)$ ]] || fail "--mode must be list, plan, or switch"
[[ "$CHANNEL" =~ ^(dev|rc|release)$ ]] || fail "--channel must be dev, rc, or release"
[[ "$LAYOUT" =~ ^(legacy|v2)$ ]] || fail "--layout must be legacy or v2"
if [[ "$MODE" =~ ^(plan|switch)$ ]]; then
  [[ -n "$DATASET_VERSION" ]] || fail "--dataset-version is required for plan or switch mode"
fi

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

catalog_dir="$workdir/catalog"
library_dir="$workdir/library"
mkdir -p "$catalog_dir" "$library_dir"

if [[ "$LAYOUT" == "legacy" ]]; then
  catalog_prefix="$CHANNEL/websoft9/plugin/catalog"
  library_prefix="$CHANNEL/websoft9/plugin/library"
else
  catalog_prefix="websoft9/v2/$CHANNEL/appstore/catalog"
  library_prefix="websoft9/v2/$CHANNEL/appstore/library"
fi

download_from_remote() {
  command -v aws >/dev/null 2>&1 || fail "aws CLI is required for remote mode"
  [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]] || fail "CLOUDFLARE_ACCOUNT_ID is required for remote mode"
  endpoint="https://${CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

  aws s3 cp "s3://$BUCKET/$catalog_prefix/manifest.json" "$catalog_dir/manifest.json" --endpoint-url="$endpoint"
  aws s3 cp "s3://$BUCKET/$library_prefix/manifest.json" "$library_dir/manifest.json" --endpoint-url="$endpoint"

  while IFS= read -r name; do
    aws s3 cp "s3://$BUCKET/$catalog_prefix/$name" "$catalog_dir/$name" --endpoint-url="$endpoint"
  done < <(aws s3 ls "s3://$BUCKET/$catalog_prefix/" --endpoint-url="$endpoint" | awk '{print $4}' | grep '^manifest-.*\.json$' || true)

  while IFS= read -r name; do
    aws s3 cp "s3://$BUCKET/$library_prefix/$name" "$library_dir/$name" --endpoint-url="$endpoint"
  done < <(aws s3 ls "s3://$BUCKET/$library_prefix/" --endpoint-url="$endpoint" | awk '{print $4}' | grep '^manifest-.*\.json$' || true)
}

copy_from_local() {
  [[ -d "$LOCAL_ROOT/$catalog_prefix" ]] || fail "local catalog path not found: $LOCAL_ROOT/$catalog_prefix"
  [[ -d "$LOCAL_ROOT/$library_prefix" ]] || fail "local library path not found: $LOCAL_ROOT/$library_prefix"
  cp "$LOCAL_ROOT/$catalog_prefix"/manifest*.json "$catalog_dir/"
  cp "$LOCAL_ROOT/$library_prefix"/manifest*.json "$library_dir/"
}

if [[ -n "$LOCAL_ROOT" ]]; then
  copy_from_local
else
  download_from_remote
fi

if [[ "$MODE" == "list" ]]; then
  print_summary "Current catalog" "$catalog_dir/manifest.json"
  print_summary "Current library" "$library_dir/manifest.json"
  echo "Shared historical dataset versions:"
  bash scripts/list_appstore_dataset_versions.sh --catalog-dir "$catalog_dir" --library-dir "$library_dir"
  exit 0
fi

target_catalog_manifest="$catalog_dir/manifest-${DATASET_VERSION}.json"
target_library_manifest="$library_dir/manifest-${DATASET_VERSION}.json"

[[ -f "$target_catalog_manifest" ]] || fail "target catalog manifest not found: $target_catalog_manifest"
[[ -f "$target_library_manifest" ]] || fail "target library manifest not found: $target_library_manifest"

print_switch_plan "$catalog_dir/manifest.json" "$library_dir/manifest.json" "$target_catalog_manifest" "$target_library_manifest"

if [[ "$MODE" == "plan" ]]; then
  echo "Plan only. No manifest files were changed."
  exit 0
fi

bash scripts/switch_appstore_dataset_manifest.sh --catalog-dir "$catalog_dir" --library-dir "$library_dir" --dataset-version "$DATASET_VERSION"

if ! $APPLY; then
  echo "Dry-run only. Latest manifests prepared locally but not uploaded."
  echo "Prepared state:"
  print_summary "Catalog" "$catalog_dir/manifest.json"
  print_summary "Library" "$library_dir/manifest.json"
  echo "Prepared catalog manifest: $catalog_dir/manifest.json"
  echo "Prepared library manifest: $library_dir/manifest.json"
  exit 0
fi

[[ -n "$LOCAL_ROOT" ]] || {
  command -v aws >/dev/null 2>&1 || fail "aws CLI is required for remote apply"
  [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]] || fail "CLOUDFLARE_ACCOUNT_ID is required for remote apply"
  endpoint="https://${CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"
  aws s3 cp "$catalog_dir/manifest.json" "s3://$BUCKET/$catalog_prefix/manifest.json" --endpoint-url="$endpoint"
  aws s3 cp "$library_dir/manifest.json" "s3://$BUCKET/$library_prefix/manifest.json" --endpoint-url="$endpoint"
  echo "Applied remote manifest switch for datasetVersion ${DATASET_VERSION} on channel ${CHANNEL}"
  exit 0
}

cp "$catalog_dir/manifest.json" "$LOCAL_ROOT/$catalog_prefix/manifest.json"
cp "$library_dir/manifest.json" "$LOCAL_ROOT/$library_prefix/manifest.json"
echo "Applied local manifest switch for datasetVersion ${DATASET_VERSION} on channel ${CHANNEL}"