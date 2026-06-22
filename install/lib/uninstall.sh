#!/bin/bash
# uninstall.sh — 卸载路径（§8）
# 职责：现代卸载与旧系统卸载分流，3 种模式（停用 / 标准卸载 / 彻底清理）。
# 不负责：隐式删除数据、隐式清理旧控制面遗留（必须显式开关）。
#
# 模式 (--mode)：
#   stop     仅停止运行实体，保留物料与数据
#   standard 停止并删除运行实体与部署物料，保留数据（除非 --keep-data=false 显式删数据）
#   purge    彻底清理：删除运行实体、物料、数据卷（需 --yes 确认）
# 独立开关：
#   --remove-legacy-controlplane  清理旧 Cockpit/systemd/旧容器旧卷（仅显式时执行）

# 现代卸载
_uninstall_modern() {
  local mode="$1"
  local install_path="$2"
  local keep_data="$3"
  local assume_yes="$4"
  local data_root
  data_root="$(resolve_runtime_data_root "$install_path")"

  log_info "==== Uninstall started (mode=${mode}) ===="

  # Stop / remove running entities
  case "$mode" in
    stop)
      log_step "Stopping container (keeping material and data)"
      if [ -f "${install_path}/docker-compose.yml" ]; then
        run_cmd modern_compose "$install_path" stop || true
      else
        run_cmd docker stop "$MODERN_CONTAINER_NAME" 2>/dev/null || true
      fi
      ;;
    standard|purge)
      log_step "Stopping and removing container and deployment material"
      if [ -f "${install_path}/docker-compose.yml" ]; then
        run_cmd modern_compose "$install_path" down || true
      else
        run_cmd docker rm -f "$MODERN_CONTAINER_NAME" 2>/dev/null || true
      fi
      ;;
    *) die "$EXIT_USAGE" "Unknown uninstall mode: $mode" ;;
  esac

  # Data handling
  if [ "$mode" = "purge" ]; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "purge mode touches bind-mounted data root ${data_root}, requires explicit --yes"
    fi
    die "$EXIT_USAGE" "Automatic deletion of bind-mounted data root is not supported. Remove ${data_root} manually if you really intend to purge all data."
    if [ -d "$install_path" ]; then
      run_cmd rm -f "${install_path}/docker-compose.yml" "${install_path}/.env" 2>/dev/null || true
    fi
  elif [ "$mode" = "standard" ]; then
    if [ "$keep_data" = "0" ]; then
      if [ "$assume_yes" != "1" ]; then
        die "$EXIT_USAGE" "--keep-data=false targets bind-mounted data root ${data_root}, requires explicit --yes"
      fi
      die "$EXIT_USAGE" "Automatic deletion of bind-mounted data root is not supported. Remove ${data_root} manually if you really intend to delete runtime data."
    else
      log_info "Data root retained: ${data_root}"
    fi
  fi

  log_info "Uninstall summary:"
  log_info "  Container: processed (mode=${mode})"
  log_info "  Data root ${data_root}: $([ -d "$data_root" ] && echo retained || echo missing)"
}

# 旧系统卸载（仅在显式 --remove-legacy-controlplane 或目标环境为 legacy 时）
_uninstall_legacy() {
  local mode="$1"
  local keep_data="$2"
  local assume_yes="$3"
  local remove_controlplane="$4"

  log_info "==== Legacy uninstall started (mode=${mode}) ===="

  # Stop legacy containers
  log_step "Stopping legacy containers"
  local name
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_running "$name" && run_cmd docker stop "$name" 2>/dev/null || true
  done

  if [ "$mode" = "stop" ]; then
    log_info "Stop mode: legacy containers stopped, material and data retained"
    return 0
  fi

  # 删除旧容器
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_exists "$name" && run_cmd docker rm -f "$name" 2>/dev/null || true
  done

  # 数据卷处理
  if [ "$mode" = "purge" ] || { [ "$mode" = "standard" ] && [ "$keep_data" = "0" ]; }; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "Deleting legacy data volumes requires explicit --yes"
    fi
    log_step "Deleting legacy data volumes"
    local v
    for v in "${LEGACY_VOLUME_NAMES[@]}"; do
      volume_exists "$v" && run_cmd docker volume rm "$v" 2>/dev/null || true
    done
  else
    log_info "Legacy data volumes retained (available as rollback source)"
  fi

  # Legacy control plane (Cockpit / systemd) — explicit opt-in only
  if [ "$remove_controlplane" = "1" ]; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "Removing legacy Cockpit/systemd requires explicit --yes"
    fi
    log_step "Removing legacy Cockpit / systemd control plane"
    if command_exists systemctl; then
      local unit
      for unit in "${LEGACY_SYSTEMD_UNITS[@]}"; do
        if systemd_unit_present "$unit"; then
          run_cmd systemctl stop "$unit" 2>/dev/null || true
          run_cmd systemctl disable "$unit" 2>/dev/null || true
        fi
      done
    fi
    log_warn "Cockpit packages, /etc/cockpit, and legacy install directory are not force-deleted by this script. Clean up manually if needed: ${LEGACY_INSTALL_DIR}"
  else
    log_warn "--remove-legacy-controlplane not specified; legacy Cockpit/systemd left untouched"
  fi

  log_info "Legacy uninstall summary:"
  log_info "  Legacy containers: processed (mode=${mode})"
  log_info "  Legacy volumes: $( [ "$mode" = "purge" ] && echo deleted || echo retained)"
  log_info "  Legacy control plane: $( [ "$remove_controlplane" = "1" ] && echo stopped/disabled || echo not touched )"
}

# 卸载主流程：按环境识别结果分流
run_uninstall() {
  local env_kind="$1"
  local mode="$2"
  local install_path="$3"
  local keep_data="$4"
  local assume_yes="$5"
  local remove_controlplane="$6"

  require_root

  # Resolve actual container name from the installed compose file (if present)
  local _compose_file="${install_path}/docker-compose.yml"
  MODERN_CONTAINER_NAME="$(_resolve_container_name "$_compose_file")"
  export MODERN_CONTAINER_NAME

  case "$env_kind" in
    modern)
      _uninstall_modern "$mode" "$install_path" "$keep_data" "$assume_yes"
      # 若显式要求且存在旧遗留，附带处理
      if [ "$remove_controlplane" = "1" ]; then
        _uninstall_legacy "$mode" "$keep_data" "$assume_yes" "$remove_controlplane"
      fi
      ;;
    legacy)
      _uninstall_legacy "$mode" "$keep_data" "$assume_yes" "$remove_controlplane"
      ;;
    mixed)
      die "$EXIT_ENV_GUARD" "Mixed environment detected. Please resolve manually before uninstalling."
      ;;
    empty)
      log_info "Nothing installed, nothing to uninstall"
      ;;
    *)
      die "$EXIT_ENV_GUARD" "Unknown environment, refusing to uninstall: $env_kind"
      ;;
  esac
}
