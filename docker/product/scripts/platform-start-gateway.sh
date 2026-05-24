#!/usr/bin/env bash

set -euo pipefail

gateway_root="/etc/websoft9/platform-gateway"
runtime_config_dir="/run/websoft9/platform-gateway"
runtime_config="$runtime_config_dir/nginx.conf"
pid_path="/run/websoft9/platform-gateway.pid"
apphub_config_path="${WEBSOFT9_APPHUB_CONFIG_PATH:-/websoft9/apphub/src/config/config.ini}"

read_platform_gateway_settings() {
  python3 - "$apphub_config_path" <<'PY'
import configparser
import os
import sys

config = configparser.ConfigParser()
config.read(sys.argv[1])

def get_value(section, key, default=""):
    return config.get(section, key, fallback=default).strip()

https_enabled = get_value("platform_gateway", "https_enabled", "false")
force_https = get_value("platform_gateway", "force_https", "false")
bound_domain = get_value("platform_gateway", "bound_domain", "")
ssl_cert = get_value("platform_gateway", "ssl_cert", os.getenv("WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH", "/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.cert"))
ssl_key = get_value("platform_gateway", "ssl_key", os.getenv("WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH", "/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.key"))
print(https_enabled.lower())
print(force_https.lower())
print(bound_domain)
print(ssl_cert)
print(ssl_key)
PY
}

is_platform_https_enabled() {
  local https_enabled="${1:-false}"
  [[ "$https_enabled" == "false" || "$https_enabled" == "0" || "$https_enabled" == "no" || "$https_enabled" == "off" ]] && echo "false" || echo "true"
}

ensure_platform_gateway_tls_assets() {
  local ssl_cert="$1"
  local ssl_key="$2"

  mkdir -p "$(dirname "$ssl_cert")" "$(dirname "$ssl_key")"

  if [[ -s "$ssl_cert" && -s "$ssl_key" ]]; then
    return 0
  fi

  openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$ssl_key" \
    -out "$ssl_cert" \
    -days 3650 \
    -subj "/CN=Websoft9 Platform Gateway" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    -addext "subjectAltName=DNS:*,IP:0.0.0.0" >/dev/null 2>&1

  chmod 644 "$ssl_cert"
  chmod 600 "$ssl_key"
}

render_platform_gateway_ssl_config() {
  local ssl_cert="$1"
  local ssl_key="$2"

  cat > "$gateway_root/platform-gateway-ssl.conf" <<EOF
ssl_certificate $ssl_cert;
ssl_certificate_key $ssl_key;
EOF
}

render_default_server() {
  local https_enabled="$1"
  local force_https="$2"
  local bound_domain="$3"

  cat > "$gateway_root/default.conf" <<'EOF'
server {
EOF

  if [[ "$https_enabled" == "true" ]]; then
    cat >> "$gateway_root/default.conf" <<'EOF'
  listen 9000 ssl default_server;
  listen [::]:9000 ssl default_server;
EOF
  else
    cat >> "$gateway_root/default.conf" <<'EOF'
  listen 9000 default_server;
  listen [::]:9000 default_server;
EOF
  fi

  printf '\n' >> "$gateway_root/default.conf"
  if [[ -n "$bound_domain" ]]; then
    printf '  server_name %s;\n' "$bound_domain" >> "$gateway_root/default.conf"
  else
    cat >> "$gateway_root/default.conf" <<'EOF'
  server_name _;
EOF
  fi

  cat >> "$gateway_root/default.conf" <<'EOF'
  set $websoft9_route_owner "platform-gateway";
  set $websoft9_app_access_owner "nginx-proxy-manager";

  add_header X-Websoft9-Route-Owner $websoft9_route_owner always;
  add_header X-Websoft9-App-Access-Owner $websoft9_app_access_owner always;
  add_header X-Websoft9-Reserved-Platform-Prefixes "/,/api/,/w9deployment/,/w9proxy/,/w9git/,/w9gateway/healthz" always;
EOF

  if [[ "$https_enabled" == "true" ]]; then
    cat >> "$gateway_root/default.conf" <<'EOF'

  include /etc/websoft9/platform-gateway/platform-gateway-ssl.conf;
EOF
    if [[ "$force_https" == "true" ]]; then
      cat >> "$gateway_root/default.conf" <<'EOF'
  error_page 497 =308 https://$host:9000$request_uri;
EOF
    fi
  fi

  cat >> "$gateway_root/default.conf" <<'EOF'
  include /etc/websoft9/platform-gateway/platform-gateway-routes.conf;
}
EOF
}

render_gateway_config() {
  local raw_https_enabled raw_force_https bound_domain ssl_cert ssl_key https_enabled force_https
  mapfile -t gateway_settings < <(read_platform_gateway_settings)
  raw_https_enabled="${gateway_settings[0]:-false}"
  raw_force_https="${gateway_settings[1]:-false}"
  bound_domain="${gateway_settings[2]:-}"
  ssl_cert="${gateway_settings[3]:-/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.cert}"
  ssl_key="${gateway_settings[4]:-/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.key}"
  https_enabled="$(is_platform_https_enabled "$raw_https_enabled")"
  force_https="$(is_platform_https_enabled "$raw_force_https")"

  mkdir -p \
    "$runtime_config_dir" \
    /var/log/websoft9 \
    /var/log/nginx \
    /var/cache/nginx/client_temp \
    /var/cache/nginx/proxy_temp \
    /var/cache/nginx/fastcgi_temp \
    /var/cache/nginx/uwsgi_temp \
    /var/cache/nginx/scgi_temp
  if [[ "$https_enabled" == "true" ]]; then
    ensure_platform_gateway_tls_assets "$ssl_cert" "$ssl_key"
    render_platform_gateway_ssl_config "$ssl_cert" "$ssl_key"
  fi
  cp "$gateway_root/nginx.conf" "$runtime_config"
  render_default_server "$https_enabled" "$force_https" "$bound_domain"
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