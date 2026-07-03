#!/bin/bash
# upgrade-modern.sh — 新版迭代升级路径（§6）
# 职责：modern 环境的同模型升级。
# 不负责：旧卷映射、Cockpit 退场。

_export_modern_runtime_config_to_data_root() {
  local install_path="$1"
  local fallback_root="$2"
  local data_root

  # Resolve the host-side data root from the running container's actual
  # bind mount rather than trusting the env file — this guarantees the
  # exported files land under the same host directory the next container
  # startup will mount, even when the env file is stale or mismatched.
  for dest in /opt/websoft9/data /data; do
    data_root="$(docker inspect --format '{{range .Mounts}}{{if and (eq .Type "bind") (eq .Destination "'"$dest"'")}}{{.Source}}{{end}}{{end}}' "$MODERN_CONTAINER_NAME" 2>/dev/null | head -n1)"
    if [ -n "$data_root" ]; then
      break
    fi
  done
  data_root="${data_root:-$fallback_root}"

  local runtime_config_dir="${data_root%/}/config/apphub"
  local runtime_config_path="${runtime_config_dir}/config.ini"
  local runtime_system_config_path="${runtime_config_dir}/system.ini"

  log_info "Exporting runtime config to: $runtime_config_dir (host data root: ${data_root})"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) would export runtime config into: $runtime_config_dir"
    return 0
  fi

  container_running "$MODERN_CONTAINER_NAME" || return 0

  run_cmd mkdir -p "$runtime_config_dir"

  if docker exec "$MODERN_CONTAINER_NAME" sh -lc 'cat "${WEBSOFT9_APPHUB_CONFIG_PATH:-/websoft9/apphub/src/config/config.ini}"' >"$runtime_config_path" 2>/dev/null; then
    log_info "Exported runtime config to: $runtime_config_path"
  else
    log_warn "Failed to export runtime config from the current container"
  fi

  if docker exec "$MODERN_CONTAINER_NAME" sh -lc 'cat "${WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH:-/websoft9/apphub/src/config/system.ini}"' >"$runtime_system_config_path" 2>/dev/null; then
    log_info "Exported runtime system config to: $runtime_system_config_path"
  else
    log_warn "Failed to export runtime system config from the current container"
  fi
}

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

  # Restore data root
  restore_host_directory "$(resolve_runtime_data_root "$install_path")" modern-data-root.tar.gz "$backup_dir" || log_warn "Data root rollback failed, check backup manually: $backup_dir"

  # Restart old runtime
  run_cmd modern_compose "$install_path" up -d || log_error "Failed to restart old runtime after rollback"
}

# 迭代升级主流程
run_upgrade_modern() {
  local console_port="$1"
  local install_path="$2"
  local image_tag="$3"

  log_info "==== Upgrade started ===="

  require_root
  if [ ! -f "${install_path}/docker-compose.yml" ]; then
    if _detect_modern_data_root; then
      log_warn "Existing deployment material not found: ${install_path}/docker-compose.yml"
      log_warn "Modern data root markers exist; continuing in recovery mode and recreating deployment material"
      run_cmd mkdir -p "$install_path"
    else
      die "$EXIT_RUNTIME" "Existing deployment material not found: ${install_path}/docker-compose.yml"
    fi
  fi

  # Derive container name from channel (keep instances isolated)
  case "${W9_CHANNEL:-release}" in
    dev)  CONTAINER_NAME="websoft9-dev" ;;
    rc)   CONTAINER_NAME="websoft9-rc" ;;
    *)    CONTAINER_NAME="websoft9" ;;
  esac
  export CONTAINER_NAME
  MODERN_CONTAINER_NAME="$(_resolve_container_name "${install_path}/docker-compose.yml")"
  export MODERN_CONTAINER_NAME
  WEBSOFT9_DATA_ROOT="$(resolve_existing_runtime_data_root "$install_path")"
  export WEBSOFT9_DATA_ROOT
  log_info "Upgrade data root resolved to: ${WEBSOFT9_DATA_ROOT}"

  # 1. Record current state
  local current_image=""
  if container_exists "$MODERN_CONTAINER_NAME"; then
    current_image="$(docker inspect --format '{{.Config.Image}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
  fi
  log_info "Current image: ${current_image:-unknown}"

  # Preserve the live runtime settings before the first upgrade switches the
  # config model from container-local files to data-root-backed files.
  _export_modern_runtime_config_to_data_root "$install_path" "$WEBSOFT9_DATA_ROOT"

  # 2. 升级前强制备份（不受 --keep-data 影响）
  local backup_dir
  backup_dir="$(backup_new_dir modern-upgrade)"
  backup_modern_pre_upgrade "$install_path" "$backup_dir"

  # 3. Migrate legacy /data to the canonical /opt/websoft9/data.
  #    Must happen AFTER the backup above so the backup captures the
  #    original /data before it is moved.
  if [ "$WEBSOFT9_DATA_ROOT" = "/data" ]; then
    log_step "Migrating data root from /data to /opt/websoft9/data"
    if [ -d /data ] && [ ! -d /opt/websoft9/data ]; then
      run_cmd mkdir -p /opt/websoft9
      run_cmd cp -a /data /opt/websoft9/data || die "$EXIT_RUNTIME" "Failed to copy data from /data to /opt/websoft9/data"
      run_cmd rm -rf /data || log_warn "Could not remove old /data after migration; you may delete it manually"
      log_info "Data root migrated to /opt/websoft9/data"
    elif [ -d /opt/websoft9/data ]; then
      log_warn "/opt/websoft9/data already exists; keeping existing data and switching to new root"
    else
      log_warn "/data does not exist; switching data root to /opt/websoft9/data"
    fi
    WEBSOFT9_DATA_ROOT="/opt/websoft9/data"
    export WEBSOFT9_DATA_ROOT
    log_info "Upgrade data root changed to: ${WEBSOFT9_DATA_ROOT}"
  fi

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) pre-upgrade checks done, stopping before material switch"
    return 0
  fi

  # 3. Switch material: update compose + .env, pull new image
  install_prepare_material "$install_path" "$image_tag" "$console_port"
  if ! pull_image_with_mirrors "$install_path"; then
    log_error "Failed to pull new image, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "Upgrade failed (image pull)"
  fi

  # 4. Stop the old runtime before starting the new one.
  #    Explicit down ensures ports (80/443/console) are released, avoiding
  #    "port is already allocated" when docker compose up -d races with the
  #    old container shutdown.
  log_step "Stopping current runtime before switching to the new image"
  if ! modern_compose "$install_path" down; then
    log_warn "Failed to gracefully stop current runtime; forcing removal"
    docker rm -f "$MODERN_CONTAINER_NAME" 2>/dev/null || true
  fi

  # 5. Start new container
  if ! modern_compose "$install_path" up -d; then
    log_error "Failed to start new container, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "Upgrade failed (container start)"
  fi

  # 6. Post-upgrade validation
  if ! validate_upgrade "$console_port"; then
    log_error "Post-upgrade validation failed, rolling back"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_VALIDATE" "Upgrade failed (post-upgrade validation)"
  fi

  log_info "==== Upgrade successful ===="
  print_runtime_summary upgrade "$install_path" "$console_port" "$backup_dir"
}
