#!/usr/bin/env bash

set -euo pipefail

runtime_state_dir="${WEBSOFT9_RUNTIME_STATE_DIR:-/run/websoft9}"
runtime_status_file="${WEBSOFT9_RUNTIME_STATUS_FILE:-$runtime_state_dir/runtime-status.json}"
supervisor_config="${WEBSOFT9_SUPERVISOR_CONFIG:-/etc/supervisor/conf.d/websoft9-platform.conf}"
supervisor_socket="${WEBSOFT9_SUPERVISOR_SOCKET:-/run/supervisor.sock}"
status_interval="${WEBSOFT9_STATUS_INTERVAL:-60}"
strict_status_interval="${WEBSOFT9_STRICT_STATUS_INTERVAL:-1800}"
platform_network_name="${WEBSOFT9_PLATFORM_NETWORK_NAME:-websoft9}"
platform_container_ref="${WEBSOFT9_PLATFORM_CONTAINER_REF:-${HOSTNAME:-}}"
docker_socket_path="${WEBSOFT9_DOCKER_SOCKET_PATH:-/var/run/docker.sock}"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [platform-entrypoint] $*"
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
      log "phase=wait name=$name result=ready url=$url status=$status_code"
      return 0
    fi

    if (( $(date +%s) - started_at >= timeout_seconds )); then
      log "phase=wait name=$name result=timeout url=$url status=$status_code"
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
      log "phase=wait name=$name result=ready path=$path"
      return 0
    fi

    if (( $(date +%s) - started_at >= timeout_seconds )); then
      log "phase=wait name=$name result=timeout path=$path"
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
  log "phase=runtime-network action=ensure name=$platform_network_name"

  if [[ ! -S "$docker_socket_path" ]]; then
    log "phase=runtime-network result=skip reason=docker-socket-unavailable path=$docker_socket_path"
    return 0
  fi

  local network_response
  local network_status
  network_response="$(docker_api_request GET "/networks/$platform_network_name")"
  network_status="$(docker_api_status "$network_response")"

  if [[ "$network_status" == "404" ]]; then
    docker_api_request POST "/networks/create" "{\"Name\":\"$platform_network_name\",\"Driver\":\"bridge\"}" >/dev/null
    log "phase=runtime-network result=created name=$platform_network_name"
  elif [[ "$network_status" != "200" ]]; then
    log "phase=runtime-network result=skip reason=network-inspect-failed status=$network_status"
    return 0
  else
    log "phase=runtime-network result=exists name=$platform_network_name"
  fi

  if [[ -z "$platform_container_ref" ]]; then
    log "phase=runtime-network result=skip-connect reason=missing-container-ref"
    return 0
  fi

  local container_response
  local container_status
  local container_body
  container_response="$(docker_api_request GET "/containers/$platform_container_ref/json")"
  container_status="$(docker_api_status "$container_response")"
  container_body="$(docker_api_body "$container_response")"

  if [[ "$container_status" == "404" ]]; then
    log "phase=runtime-network result=skip-connect reason=container-not-found ref=$platform_container_ref"
    return 0
  elif [[ "$container_status" != "200" ]]; then
    log "phase=runtime-network result=skip-connect reason=container-inspect-failed status=$container_status ref=$platform_container_ref"
    return 0
  fi

  if printf '%s' "$container_body" | grep -Fq "\"$platform_network_name\":{"; then
    log "phase=runtime-network result=attached name=$platform_network_name ref=$platform_container_ref"
    return 0
  fi

  docker_api_request POST "/networks/$platform_network_name/connect" "{\"Container\":\"$platform_container_ref\"}" >/dev/null
  log "phase=runtime-network result=connected name=$platform_network_name ref=$platform_container_ref"
}

shutdown_supervisor() {
  if [[ -S "$supervisor_socket" ]]; then
    supervisorctl -c "$supervisor_config" shutdown >/dev/null 2>&1 || true
  fi
}

start_supervisor() {
  log "phase=core-bootstrap action=start-supervisor"

  mkdir -p "$runtime_state_dir"
  supervisord -c "$supervisor_config"
  wait_for_file "supervisor-socket" "$supervisor_socket" 30
}

start_apphub_core() {
  log "phase=core-bootstrap action=start-apphub-core"

  wait_for_url "apphub-api" "${WEBSOFT9_APPHUB_HEALTH_URL:-http://127.0.0.1:8080/api/healthz}" 60
  wait_for_url "apphub-media" "${WEBSOFT9_MEDIA_HEALTH_URL:-http://127.0.0.1:8081/healthz}" 60
}

bootstrap_gitea() {
  log "phase=workspace-bootstrap action=bootstrap-gitea"

  if ! wait_for_url "gitea" "${WEBSOFT9_GITEA_HEALTH_URL:-http://127.0.0.1:3000/}" 45; then
    write_status "degraded" "gitea failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "gitea-credential" "${WEBSOFT9_GITEA_CREDENTIAL_PATH:-/data/gitea/credential}" 30 || true
}

bootstrap_portainer() {
  log "phase=workspace-bootstrap action=bootstrap-portainer"

  if ! wait_for_url "portainer" "${WEBSOFT9_PORTAINER_HEALTH_URL:-https://127.0.0.1:9443/api/system/status}" 45; then
    write_status "degraded" "portainer failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "portainer-credential" "${WEBSOFT9_PORTAINER_CREDENTIAL_PATH:-/data/portainer/credential}" 30 || true
}

bootstrap_nginx_proxy_manager() {
  log "phase=workspace-bootstrap action=bootstrap-nginx-proxy-manager"

  if ! wait_for_url "nginx-proxy-manager" "${WEBSOFT9_NPM_HEALTH_URL:-http://127.0.0.1:81/}" 45; then
    write_status "degraded" "nginx-proxy-manager failed to become healthy during bootstrap"
    return 0
  fi

  wait_for_file "npm-credential" "${WEBSOFT9_NPM_CREDENTIAL_PATH:-/data/credential.json}" 30 || true
  wait_for_file "npm-certificate" "${WEBSOFT9_NPM_CERT_MARKER:-/data/custom_ssl/websoft9-self-signed.cert}" 30 || true
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

  log "Starting Websoft9 converged product runtime"
  write_status "starting" "bootstrap started"
  sync_runtime_config base
  start_supervisor
  ensure_platform_network
  start_apphub_core
  bootstrap_gitea
  bootstrap_portainer
  bootstrap_nginx_proxy_manager
  sync_runtime_config credentials || true

  if ! update_runtime_status strict; then
    log "bootstrap failed and runtime is not ready"
    exit 1
  fi

  monitor_runtime
}

main "$@"