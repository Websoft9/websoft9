#!/usr/bin/env bash

set -euo pipefail

export PUID="${PUID:-0}"
export PGID="${PGID:-0}"
export NPMUSER="${NPMUSER:-npm}"
export NPMGROUP="${NPMGROUP:-npm}"
export NPMHOME="${NPMHOME:-/tmp/npmuserhome}"
export HOME="$NPMHOME"

mkdir -p "$NPMHOME" /data/logs /var/log/websoft9/nginx-proxy-manager

cd /app
exec /usr/bin/node --abort_on_uncaught_exception --max_old_space_size=250 index.js