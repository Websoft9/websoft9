#!/usr/bin/env bash

set -euo pipefail

data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
runtime_state_dir="${WEBSOFT9_RUNTIME_STATE_DIR:-/run/websoft9}"
runtime_status_file="${WEBSOFT9_RUNTIME_STATUS_FILE:-$runtime_state_dir/runtime-status.json}"
supervisor_config="${WEBSOFT9_SUPERVISOR_CONFIG:-/etc/supervisor/conf.d/websoft9-platform.conf}"
supervisor_socket="${WEBSOFT9_SUPERVISOR_SOCKET:-/run/supervisor.sock}"
status_interval="${WEBSOFT9_STATUS_INTERVAL:-60}"
strict_status_interval="${WEBSOFT9_STRICT_STATUS_INTERVAL:-1800}"
platform_runtime_log_path="${WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH:-$data_root/logs/platform-runtime.log}"
product_auth_credential_path="${WEBSOFT9_PRODUCT_AUTH_CREDENTIAL_PATH:-$data_root/product-auth/credential.json}"
service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-$data_root/logs}"
custom_root="${WEBSOFT9_CUSTOM_ROOT:-$data_root/config}"
platform_network_name="${WEBSOFT9_PLATFORM_NETWORK_NAME:-websoft9}"
platform_container_ref="${WEBSOFT9_PLATFORM_CONTAINER_REF:-${HOSTNAME:-}}"
docker_socket_path="${WEBSOFT9_DOCKER_SOCKET_PATH:-/var/run/docker.sock}"

export WEBSOFT9_DATA_ROOT="$data_root"
export WEBSOFT9_SERVICE_LOG_ROOT="$service_log_root"
export WEBSOFT9_CUSTOM_ROOT="$custom_root"
export WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR="${WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR:-$custom_root/internal-gateway-auth}"
export WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE="${WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE:-$WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR/trust_key}"
export WEBSOFT9_HOST_ACCESS_DATA_DIR="${WEBSOFT9_HOST_ACCESS_DATA_DIR:-$custom_root/host-access}"
export WEBSOFT9_INSTALL_TRACKING_DIR="${WEBSOFT9_INSTALL_TRACKING_DIR:-$custom_root/apphub}"
export WEBSOFT9_PRODUCT_AUTH_DATA_DIR="${WEBSOFT9_PRODUCT_AUTH_DATA_DIR:-$custom_root/product-auth}"
export WEBSOFT9_GITEA_DATA_DIR="${WEBSOFT9_GITEA_DATA_DIR:-$data_root/gitea}"
export WEBSOFT9_GITEA_CREDENTIAL_PATH="${WEBSOFT9_GITEA_CREDENTIAL_PATH:-$WEBSOFT9_GITEA_DATA_DIR/credential}"
export WEBSOFT9_PORTAINER_DATA_DIR="${WEBSOFT9_PORTAINER_DATA_DIR:-$data_root/portainer}"
export WEBSOFT9_PORTAINER_CREDENTIAL_PATH="${WEBSOFT9_PORTAINER_CREDENTIAL_PATH:-$WEBSOFT9_PORTAINER_DATA_DIR/credential}"
export WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH="${WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH:-$custom_root/platform-gateway/ssl/websoft9-platform-gateway.cert}"
export WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH="${WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH:-$custom_root/platform-gateway/ssl/websoft9-platform-gateway.key}"
export WEBSOFT9_NPM_CREDENTIAL_PATH="${WEBSOFT9_NPM_CREDENTIAL_PATH:-$data_root/credential.json}"
export WEBSOFT9_NPM_DATABASE_PATH="${WEBSOFT9_NPM_DATABASE_PATH:-$data_root/database.sqlite}"
export WEBSOFT9_NPM_SSL_DIR="${WEBSOFT9_NPM_SSL_DIR:-$data_root/custom_ssl}"
export WEBSOFT9_NPM_CERT_MARKER="${WEBSOFT9_NPM_CERT_MARKER:-$WEBSOFT9_NPM_SSL_DIR/websoft9-self-signed.cert}"
export WEBSOFT9_NPM_SSL_KEY_PATH="${WEBSOFT9_NPM_SSL_KEY_PATH:-$WEBSOFT9_NPM_SSL_DIR/websoft9-self-signed.key}"
export WEBSOFT9_NPM_LETSENCRYPT_DIR="${WEBSOFT9_NPM_LETSENCRYPT_DIR:-$data_root/letsencrypt}"
export WEBSOFT9_NPM_ACME_ROOT="${WEBSOFT9_NPM_ACME_ROOT:-$data_root/letsencrypt-acme-challenge}"
export WEBSOFT9_NPM_NGINX_ROOT="${WEBSOFT9_NPM_NGINX_ROOT:-$data_root/nginx}"
export WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH="${WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH:-$service_log_root/platform-runtime.log}"

ensure_legacy_compat_link() {
  local target_path="$1"
  local legacy_path="$2"
  local legacy_parent

  mkdir -p "$target_path"
  legacy_parent="$(dirname "$legacy_path")"
  mkdir -p "$legacy_parent"

  if [[ -L "$legacy_path" ]]; then
    return 0
  fi

  if [[ -d "$legacy_path" ]]; then
    if [[ -n "$(find "$legacy_path" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
      cp -a "$legacy_path/." "$target_path/"
    fi
    rm -rf "$legacy_path"
  elif [[ -e "$legacy_path" ]]; then
    rm -f "$legacy_path"
  fi

  ln -s "$target_path" "$legacy_path"
}

ensure_data_managed_paths() {
  mkdir -p "$custom_root" "$service_log_root"
  ensure_legacy_compat_link "$custom_root" /etc/custom
  ensure_legacy_compat_link "$service_log_root" /var/log/websoft9
}

write_runtime_event() {
  local level="$1"
  local event="$2"
  local message="$3"

  mkdir -p "$(dirname "$platform_runtime_log_path")"
  python3 - "$platform_runtime_log_path" "$level" "$event" "$message" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, level, event, message = sys.argv[1:5]
payload = {
    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "level": level,
    "component": "platform-entrypoint",
    "domain": "runtime",
    "event": event,
    "message": message,
}
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
PY
}

log_event() {
  local level="$1"
  local event="$2"
  local message="$3"

  echo "$(date '+%Y-%m-%d %H:%M:%S') [platform-entrypoint] $message"
  write_runtime_event "$level" "$event" "$message"
}

write_status() {
  local state="$1"
  local detail="$2"

  detail="${detail//$'\n'/\\n}"
  detail="${detail//"/\\"}"

  mkdir -p "$runtime_state_dir"
  cat >"$runtime_status_file" <<EOF
{"state":"$state","updated_at":"$(date -u '+%Y-%m-%dT%H:%M:%SZ')","detail":"$detail"}
EOF
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local timeout_seconds="$3"
  local started_at
  local status_code
  local curl_args=(--silent --show-error --max-time 2 --output /dev/null --write-out '%{http_code}')

  started_at="$(date +%s)"

  if [[ "$url" == https://* ]]; then
    curl_args+=(--insecure)
  fi

  while true; do
    status_code="$(curl "${curl_args[@]}" "$url" || true)"
    if [[ "$status_code" != "000" && "$status_code" -lt 500 ]]; then
      log_event "info" "wait.ready" "phase=wait name=$name result=ready url=$url status=$status_code"
      return 0
    fi

    if (( $(date +%s) - started_at >= timeout_seconds )); then
      log_event "warning" "wait.timeout" "phase=wait name=$name result=timeout url=$url status=$status_code"
      return 1
    fi

    sleep 2
  done
}

wait_for_file() {
  local name="$1"
  local path="$2"
  local timeout_seconds="$3"
  local started_at

  started_at="$(date +%s)"

  while true; do
    if [[ -e "$path" ]]; then
      log_event "info" "wait.ready" "phase=wait name=$name result=ready path=$path"
      return 0
    fi

    if (( $(date +%s) - started_at >= timeout_seconds )); then
      log_event "warning" "wait.timeout" "phase=wait name=$name result=timeout path=$path"
      return 1
    fi

    sleep 2
  done
}

sync_runtime_config() {
  local mode="$1"

  /websoft9/script/platform-sync-config.sh --mode "$mode"
}

update_runtime_status() {
  local mode="${1:-strict}"
  local output

  if output="$(/websoft9/script/platform-healthcheck.sh --"$mode" 2>&1)"; then
    write_status "ready" "$output"
    return 0
  fi

  if [[ "$mode" != "strict" ]]; then
    write_status "failed" "$output"
    return 1
  fi

  if output="$(/websoft9/script/platform-healthcheck.sh --readiness 2>&1)"; then
    write_status "degraded" "$output"
    return 0
  fi

  write_status "failed" "$output"
  return 1
}

docker_api_request() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local curl_args=(
    --silent
    --show-error
    --unix-socket "$docker_socket_path"
    --write-out $'\n%{http_code}'
    --request "$method"
  )

  if [[ -n "$payload" ]]; then
    curl_args+=(--header 'Content-Type: application/json' --data "$payload")
  fi

  curl "${curl_args[@]}" "http://localhost${path}"
}

docker_api_status() {
  local response="$1"
  printf '%s' "$response" | tail -n 1
}

docker_api_body() {
  local response="$1"
  printf '%s' "$response" | sed '$d'
}

ensure_platform_network() {
  log_event "info" "runtime-network.ensure" "phase=runtime-network action=ensure name=$platform_network_name"

  if [[ ! -S "$docker_socket_path" ]]; then
    log_event "warning" "runtime-network.skip" "phase=runtime-network result=skip reason=docker-socket-unavailable path=$docker_socket_path"
    return 0
  fi

  local network_response
  local network_status
  network_response="$(docker_api_request GET "/networks/$platform_network_name")"
  network_status="$(docker_api_status "$network_response")"

  if [[ "$network_status" == "404" ]]; then
    docker_api_request POST "/networks/create" "{\"Name\":\"$platform_network_name\",\"Driver\":\"bridge\"}" >/dev/null
    log_event "info" "runtime-network.created" "phase=runtime-network result=created name=$platform_network_name"
  elif [[ "$network_status" != "200" ]]; then
    log_event "warning" "runtime-network.skip" "phase=runtime-network result=skip reason=network-inspect-failed status=$network_status"
    return 0
  else
    log_event "info" "runtime-network.exists" "phase=runtime-network result=exists name=$platform_network_name"
  fi

  if [[ -z "$platform_container_ref" ]]; then
    log_event "warning" "runtime-network.skip-connect" "phase=runtime-network result=skip-connect reason=missing-container-ref"
    return 0
  fi

  local container_response
  local container_status
  local container_body
  container_response="$(docker_api_request GET "/containers/$platform_container_ref/json")"
  container_status="$(docker_api_status "$container_response")"
  container_body="$(docker_api_body "$container_response")"

  if [[ "$container_status" == "404" ]]; then
    log_event "warning" "runtime-network.skip-connect" "phase=runtime-network result=skip-connect reason=container-not-found ref=$platform_container_ref"
    return 0
  elif [[ "$container_status" != "200" ]]; then
    log_event "warning" "runtime-network.skip-connect" "phase=runtime-network result=skip-connect reason=container-inspect-failed status=$container_status ref=$platform_container_ref"
    return 0
  fi

  if printf '%s' "$container_body" | grep -Fq "\"$platform_network_name\":{"; then
    log_event "info" "runtime-network.attached" "phase=runtime-network result=attached name=$platform_network_name ref=$platform_container_ref"
    return 0
  fi

  docker_api_request POST "/networks/$platform_network_name/connect" "{\"Container\":\"$platform_container_ref\"}" >/dev/null
  log_event "info" "runtime-network.connected" "phase=runtime-network result=connected name=$platform_network_name ref=$platform_container_ref"
}

ensure_service_log_roots() {
  mkdir -p "$service_log_root/gitea" "$service_log_root/portainer" "$service_log_root/npm"

}

shutdown_supervisor() {
  if [[ -S "$supervisor_socket" ]]; then
    supervisorctl -c "$supervisor_config" shutdown >/dev/null 2>&1 || true
  fi
}

start_supervisor() {
  log_event "info" "core-bootstrap.start-supervisor" "phase=core-bootstrap action=start-supervisor"

  mkdir -p "$runtime_state_dir"
  ensure_service_log_roots
  supervisord -c "$supervisor_config"
  wait_for_file "supervisor-socket" "$supervisor_socket" 30
}

start_apphub_core() {
  log_event "info" "core-bootstrap.start-apphub-core" "phase=core-bootstrap action=start-apphub-core"

  wait_for_url "apphub-api" "${WEBSOFT9_APPHUB_HEALTH_URL:-http://127.0.0.1:8080/api/healthz}" 60
  wait_for_url "apphub-media" "${WEBSOFT9_MEDIA_HEALTH_URL:-http://127.0.0.1:8081/healthz}" 60
}

bootstrap_product_auth() {
  log_event "info" "workspace-bootstrap.bootstrap-product-auth" "phase=workspace-bootstrap action=bootstrap-product-auth"
  local output
  output="$(python3 - <<'PY'
import os
import sys

sys.path.insert(0, "/websoft9/apphub")

from src.services.product_auth import ProductAuthService

status = ProductAuthService().get_status()
print(
    "product_auth_status="
    + ("initialization-required" if status["initialization_required"] else "initialized")
)
PY
  )"
  log_event "info" "workspace-bootstrap.bootstrap-product-auth.result" "$output"
}

bootstrap_platform_gateway() {
  log_event "info" "workspace-bootstrap.bootstrap-platform-gateway" "phase=workspace-bootstrap action=bootstrap-platform-gateway"

  local platform_gateway_health_url
  platform_gateway_health_url="${WEBSOFT9_PLATFORM_GATEWAY_HEALTH_URL:-$(python3 - "${WEBSOFT9_APPHUB_CONFIG_PATH:-/websoft9/apphub/src/config/config.ini}" <<'PY'
import configparser
import sys

config = configparser.ConfigParser()
config.read(sys.argv[1])
enabled = config.get("platform_gateway", "https_enabled", fallback="false").strip().lower()
scheme = "https" if enabled in {"true", "1", "yes", "on"} else "http"
print(f"{scheme}://127.0.0.1:9000/w9gateway/healthz")
PY
)}"

  if ! wait_for_url "platform-gateway" "$platform_gateway_health_url" 30; then
    write_status "degraded" "platform gateway failed to become healthy during bootstrap"
    return 0
  fi
}

bootstrap_gitea() {
  log_event "info" "workspace-bootstrap.bootstrap-gitea" "phase=workspace-bootstrap action=bootstrap-gitea"

  if ! wait_for_url "gitea" "${WEBSOFT9_GITEA_HEALTH_URL:-http://127.0.0.1:3001/}" 45; then
    write_status "degraded" "gitea failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "gitea-credential" "${WEBSOFT9_GITEA_CREDENTIAL_PATH:-$data_root/gitea/credential}" 30 || true
}

bootstrap_portainer() {
  log_event "info" "workspace-bootstrap.bootstrap-portainer" "phase=workspace-bootstrap action=bootstrap-portainer"

  if ! wait_for_url "portainer" "${WEBSOFT9_PORTAINER_HEALTH_URL:-http://127.0.0.1:9004/api/system/status}" 45; then
    write_status "degraded" "portainer failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "portainer-credential" "${WEBSOFT9_PORTAINER_CREDENTIAL_PATH:-$data_root/portainer/credential}" 30 || true
}

bootstrap_nginx_proxy_manager() {
  log_event "info" "workspace-bootstrap.bootstrap-nginx-proxy-manager" "phase=workspace-bootstrap action=bootstrap-nginx-proxy-manager"

  if ! wait_for_url "nginx-proxy-manager" "${WEBSOFT9_NPM_HEALTH_URL:-http://127.0.0.1:81/}" 45; then
    write_status "degraded" "nginx-proxy-manager failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "npm-credential" "${WEBSOFT9_NPM_CREDENTIAL_PATH:-$data_root/credential.json}" 30 || true
  wait_for_file "npm-certificate" "${WEBSOFT9_NPM_CERT_MARKER:-$data_root/custom_ssl/websoft9-self-signed.cert}" 30 || true
}

monitor_runtime() {
  local last_strict_check=0

  while true; do
    if (( $(date +%s) - last_strict_check >= strict_status_interval )); then
      update_runtime_status strict || true
      last_strict_check=$(date +%s)
    else
      update_runtime_status readiness || true
    fi
    sleep "$status_interval"
  done
}

main() {
  trap shutdown_supervisor EXIT INT TERM

  ensure_data_managed_paths
  log_event "info" "runtime.start" "Starting Websoft9 converged product runtime"
  write_status "starting" "bootstrap started"
  export WEBSOFT9_PRODUCT_AUTH_CREDENTIAL_PATH="$product_auth_credential_path"
  sync_runtime_config base
  start_supervisor
  ensure_platform_network
  start_apphub_core
  bootstrap_product_auth
  bootstrap_platform_gateway
  bootstrap_gitea
  bootstrap_portainer
  bootstrap_nginx_proxy_manager
  sync_runtime_config credentials || true

  if ! update_runtime_status strict; then
    log_event "error" "runtime.bootstrap-failed" "bootstrap failed and runtime is not ready"
    exit 1
  fi

  monitor_runtime
}

main "$@"