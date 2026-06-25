#!/usr/bin/env bash

set -euo pipefail

mode="${1:---readiness}"
timeout_seconds="${WEBSOFT9_HEALTHCHECK_TIMEOUT:-2}"
runtime_layout="${WEBSOFT9_RUNTIME_LAYOUT:-single-container-target}"
data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"

case "$runtime_layout" in
  legacy-multi-container)
    portainer_default_marker="$data_root/credential"
    npm_default_marker="$data_root/credential"
    npm_default_cert_marker="$data_root/custom_ssl/websoft9-self-signed.cert"
    ;;
  single-container-target)
    portainer_default_marker="$data_root/portainer/credential"
    npm_default_marker="$data_root/credential.json"
    npm_default_cert_marker="$data_root/custom_ssl/websoft9-self-signed.cert"
    ;;
  *)
    echo "unsupported runtime layout: $runtime_layout" >&2
    exit 1
    ;;
esac

portainer_marker="${WEBSOFT9_PORTAINER_BOOTSTRAP_MARKER:-$portainer_default_marker}"
npm_marker="${WEBSOFT9_NPM_BOOTSTRAP_MARKER:-$npm_default_marker}"
npm_cert_marker="${WEBSOFT9_NPM_CERT_MARKER:-$npm_default_cert_marker}"
apphub_config_path="${WEBSOFT9_APPHUB_CONFIG_PATH:-/websoft9/apphub/src/config/config.ini}"

platform_gateway_health_url() {
  python3 - "$apphub_config_path" <<'PY'
import configparser
import sys

config = configparser.ConfigParser()
config.read(sys.argv[1])
enabled = config.get("platform_gateway", "https_enabled", fallback="false").strip().lower()
scheme = "https" if enabled in {"true", "1", "yes", "on"} else "http"
print(f"{scheme}://127.0.0.1:9000/w9gateway/healthz")
PY
}

required_checks=(
  "apphub-api|${WEBSOFT9_APPHUB_HEALTH_URL:-http://127.0.0.1:8080/api/healthz}"
  "apphub-media|${WEBSOFT9_MEDIA_HEALTH_URL:-http://127.0.0.1:8081/healthz}"
)

get_supporting_checks() {
  cat <<EOF
platform-gateway|${WEBSOFT9_PLATFORM_GATEWAY_HEALTH_URL:-$(platform_gateway_health_url)}
gitea|${WEBSOFT9_GITEA_HEALTH_URL:-http://127.0.0.1:3001/}
portainer|${WEBSOFT9_PORTAINER_HEALTH_URL:-http://127.0.0.1:9004/api/system/status}
nginx-proxy-manager|${WEBSOFT9_NPM_HEALTH_URL:-http://127.0.0.1:81/}
EOF
}

check_url() {
  local name="$1"
  local url="$2"
  local status_code
  local curl_args=(--silent --show-error --max-time "$timeout_seconds" --output /dev/null --write-out '%{http_code}')

  if [[ "$url" == https://* ]]; then
    curl_args+=(--insecure)
  fi

  status_code="$(curl "${curl_args[@]}" "$url" || true)"

  if [[ "$status_code" != "000" && "$status_code" -lt 500 ]]; then
    echo "ready:${name}:${url}"
    return 0
  fi

  echo "failed:${name}:${url}:${status_code}"
  return 1
}

check_file() {
  local name="$1"
  local path="$2"

  if [[ -f "$path" ]]; then
    echo "ready:${name}:${path}"
    return 0
  fi

  echo "failed:${name}:${path}:missing"
  return 1
}

check_supervisor() {
  local supervisor_config="${WEBSOFT9_SUPERVISOR_CONFIG:-/etc/supervisor/conf.d/websoft9-platform.conf}"
  local socket_path="${WEBSOFT9_SUPERVISOR_SOCKET:-/run/supervisor.sock}"
  local pidfile_path="${WEBSOFT9_SUPERVISOR_PIDFILE:-/run/supervisord.pid}"

  if [[ "$mode" != "--strict" ]]; then
    if [[ -S "$socket_path" ]]; then
      echo "ready:runtime-supervisor:supervisord"
      return 0
    fi

    if [[ -f "$pidfile_path" ]] && kill -0 "$(cat "$pidfile_path")" >/dev/null 2>&1; then
      echo "ready:runtime-supervisor:supervisord"
      return 0
    fi

    echo "failed:runtime-supervisor:supervisord:missing"
    return 1
  fi

  if [[ -S "$socket_path" ]] && supervisorctl -c "$supervisor_config" status >/dev/null 2>&1; then
    echo "ready:runtime-supervisor:supervisord"
    return 0
  fi

  if [[ -f "$pidfile_path" ]] && kill -0 "$(cat "$pidfile_path")" >/dev/null 2>&1; then
    echo "ready:runtime-supervisor:supervisord"
    return 0
  fi

  echo "failed:runtime-supervisor:supervisord:missing"
  return 1
}

required_failures=()
degraded_services=()

if ! check_supervisor; then
  required_failures+=("runtime-supervisor")
fi

for check in "${required_checks[@]}"; do
  IFS='|' read -r name url <<<"$check"
  if ! check_url "$name" "$url"; then
    required_failures+=("$name")
  fi
done

if [[ "$mode" == "--strict" ]]; then
  while IFS= read -r check; do
    [[ -n "$check" ]] || continue
    IFS='|' read -r name url <<<"$check"
    if ! check_url "$name" "$url"; then
      degraded_services+=("$name")
    fi
  done < <(get_supporting_checks)

  if ! check_file "portainer-bootstrap" "$portainer_marker"; then
    degraded_services+=("portainer-bootstrap")
  fi

  if ! check_file "npm-bootstrap" "$npm_marker"; then
    degraded_services+=("nginx-proxy-manager-bootstrap")
  fi

  if ! check_file "npm-certificate" "$npm_cert_marker"; then
    degraded_services+=("nginx-proxy-manager-certificate")
  fi
fi

if [[ ${#required_failures[@]} -gt 0 ]]; then
  echo "status=unready required_failures=${required_failures[*]}"
  exit 1
fi

if [[ "$mode" == "--strict" && ${#degraded_services[@]} -gt 0 ]]; then
  echo "status=degraded degraded_services=${degraded_services[*]}"
  exit 1
fi

if [[ ${#degraded_services[@]} -gt 0 ]]; then
  echo "status=ready-with-degradation degraded_services=${degraded_services[*]}"
  exit 0
fi

echo "status=ready"