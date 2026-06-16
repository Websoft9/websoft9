#!/usr/bin/env bash

set -euo pipefail

export PUID="${PUID:-0}"
export PGID="${PGID:-0}"
export NPMUSER="${NPMUSER:-npm}"
export NPMGROUP="${NPMGROUP:-npm}"
export NPMHOME="${NPMHOME:-/tmp/npmuserhome}"
export HOME="$NPMHOME"
service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-/data/logs}"

mkdir -p "$NPMHOME" /data/logs "$service_log_root/nginx-proxy-manager"

cd /app
exec /usr/bin/node --abort_on_uncaught_exception --max_old_space_size=250 index.js