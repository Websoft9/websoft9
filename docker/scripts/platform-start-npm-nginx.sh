#!/usr/bin/env bash

set -euo pipefail

mkdir -p /run/nginx /tmp/nginx/body /var/cache/nginx /var/lib/nginx/cache/private /var/lib/nginx/cache/public /var/log/nginx /data/logs /var/log/websoft9/nginx-proxy-manager
rm -f /run/nginx/nginx.pid

exec /usr/sbin/nginx