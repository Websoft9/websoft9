#!/bin/bash
# validate.sh — validation layer (health check, console, API, data, product state)

# Wait for container to become running and healthy, printing a dot every interval
validate_container_health() {
  local timeout="${1:-180}"
  local waited=0 interval=5
  log_step "Checking container health: $MODERN_CONTAINER_NAME (timeout ${timeout}s)"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping container health wait"
    return 0
  fi

  printf "[Websoft9] Waiting"
  while [ "$waited" -lt "$timeout" ]; do
    if container_running "$MODERN_CONTAINER_NAME"; then
      local health
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
      case "$health" in
        healthy)
          printf "\n"
          log_info "Container health check passed (healthy)"
          return 0
          ;;
        none)
          printf "\n"
          log_info "Container is running (no healthcheck defined, treating as ready)"
          return 0
          ;;
        *)
          : ;;  # starting / unhealthy — keep waiting
      esac
    fi
    printf "."
    sleep "$interval"
    waited=$((waited + interval))
  done
  printf "\n"
  log_error "Container did not reach healthy state within ${timeout}s"
  return 1
}

# Check that the console port is reachable
validate_console_entry() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  log_step "Checking console entry: 127.0.0.1:${console_port}"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping console probe"
    return 0
  fi
  local i
  for i in $(seq 1 30); do
    if curl -fs -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/" \
       || curl -fs -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/api"; then
      log_info "Console entry reachable"
      return 0
    fi
    sleep 3
  done
  log_error "Console entry ${console_port} not reachable"
  return 1
}

# Check that the product API root path responds
validate_api() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  log_step "Checking product API: /api"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping API probe"
    return 0
  fi
  local i
  for i in $(seq 1 30); do
    if curl -fs -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/api"; then
      log_info "Product API root reachable"
      return 0
    fi
    sleep 3
  done
  log_error "Product API root not reachable"
  return 1
}

# Check that the main data volume exists and the key subtree is readable
validate_data_root() {
  log_step "Checking data volume: ${MODERN_DATA_VOLUME}:${MODERN_DATA_MOUNT}"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping data root check"
    return 0
  fi
  if ! volume_exists "$MODERN_DATA_VOLUME"; then
    log_error "Data volume not found: $MODERN_DATA_VOLUME"
    return 1
  fi
  if container_running "$MODERN_CONTAINER_NAME"; then
    if docker exec "$MODERN_CONTAINER_NAME" sh -c '[ -d /data/config ]' >/dev/null 2>&1; then
      log_info "Data root ready and key subtree readable"
      return 0
    fi
  fi
  log_warn "Data root key subtree not yet ready (may still be initializing)"
  return 1
}

# Check product runtime state (version / edition)
validate_product_state() {
  log_step "Checking product runtime state"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping product state check"
    return 0
  fi
  if ! container_running "$MODERN_CONTAINER_NAME"; then
    log_error "Container not running, cannot check product state"
    return 1
  fi
  local out
  out="$(docker exec "$MODERN_CONTAINER_NAME" python3 -c \
    'import sys; sys.path.insert(0, "/websoft9/apphub"); from src.services.product_metadata import read_product_metadata; m=read_product_metadata(); print(m.get("version"), m.get("edition_key"), m.get("state_source"))' 2>/dev/null)"
  if [ -n "$out" ]; then
    log_info "Product runtime state: ${out}"
    return 0
  fi
  log_warn "Could not read product runtime state"
  return 1
}

# Minimum post-install acceptance checks
validate_install() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  local rc=0
  validate_container_health 180 || rc=1
  validate_console_entry "$console_port" || rc=1
  validate_api "$console_port" || rc=1
  validate_product_state || rc=1
  return $rc
}

# Post-upgrade acceptance checks
validate_upgrade() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  local rc=0
  validate_container_health 240 || rc=1
  validate_console_entry "$console_port" || rc=1
  validate_api "$console_port" || rc=1
  validate_product_state || rc=1
  return $rc
}

