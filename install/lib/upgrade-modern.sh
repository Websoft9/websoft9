#!/bin/bash
# upgrade-modern.sh — 新版迭代升级路径（§6）
# 职责：modern 环境的同模型升级。
# 不负责：旧卷映射、Cockpit 退场。

_export_modern_runtime_config_to_data_root() {
  local install_path="$1"
  local fallback_root="$2"

  # Select the host-side data root: prefer the canonical path when the
  # directory tree already exists, otherwise fall back to the resolved
  # value from the .env file.
  local data_root="${fallback_root}"
  for candidate in /opt/websoft9/data /data; do
    if [ -d "$candidate" ] && [ -d "${candidate}/config" ]; then
      data_root="$candidate"
      break
    fi
  done

  local runtime_config_path="${data_root%/}/config/apphub/config.ini"
  local runtime_system_config_path="${data_root%/}/config/apphub/system.ini"

  # Once the persistent config exists on the host it naturally survives
  # container recreations through the bind mount — no export is needed.
  # This path only runs once, during the very first upgrade from the old
  # container-local config model to the data-root-backed persistent model.
  if [ -f "$runtime_config_path" ] && [ -f "$runtime_system_config_path" ]; then
    log_info "Persistent runtime config already present, skipping export"
    return 0
  fi

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) would export runtime config from container into ${runtime_config_path}"
    return 0
  fi

  run_cmd mkdir -p "$(dirname "$runtime_config_path")"

  # Prefer a running container, but a stopped container can still provide its
  # configuration through docker cp during recovery upgrades.
  if container_running "$MODERN_CONTAINER_NAME"; then
    log_step "Migrating runtime config from running container to persistent host storage"
    docker exec "$MODERN_CONTAINER_NAME" sh -lc '
      for p in /opt/websoft9/data/config/apphub/config.ini /websoft9/apphub/src/config/config.ini; do
        if [ -s "$p" ]; then cat "$p"; break; fi
      done
    ' >"$runtime_config_path" 2>/dev/null || true

    docker exec "$MODERN_CONTAINER_NAME" sh -lc '
      for p in /opt/websoft9/data/config/apphub/system.ini /websoft9/apphub/src/config/system.ini; do
        if [ -s "$p" ]; then cat "$p"; break; fi
      done
    ' >"$runtime_system_config_path" 2>/dev/null || true
  elif container_exists "$MODERN_CONTAINER_NAME"; then
    log_step "Container is stopped; migrating runtime config with docker cp"
    local source_path
    for source_path in /opt/websoft9/data/config/apphub/config.ini /websoft9/apphub/src/config/config.ini; do
      docker cp "$MODERN_CONTAINER_NAME:$source_path" "$runtime_config_path" 2>/dev/null && [ -s "$runtime_config_path" ] && break
    done
    for source_path in /opt/websoft9/data/config/apphub/system.ini /websoft9/apphub/src/config/system.ini; do
      docker cp "$MODERN_CONTAINER_NAME:$source_path" "$runtime_system_config_path" 2>/dev/null && [ -s "$runtime_system_config_path" ] && break
    done
  fi

  [ -s "$runtime_config_path" ] || log_warn "Failed to export runtime config; new runtime will use the available persistent or image defaults"
  [ -s "$runtime_system_config_path" ] || log_warn "Failed to export runtime system config; new runtime will use the available persistent or image defaults"
}

# 回退到升级前备份点：物料 + 主数据卷
_upgrade_modern_rollback() {
  local install_path="$1"
  local backup_dir="$2"

  log_warn "Rolling back upgrade -> $backup_dir"

  # Stop the failed new runtime
  run_cmd modern_compose "$install_path" down 2>/dev/null || true

  # Restore material
  local _material_restored=0
  if [ -f "${backup_dir}/.env" ]; then
    run_cmd cp -a "${backup_dir}/.env" "${install_path}/.env"
    _material_restored=1
  fi
  if [ -f "${backup_dir}/docker-compose.yml" ]; then
    run_cmd cp -a "${backup_dir}/docker-compose.yml" "${install_path}/docker-compose.yml"
    _material_restored=1
  fi

  # Restore data root
  restore_host_directory "$(resolve_runtime_data_root "$install_path")" modern-data-root.tar.gz "$backup_dir" || log_warn "Data root rollback failed, check backup manually: $backup_dir"
  report_user_app_volumes "$backup_dir"

  # Restart old runtime (only if deployment material was restored)
  if [ "$_material_restored" -eq 1 ]; then
    run_cmd modern_compose "$install_path" up -d || log_error "Failed to restart old runtime after rollback"
  else
    log_error "Backup does not contain deployment material; cannot restart old runtime"
    log_error "Backup point: $backup_dir — restore manually if needed"
  fi
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

  # Detect the actual container from the live system.
  # The running container may use a different channel than the target
  # (e.g. a dev install upgraded via the release install.sh).
  # We detect the old container name for pre-switch operations
  # (config export, state recording, shutdown) but do NOT change
  # W9_CHANNEL — the compose file and .env must reflect the target channel.
  local _detected_name
  _detected_name="$(_detect_websoft9_container)"
  if [ -n "$_detected_name" ]; then
    MODERN_CONTAINER_NAME="$_detected_name"
    log_info "Detected existing container: ${MODERN_CONTAINER_NAME}"
  else
    MODERN_CONTAINER_NAME="$(resolve_container_name_by_channel "${W9_CHANNEL:-release}")"
  fi
  export MODERN_CONTAINER_NAME

  # Resolve the target container name from the script's channel.
  # This is used for the new .env and deployment; the target channel
  # (set by install.sh, always "release" for release artifacts) is
  # never overwritten by container detection.
  CONTAINER_NAME="$(resolve_container_name_by_channel "${W9_CHANNEL:-release}")"
  export CONTAINER_NAME
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

  # 3. Copy legacy /data to the canonical /opt/websoft9/data. The source
  #    directory is retained because it may be a user-owned data mount.
  #    The backup above captures the original data before this copy.
  if [ "$WEBSOFT9_DATA_ROOT" = "/data" ]; then
    log_step "Migrating data root from /data to /opt/websoft9/data"
    if [ -d /data ] && [ ! -d /opt/websoft9/data ]; then
      run_cmd mkdir -p /opt/websoft9
      run_cmd cp -a /data /opt/websoft9/data || die "$EXIT_RUNTIME" "Failed to copy data from /data to /opt/websoft9/data"
      log_info "Data root copied to /opt/websoft9/data; source /data was retained"
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
  log_step "Stopping current runtime before switching to the new image"
  modern_compose "$install_path" down 2>/dev/null || true
  if container_exists "$MODERN_CONTAINER_NAME"; then
    log_warn "Container ${MODERN_CONTAINER_NAME} still exists after compose down; forcing removal"
    docker rm -f "$MODERN_CONTAINER_NAME" 2>/dev/null || true
  fi

  # docker-proxy may take a moment to release ports after the container
  # is removed.  Wait until ports are actually free before starting the
  # new container, otherwise docker compose up -d will fail with
  # "port is already allocated".
  log_step "Waiting for ports to be released"
  local _port _wait_ok _waited _blocked_ports=()
  _waited=0
  while [ "$_waited" -lt 30 ]; do
    _wait_ok=1
    _blocked_ports=()
    for _port in 80 443 "$console_port"; do
      if port_in_use "$_port"; then
        _wait_ok=0
        _blocked_ports+=("$_port")
      fi
    done
    [ "$_wait_ok" = "1" ] && break
    sleep 1
    _waited=$((_waited + 1))
  done
  if [ "$_wait_ok" != "1" ]; then
    log_error "Required ports are still in use after ${_waited}s: ${_blocked_ports[*]}"
    log_error "No processes were terminated. Stop the conflicting service and retry the upgrade."
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "Required ports are held by another service"
  fi

  # Switch to the target container name now that the old runtime is stopped.
  MODERN_CONTAINER_NAME="$CONTAINER_NAME"
  export MODERN_CONTAINER_NAME

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
