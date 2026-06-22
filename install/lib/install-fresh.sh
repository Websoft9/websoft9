#!/bin/bash
# install-fresh.sh (lib) — fresh installation path

# Pre-flight checks: Docker, ports, install path
install_precheck() {
  local console_port="$1"
  local install_path="$2"

  log_step "Pre-flight checks"

  require_root

  # Docker / compose
  if ! docker_available; then
    log_warn "Docker not found, attempting automatic installation"
    if [ "${W9_DRY_RUN:-0}" = "1" ]; then
      log_info "(dry-run) skipping Docker installation"
    else
      ensure_docker_installed || die "$EXIT_PRECHECK" "Docker installation failed"
    fi
  fi
  if [ "${W9_DRY_RUN:-0}" != "1" ] && ! compose_available; then
    die "$EXIT_PRECHECK" "docker compose plugin not available"
  fi

  # Port availability (console + HTTP/HTTPS)
  local p
  for p in "$console_port" 80 443; do
    if port_in_use "$p"; then
      die "$EXIT_PRECHECK" "Port already in use: $p"
    fi
  done

  # Install directory writable
  if [ "${W9_DRY_RUN:-0}" != "1" ]; then
    mkdir -p "$install_path" || die "$EXIT_PRECHECK" "Cannot create install directory: $install_path"
    [ -w "$install_path" ] || die "$EXIT_PRECHECK" "Install directory not writable: $install_path"
  fi

  log_info "Pre-flight checks passed"
}

# 物料准备：compose 文件 + .env + 安装目录
install_prepare_material() {
  local install_path="$1"
  local image_repo="$2"
  local image_tag="$3"
  local network_name="$4"
  local console_port="$5"

  log_step "Preparing deployment material"
  ensure_deployment_material "$install_path" "${W9_CHANNEL:-release}"
  ensure_shared_network "$network_name" || die "$EXIT_RUNTIME" "Failed to prepare shared Docker network: $network_name"
  write_env_file "${install_path}/.env" "$image_repo" "$image_tag" "$network_name" "$console_port"
  log_info "Deployment material and .env ready"
}

# Pull image and start container
install_start() {
  local install_path="$1"
  log_step "Pulling image"
  pull_image_with_mirrors "$install_path" || die "$EXIT_RUNTIME" "Failed to pull image"
  log_step "Starting container"
  run_cmd modern_compose "$install_path" up -d || die "$EXIT_RUNTIME" "Failed to start container"
}

# Rollback on post-install validation failure
install_cleanup_on_failure() {
  local install_path="$1"
  log_warn "Post-install validation failed, cleaning up"
  run_cmd modern_compose "$install_path" down 2>/dev/null || true
}

# Fresh install main flow
run_install() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"

  log_info "==== Installation started ===="

  # Derive container name from channel (keep instances isolated)
  case "${W9_CHANNEL:-release}" in
    dev)  CONTAINER_NAME="websoft9-dev" ;;
    rc)   CONTAINER_NAME="websoft9-rc" ;;
    *)    CONTAINER_NAME="websoft9" ;;
  esac
  export CONTAINER_NAME

  install_precheck "$console_port" "$install_path"
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port"

  # Sync the global constant for downstream health checks etc.
  MODERN_CONTAINER_NAME="$CONTAINER_NAME"
  export MODERN_CONTAINER_NAME

  install_start "$install_path"

  if ! validate_install "$console_port"; then
    install_cleanup_on_failure "$install_path"
    die "$EXIT_VALIDATE" "Installation validation failed"
  fi

  log_info "==== Installation successful ===="
  log_info "Console: http://<host>:${console_port}"
}
