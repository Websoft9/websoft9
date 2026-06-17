#!/bin/bash
# upgrade-modern.sh — 新版迭代升级路径（§6）
# 职责：modern 环境的同模型升级。
# 不负责：旧卷映射、Cockpit 退场。

# 回退到升级前备份点：物料 + 主数据卷
_upgrade_modern_rollback() {
  local install_path="$1"
  local backup_dir="$2"

  log_warn "执行迭代升级回退 -> $backup_dir"

  # 先停掉失败的新运行时
  run_cmd modern_compose "$install_path" down 2>/dev/null || true

  # 恢复物料
  if [ -f "${backup_dir}/.env" ]; then
    run_cmd cp -a "${backup_dir}/.env" "${install_path}/.env"
  fi
  if [ -f "${backup_dir}/docker-compose.yml" ]; then
    run_cmd cp -a "${backup_dir}/docker-compose.yml" "${install_path}/docker-compose.yml"
  fi

  # 恢复主数据卷
  restore_volume "$MODERN_DATA_VOLUME" "$backup_dir" || log_warn "主数据卷回退失败，请人工核对备份: $backup_dir"

  # 重新启动旧运行时
  run_cmd modern_compose "$install_path" up -d || log_error "回退后旧运行时启动失败"
}

# 迭代升级主流程
run_upgrade_modern() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"
  local volumes_root="$6"

  log_info "==== 新版迭代升级开始 (modern) ===="

  require_root
  if [ ! -f "${install_path}/docker-compose.yml" ]; then
    die "$EXIT_RUNTIME" "未找到现有部署物料: ${install_path}/docker-compose.yml"
  fi

  # 1. 升级前识别与记录
  local current_image=""
  if container_exists "$MODERN_CONTAINER_NAME"; then
    current_image="$(docker inspect --format '{{.Config.Image}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
  fi
  log_info "当前镜像: ${current_image:-未知}"

  # 2. 升级前强制备份（不受 --keep-data 影响）
  local backup_dir
  backup_dir="$(backup_new_dir modern-upgrade)"
  backup_modern_pre_upgrade "$install_path" "$backup_dir"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 迭代升级前置完成，停止于物料切换前"
    return 0
  fi

  # 3. 物料切换：更新 compose 与 .env，拉取新镜像
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port" "$volumes_root"
  if ! modern_compose "$install_path" pull; then
    log_error "拉取新镜像失败，回退"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "迭代升级失败（镜像拉取）"
  fi

  # 4. 启动新容器（compose 自动滚动到新镜像；内置组件在启动时自迁移 schema）
  if ! modern_compose "$install_path" up -d; then
    log_error "新容器启动失败，回退"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_RUNTIME" "迭代升级失败（容器启动）"
  fi

  # 5. 升级后验证
  if ! validate_upgrade "$console_port"; then
    log_error "升级后验证未通过，回退到升级前运行时"
    _upgrade_modern_rollback "$install_path" "$backup_dir"
    die "$EXIT_VALIDATE" "迭代升级失败（升级后校验）"
  fi

  log_info "==== 新版迭代升级成功 ===="
  log_info "升级前备份点保留于: $backup_dir"
}
