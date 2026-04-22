#!/usr/bin/env bash

set -euo pipefail

gateway_root="/etc/websoft9/platform-gateway"
runtime_config_dir="/run/websoft9/platform-gateway"
runtime_config="$runtime_config_dir/nginx.conf"
pid_path="/run/websoft9/platform-gateway.pid"

render_gateway_config() {
  mkdir -p \
    "$runtime_config_dir" \
    /var/log/websoft9 \
    /var/log/nginx \
    /var/cache/nginx/client_temp \
    /var/cache/nginx/proxy_temp \
    /var/cache/nginx/fastcgi_temp \
    /var/cache/nginx/uwsgi_temp \
    /var/cache/nginx/scgi_temp
  cp "$gateway_root/nginx.conf" "$runtime_config"
  sed -i "s#{{DOCKER0_IP}}#${DOCKER0_IP:-172.17.0.1}#g" "$gateway_root/platform-gateway-routes.conf"

  if [[ "${WEBSOFT9_RUNTIME_LAYOUT:-single-container-target}" == "single-container-target" ]]; then
    sed -i 's#http://websoft9-deployment:9000#http://127.0.0.1:9000#g' "$gateway_root/platform-gateway-routes.conf"
    sed -i 's#http://websoft9-proxy:81#http://127.0.0.1:81#g' "$gateway_root/platform-gateway-routes.conf"
    sed -i 's#http://websoft9-git:3001#http://127.0.0.1:3001#g' "$gateway_root/platform-gateway-routes.conf"
    sed -i 's#http://websoft9-apphub:8080#http://127.0.0.1:8080#g' "$gateway_root/platform-gateway-routes.conf"
    sed -i 's#http://websoft9-apphub:8081#http://127.0.0.1:8081#g' "$gateway_root/platform-gateway-routes.conf"
  fi
}

main() {
  render_gateway_config
  exec /usr/sbin/nginx -c "$runtime_config" -g "daemon off;"
}

main "$@"