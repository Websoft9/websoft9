#!/usr/bin/env bash

set -euo pipefail

CURRENT_INDEX=""
PREVIOUS_INDEX=""
OUTPUT_DIR=""
FROM_VERSION=""
TO_VERSION=""
GENERATED_AT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --current-index) CURRENT_INDEX="$2"; shift 2 ;;
    --previous-index) PREVIOUS_INDEX="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --from-version) FROM_VERSION="$2"; shift 2 ;;
    --to-version) TO_VERSION="$2"; shift 2 ;;
    --generated-at) GENERATED_AT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$CURRENT_INDEX" ]] || { echo "--current-index is required" >&2; exit 1; }
[[ -n "$OUTPUT_DIR" ]] || { echo "--output-dir is required" >&2; exit 1; }
[[ -n "$TO_VERSION" ]] || { echo "--to-version is required" >&2; exit 1; }
[[ -f "$CURRENT_INDEX" ]] || { echo "current index not found: $CURRENT_INDEX" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

mkdir -p "$OUTPUT_DIR"

if [[ -z "$GENERATED_AT" ]]; then
  GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

if [[ -z "$FROM_VERSION" ]]; then
  FROM_VERSION="bootstrap"
fi

if [[ -z "$PREVIOUS_INDEX" ]] || [[ ! -f "$PREVIOUS_INDEX" ]]; then
  jq -n \
    --arg fromVersion "$FROM_VERSION" \
    --arg toVersion "$TO_VERSION" \
    --arg generatedAt "$GENERATED_AT" \
    --slurpfile current "$CURRENT_INDEX" \
    '{
      scope: "library",
      mode: "bootstrap",
      fromVersion: $fromVersion,
      toVersion: $toVersion,
      changedApps: ($current[0].apps | map(.key)),
      generatedAt: $generatedAt
    }' > "$OUTPUT_DIR/library-delta-${FROM_VERSION}-to-${TO_VERSION}.json"

  jq -n \
    --arg fromVersion "$FROM_VERSION" \
    --arg toVersion "$TO_VERSION" \
    --arg generatedAt "$GENERATED_AT" \
    --slurpfile current "$CURRENT_INDEX" \
    '{
      scope: "apps",
      mode: "bootstrap",
      fromVersion: $fromVersion,
      toVersion: $toVersion,
      addedApps: ($current[0].apps | map(.key)),
      removedApps: [],
      changedApps: [],
      generatedAt: $generatedAt
    }' > "$OUTPUT_DIR/apps-delta-${FROM_VERSION}-to-${TO_VERSION}.json"
  exit 0
fi

jq -n \
  --arg fromVersion "$FROM_VERSION" \
  --arg toVersion "$TO_VERSION" \
  --arg generatedAt "$GENERATED_AT" \
  --slurpfile current "$CURRENT_INDEX" \
  --slurpfile previous "$PREVIOUS_INDEX" \
  '
  def index_apps(items):
    reduce items[] as $item ({}; . + {($item.key): $item});

  ($current[0].apps // []) as $currentApps |
  ($previous[0].apps // []) as $previousApps |
  ($currentApps | index_apps(.)) as $currentMap |
  ($previousApps | index_apps(.)) as $previousMap |
  (($currentMap | keys_unsorted) + ($previousMap | keys_unsorted) | unique) as $allKeys |
  {
    scope: "library",
    mode: "diff",
    fromVersion: $fromVersion,
    toVersion: $toVersion,
    changedApps: [ $allKeys[] | select(($currentMap[.] // null) != ($previousMap[.] // null)) ],
    generatedAt: $generatedAt
  }' > "$OUTPUT_DIR/library-delta-${FROM_VERSION}-to-${TO_VERSION}.json"

jq -n \
  --arg fromVersion "$FROM_VERSION" \
  --arg toVersion "$TO_VERSION" \
  --arg generatedAt "$GENERATED_AT" \
  --slurpfile current "$CURRENT_INDEX" \
  --slurpfile previous "$PREVIOUS_INDEX" \
  '
  def index_apps(items):
    reduce items[] as $item ({}; . + {($item.key): $item});

  ($current[0].apps // []) as $currentApps |
  ($previous[0].apps // []) as $previousApps |
  ($currentApps | index_apps(.)) as $currentMap |
  ($previousApps | index_apps(.)) as $previousMap |
  (($currentMap | keys_unsorted) + ($previousMap | keys_unsorted) | unique) as $allKeys |
  {
    scope: "apps",
    mode: "diff",
    fromVersion: $fromVersion,
    toVersion: $toVersion,
    addedApps: [ $allKeys[] | select(($previousMap[.] == null) and ($currentMap[.] != null)) ],
    removedApps: [ $allKeys[] | select(($previousMap[.] != null) and ($currentMap[.] == null)) ],
    changedApps: [ $allKeys[] | select(($previousMap[.] != null) and ($currentMap[.] != null) and ($previousMap[.] != $currentMap[.])) ],
    generatedAt: $generatedAt
  }' > "$OUTPUT_DIR/apps-delta-${FROM_VERSION}-to-${TO_VERSION}.json"