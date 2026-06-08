#!/usr/bin/env bash

set -euo pipefail

LIBRARY_ROOT="${1:-library-dev/library}"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || fail "jq is required"

[[ -d "$LIBRARY_ROOT" ]] || fail "library root not found: $LIBRARY_ROOT"
[[ -d "$LIBRARY_ROOT/apps" ]] || fail "library apps directory not found: $LIBRARY_ROOT/apps"

FOUND_APP=false
VALID_APP=false

while IFS= read -r -d '' variables_file; do
  FOUND_APP=true
  VALID_APP=true

  jq -e '
    (.edition | type) == "array" and
    (.edition | length) > 0 and
    all(.edition[]; (.dist | type) == "string" and (.dist | length) > 0 and (.version | type) == "string" and (.version | length) > 0)
  ' "$variables_file" >/dev/null || fail "invalid edition schema in ${variables_file#$LIBRARY_ROOT/}"
done < <(find "$LIBRARY_ROOT/apps" -mindepth 2 -maxdepth 2 -type f -name variables.json -print0)

[[ "$FOUND_APP" == true ]] || fail "no variables.json files found under $LIBRARY_ROOT/apps"
[[ "$VALID_APP" == true ]] || fail "no valid app entries found under $LIBRARY_ROOT/apps"

echo "Validated app-store library artifact in $LIBRARY_ROOT"