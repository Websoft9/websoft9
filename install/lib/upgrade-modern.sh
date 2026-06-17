#!/bin/bash
# upgrade-modern.sh — 新版迭代升级路径（§6）
# 职责：modern 环境的同模型升级。
# 不负责：旧卷映射、Cockpit 退场。

# 回退到升级前备份点：物料 + 主数据卷
_upgrade_modern_rollback() {
  local install_path="$1"
  local backup_dir="$2"

  log_warn "Rolling back upgrade -> $backup_dir"

  # Stop the failed new runtime
  run_cmd modern_compose "$install_path" down 2>/dev/null || true

  # Restore material
  if [ -f "${backup_dir}/.env" ]; then
    run_cmd cp -a "${backup_dir}/.env" "${install_path}/.env"
  fi
  if [ -f "${backup_dir}/docker-compose.yml" ]; then
    run_cmd cp -a "${backup_dir}/docker-compose.yml" "${install_path}/docker-compose.yml"
  fi

  # Restore data volume
  restore_volume "$MODERN_DATA_VOLUME" "$backup_dir" || log_warn "Data volume rollback failed, check backup manually: $backup_dir"

  # Restart old runtime
  run_cmd modern_compose "$install_path" up -d || log_error "Failed to restart old runtime after rollback"
}

# 迭代升级主流程
run_upgrade_modern() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"
  local volumes_root="$6"

  log_info "==== Upgrade started ===="

  require_root
  if [ ! -f "${install_path}/docker-compose.yml" ]; then
    die "$EXIT_RUNTIME" "Existing deployment material not found: ${install_path}/docker-compose.yml"
  fi

  # Resolve actual container name from the existing compose file
  MODERN_CONTAINER_NAME="$(_resolve_container_name "${install_path}/docker-compose.yml")"
  export MODERN_CONTAINER_NAME

  # 1. Record current state
  local current_image=""
  if container_exists "$MODERN_CONTAINER_NAME"; then
    current_image="$(docker inspect --format '{{.Config.Image}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
  fi
  log_info "Current image: ${current_image:-unknown}"

  # 2. 升级前强制备份（不受 --keep-data 影响）
  local backup_dir
  backup_dir="$(backup_new_dir modern-upgrade)"
  backup_modern_pre_upgrade "$install_path" "$backup_dir"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) pre-upgrade checks done, stopping before material switch"
    return 0
  fi

  # 3. Switch material: update compose + .env, pull new image
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port" "$volumes_root"
  if ! modern_compose "$install_path" pull; then
    log_error "Failed to pull new image, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "Upgrade failed (image pull)"
  fi

  # 4. Start new container
  if ! modern_compose "$install_path" up -d; then
    log_error "Failed to start new container, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "Upgrade failed (container start)"
  fi

  # 5. Post-upgrade validation
  if ! validate_upgrade "$console_port"; then
    log_error "Post-upgrade validation failed, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_VALIDATE" "Upgrade failed (post-upgrade validation)"
  fi

  log_info "==== Upgrade successful ===="
  log_info "Pre-upgrade backup retained at: $backup_dir"
}
