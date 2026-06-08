#!/usr/bin/env bash

set -euo pipefail

CURRENT=""
PREVIOUS=""
OUTPUT=""
ENTITY=""
FROM_VERSION=""
TO_VERSION=""
GENERATED_AT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --current) CURRENT="$2"; shift 2 ;;
    --previous) PREVIOUS="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --entity) ENTITY="$2"; shift 2 ;;
    --from-version) FROM_VERSION="$2"; shift 2 ;;
    --to-version) TO_VERSION="$2"; shift 2 ;;
    --generated-at) GENERATED_AT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$CURRENT" ]] || { echo "--current is required" >&2; exit 1; }
[[ -n "$OUTPUT" ]] || { echo "--output is required" >&2; exit 1; }
[[ -n "$ENTITY" ]] || { echo "--entity is required" >&2; exit 1; }
[[ -n "$TO_VERSION" ]] || { echo "--to-version is required" >&2; exit 1; }
[[ -f "$CURRENT" ]] || { echo "current file not found: $CURRENT" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

mkdir -p "$(dirname "$OUTPUT")"

if [[ -z "$GENERATED_AT" ]]; then
  GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

if [[ -z "$PREVIOUS" ]] || [[ ! -f "$PREVIOUS" ]]; then
  jq \
    --arg entity "$ENTITY" \
    --arg fromVersion "${FROM_VERSION:-bootstrap}" \
    --arg toVersion "$TO_VERSION" \
    --arg generatedAt "$GENERATED_AT" \
    '{
      entity: $entity,
      mode: "bootstrap",
      fromVersion: $fromVersion,
      toVersion: $toVersion,
      addedKeys: (map(.key) | map(select(. != null))),
      removedKeys: [],
      changedKeys: [],
      generatedAt: $generatedAt
    }' "$CURRENT" > "$OUTPUT"
  exit 0
fi

jq -n \
  --argfile current "$CURRENT" \
  --argfile previous "$PREVIOUS" \
  --arg entity "$ENTITY" \
  --arg fromVersion "$FROM_VERSION" \
  --arg toVersion "$TO_VERSION" \
  --arg generatedAt "$GENERATED_AT" \
  '
  def index_by_key(items):
    reduce items[] as $item ({};
      if ($item.key // "") == "" then . else . + {($item.key): $item} end
    );

  ($current | index_by_key(.)) as $currentMap |
  ($previous | index_by_key(.)) as $previousMap |
  (($currentMap | keys_unsorted) + ($previousMap | keys_unsorted) | unique) as $allKeys |
  {
    entity: $entity,
    mode: "diff",
    fromVersion: ($fromVersion | if . == "" then "unknown" else . end),
    toVersion: $toVersion,
    addedKeys: [ $allKeys[] | select(($previousMap[.] == null) and ($currentMap[.] != null)) ],
    removedKeys: [ $allKeys[] | select(($previousMap[.] != null) and ($currentMap[.] == null)) ],
    changedKeys: [ $allKeys[] | select(($previousMap[.] != null) and ($currentMap[.] != null) and ($previousMap[.] != $currentMap[.])) ],
    generatedAt: $generatedAt
  }
  ' > "$OUTPUT"