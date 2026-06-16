#!/usr/bin/env bash

set -euo pipefail

service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-/data/logs}"

mkdir -p /run/nginx /tmp/nginx/body /var/cache/nginx /var/lib/nginx/cache/private /var/lib/nginx/cache/public /var/log/nginx /data/logs "$service_log_root/nginx-proxy-manager"
rm -f /run/nginx/nginx.pid

exec /usr/sbin/nginx