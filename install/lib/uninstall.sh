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

  log_info "==== 现代卸载 (mode=${mode}) ===="

  # 停止/删除运行实体
  case "$mode" in
    stop)
      log_step "停止现代容器（保留物料与数据）"
      if [ -f "${install_path}/docker-compose.yml" ]; then
        run_cmd modern_compose "$install_path" stop || true
      else
        run_cmd docker stop "$MODERN_CONTAINER_NAME" 2>/dev/null || true
      fi
      ;;
    standard|purge)
      log_step "停止并删除现代容器与部署物料"
      if [ -f "${install_path}/docker-compose.yml" ]; then
        run_cmd modern_compose "$install_path" down || true
      else
        run_cmd docker rm -f "$MODERN_CONTAINER_NAME" 2>/dev/null || true
      fi
      ;;
    *) die "$EXIT_USAGE" "未知卸载模式: $mode" ;;
  esac

  # 数据处理
  if [ "$mode" = "purge" ]; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "purge 模式将删除数据卷 ${MODERN_DATA_VOLUME}，需显式 --yes 确认"
    fi
    log_step "彻底清理：删除主数据卷 ${MODERN_DATA_VOLUME}"
    run_cmd docker volume rm "$MODERN_DATA_VOLUME" 2>/dev/null || log_warn "删除数据卷失败或不存在"
    # 删除安装目录物料
    if [ -d "$install_path" ]; then
      run_cmd rm -f "${install_path}/docker-compose.yml" "${install_path}/.env" 2>/dev/null || true
    fi
  elif [ "$mode" = "standard" ]; then
    if [ "$keep_data" = "0" ]; then
      if [ "$assume_yes" != "1" ]; then
        die "$EXIT_USAGE" "--keep-data=false 将删除数据卷，需显式 --yes 确认"
      fi
      log_step "按 --keep-data=false 删除主数据卷 ${MODERN_DATA_VOLUME}"
      run_cmd docker volume rm "$MODERN_DATA_VOLUME" 2>/dev/null || log_warn "删除数据卷失败或不存在"
    else
      log_info "保留主数据卷: ${MODERN_DATA_VOLUME}"
    fi
  fi

  # 结果清单
  log_info "卸载结果清单："
  log_info "  运行实体: 已按 mode=${mode} 处理"
  log_info "  数据卷 ${MODERN_DATA_VOLUME}: $(volume_exists "$MODERN_DATA_VOLUME" && echo 保留 || echo 已删除)"
}

# 旧系统卸载（仅在显式 --remove-legacy-controlplane 或目标环境为 legacy 时）
_uninstall_legacy() {
  local mode="$1"
  local keep_data="$2"
  local assume_yes="$3"
  local remove_controlplane="$4"

  log_info "==== 旧系统卸载 (mode=${mode}) ===="

  # 停止旧容器
  log_step "停止旧版容器"
  local name
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_running "$name" && run_cmd docker stop "$name" 2>/dev/null || true
  done

  if [ "$mode" = "stop" ]; then
    log_info "停用模式：旧容器已停止，物料与数据保留"
    return 0
  fi

  # 删除旧容器
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_exists "$name" && run_cmd docker rm -f "$name" 2>/dev/null || true
  done

  # 数据卷处理
  if [ "$mode" = "purge" ] || { [ "$mode" = "standard" ] && [ "$keep_data" = "0" ]; }; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "删除旧数据卷需显式 --yes 确认"
    fi
    log_step "删除旧版数据卷"
    local v
    for v in "${LEGACY_VOLUME_NAMES[@]}"; do
      volume_exists "$v" && run_cmd docker volume rm "$v" 2>/dev/null || true
    done
  else
    log_info "保留旧版数据卷（可用作回退源）"
  fi

  # 旧控制面遗留（Cockpit / systemd）——独立显式开关
  if [ "$remove_controlplane" = "1" ]; then
    if [ "$assume_yes" != "1" ]; then
      die "$EXIT_USAGE" "清理旧 Cockpit/systemd 遗留需显式 --yes 确认"
    fi
    log_step "清理旧 Cockpit / systemd 控制面遗留"
    if command_exists systemctl; then
      local unit
      for unit in "${LEGACY_SYSTEMD_UNITS[@]}"; do
        if systemd_unit_present "$unit"; then
          run_cmd systemctl stop "$unit" 2>/dev/null || true
          run_cmd systemctl disable "$unit" 2>/dev/null || true
        fi
      done
    fi
    log_warn "Cockpit 软件包与 /etc/cockpit、旧安装目录默认不在脚本内强删，请按需人工处理: ${LEGACY_INSTALL_DIR}"
  else
    log_warn "未指定 --remove-legacy-controlplane，旧 Cockpit/systemd 遗留保留未处理"
  fi

  log_info "旧系统卸载结果清单："
  log_info "  旧容器: 已按 mode=${mode} 处理"
  log_info "  旧数据卷: $( [ "$mode" = "purge" ] && echo 已删除 || echo 视模式保留 )"
  log_info "  旧控制面遗留: $( [ "$remove_controlplane" = "1" ] && echo 已停用/禁用 || echo 未处理 )"
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
      die "$EXIT_ENV_GUARD" "检测到 mixed 环境，卸载不自动执行，请先人工治理收敛到 modern 或 legacy"
      ;;
    empty)
      log_info "环境为 empty，无可卸载实体"
      ;;
    *)
      die "$EXIT_ENV_GUARD" "未知环境，卸载拒绝执行: $env_kind"
      ;;
  esac
}
