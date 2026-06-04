#!/usr/bin/env bash

set -euo pipefail

/app/init_nginx.sh --prepare-only

exec /websoft9/script/platform-entrypoint.sh