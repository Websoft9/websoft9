#!/usr/bin/env bash

set -euo pipefail

runtime_state_dir="${WEBSOFT9_RUNTIME_STATE_DIR:-/run/websoft9}"
runtime_status_file="${WEBSOFT9_RUNTIME_STATUS_FILE:-$runtime_state_dir/runtime-status.json}"
supervisor_config="${WEBSOFT9_SUPERVISOR_CONFIG:-/etc/supervisor/conf.d/websoft9-platform.conf}"
supervisor_socket="${WEBSOFT9_SUPERVISOR_SOCKET:-/run/supervisor.sock}"
status_interval="${WEBSOFT9_STATUS_INTERVAL:-15}"
platform_runtime_log_path="${WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH:-/var/log/websoft9/platform-runtime.log}"
product_auth_credential_path="${WEBSOFT9_PRODUCT_AUTH_CREDENTIAL_PATH:-/data/product-auth/credential.json}"
product_auth_bootstrap_username="${WEBSOFT9_PRODUCT_AUTH_BOOTSTRAP_USERNAME:-websoft9}"
product_auth_bootstrap_display_name="${WEBSOFT9_PRODUCT_AUTH_BOOTSTRAP_DISPLAY_NAME:-Websoft9 User}"
service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-/var/log/websoft9}"

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

generate_password() {
  openssl rand -base64 18 | tr -dc 'A-Za-z0-9@#%+=' | head -c 16
}

load_or_create_product_auth_credentials() {
  if [[ -f "$product_auth_credential_path" ]]; then
    read -r product_auth_bootstrap_username product_auth_bootstrap_display_name product_auth_bootstrap_password < <(
      jq -r '.username + "\t" + (.display_name // "Websoft9 User") + "\t" + .password' "$product_auth_credential_path"
    )
    return
  fi

  product_auth_bootstrap_password="$(generate_password)"
  mkdir -p "$(dirname "$product_auth_credential_path")"
  cat >"$product_auth_credential_path" <<EOF
{"username":"$product_auth_bootstrap_username","display_name":"$product_auth_bootstrap_display_name","password":"$product_auth_bootstrap_password"}
EOF
  chmod 600 "$product_auth_credential_path"
}

sync_runtime_config() {
  local mode="$1"

  /websoft9/script/platform-sync-config.sh --mode "$mode"
}

ensure_runtime_assets() {
  /websoft9/script/platform-sync-runtime-assets.py
}

update_runtime_status() {
  local output

  if output="$(/websoft9/script/platform-healthcheck.sh --strict 2>&1)"; then
    write_status "ready" "$output"
    return 0
  fi

  if output="$(/websoft9/script/platform-healthcheck.sh --readiness 2>&1)"; then
    write_status "degraded" "$output"
    return 0
  fi

  write_status "failed" "$output"
  return 1
}

ensure_service_log_roots() {
  mkdir -p "$service_log_root/gitea" "$service_log_root/portainer"

  if [[ -d /data/logs && ! -e "$service_log_root/nginx-proxy-manager" ]]; then
    ln -s /data/logs "$service_log_root/nginx-proxy-manager"
  fi
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

  load_or_create_product_auth_credentials
  local output
  output="$(python3 - <<'PY'
import json
import os
import sys

sys.path.insert(0, "/websoft9/apphub")

from src.services.product_auth import ProductAuthService

credential_path = os.environ["WEBSOFT9_PRODUCT_AUTH_CREDENTIAL_PATH"]
with open(credential_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

operator, created = ProductAuthService().bootstrap_operator_if_missing(
    username=payload["username"],
    password=payload["password"],
    display_name=payload.get("display_name") or "Websoft9 User",
    client_host="127.0.0.1",
    user_agent="platform-entrypoint",
)

state = "created" if created else "reused"
print(f"product_auth_bootstrap={state} username={operator['username']}")
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

  wait_for_file "gitea-credential" "${WEBSOFT9_GITEA_CREDENTIAL_PATH:-/data/gitea/credential}" 30 || true
}

bootstrap_portainer() {
  log_event "info" "workspace-bootstrap.bootstrap-portainer" "phase=workspace-bootstrap action=bootstrap-portainer"

  if ! wait_for_url "portainer" "${WEBSOFT9_PORTAINER_HEALTH_URL:-http://127.0.0.1:9004/api/system/status}" 45; then
    write_status "degraded" "portainer failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "portainer-credential" "${WEBSOFT9_PORTAINER_CREDENTIAL_PATH:-/data/portainer/credential}" 30 || true
}

bootstrap_nginx_proxy_manager() {
  log_event "info" "workspace-bootstrap.bootstrap-nginx-proxy-manager" "phase=workspace-bootstrap action=bootstrap-nginx-proxy-manager"

  if ! wait_for_url "nginx-proxy-manager" "${WEBSOFT9_NPM_HEALTH_URL:-http://127.0.0.1:81/}" 45; then
    write_status "degraded" "nginx-proxy-manager failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "npm-credential" "${WEBSOFT9_NPM_CREDENTIAL_PATH:-/data/nginx-proxy-manager/credential.json}" 30 || true
  wait_for_file "npm-certificate" "${WEBSOFT9_NPM_CERT_MARKER:-/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert}" 30 || true
}

monitor_runtime() {
  while true; do
    update_runtime_status || true
    sync_runtime_config credentials || true
    sleep "$status_interval"
  done
}

main() {
  trap shutdown_supervisor EXIT INT TERM

  log_event "info" "runtime.start" "Starting Websoft9 converged product runtime"
  write_status "starting" "bootstrap started"
  export WEBSOFT9_PRODUCT_AUTH_CREDENTIAL_PATH="$product_auth_credential_path"
  ensure_runtime_assets
  sync_runtime_config base
  start_supervisor
  start_apphub_core
  bootstrap_product_auth
  bootstrap_platform_gateway
  bootstrap_gitea
  bootstrap_portainer
  bootstrap_nginx_proxy_manager
  sync_runtime_config credentials || true

  if ! update_runtime_status; then
    log_event "error" "runtime.bootstrap-failed" "bootstrap failed and runtime is not ready"
    exit 1
  fi

  monitor_runtime
}

main "$@"