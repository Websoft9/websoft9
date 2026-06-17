#!/bin/bash
# install-fresh.sh (lib) — 全新安装路径（§5）
# 职责：仅面向 empty 环境的全新安装。
# 不负责：旧系统迁移、混合环境治理。

# 前置检查：OS、Docker、端口、路径、磁盘
install_precheck() {
  local console_port="$1"
  local install_path="$2"

  log_step "全新安装前置检查"

  require_root

  # Docker / compose 准备
  if ! docker_available; then
    log_warn "未检测到可用 Docker，尝试自动安装"
    if [ "${W9_DRY_RUN:-0}" = "1" ]; then
      log_info "(dry-run) 跳过 Docker 安装"
    else
      ensure_docker_installed || die "$EXIT_PRECHECK" "Docker 自动安装失败"
    fi
  fi
  if [ "${W9_DRY_RUN:-0}" != "1" ] && ! compose_available; then
    die "$EXIT_PRECHECK" "docker compose 插件不可用"
  fi

  # 端口检查（控制台 + HTTP/HTTPS）
  local p
  for p in "$console_port" 80 443; do
    if port_in_use "$p"; then
      die "$EXIT_PRECHECK" "端口已被占用，无法全新安装: $p"
    fi
  done

  # 安装目录可写
  if [ "${W9_DRY_RUN:-0}" != "1" ]; then
    mkdir -p "$install_path" || die "$EXIT_PRECHECK" "无法创建安装目录: $install_path"
    [ -w "$install_path" ] || die "$EXIT_PRECHECK" "安装目录不可写: $install_path"
  fi

  log_info "前置检查通过"
}

# 物料准备：compose 文件 + .env + 安装目录
install_prepare_material() {
  local install_path="$1"
  local image_repo="$2"
  local image_tag="$3"
  local network_name="$4"
  local console_port="$5"
  local volumes_root="$6"

  log_step "准备部署物料"
  ensure_deployment_material "$install_path" "${W9_CHANNEL:-release}"
  write_env_file "${install_path}/.env" "$image_repo" "$image_tag" "$network_name" "$console_port" "$volumes_root"
  log_info "已生成标准 .env 与 compose 物料"
}

# 启动切换：拉取镜像并启动单容器
install_start() {
  local install_path="$1"
  log_step "启动现代单容器"
  run_cmd modern_compose "$install_path" pull
  run_cmd modern_compose "$install_path" up -d
}

# 启动后失败清理：仅清理本次生成的运行实体与物料
install_cleanup_on_failure() {
  local install_path="$1"
  log_warn "安装后校验失败，清理本次安装生成的运行实体与物料"
  run_cmd modern_compose "$install_path" down 2>/dev/null || true
}

# 全新安装主流程
run_install() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"
  local volumes_root="$6"

  log_info "==== 全新安装开始 (empty) ===="

  install_precheck "$console_port" "$install_path"
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port" "$volumes_root"
  install_start "$install_path"

  if ! validate_install "$console_port"; then
    install_cleanup_on_failure "$install_path"
    die "$EXIT_VALIDATE" "全新安装校验未通过"
  fi

  log_info "==== 全新安装成功 ===="
  log_info "控制台入口: http://<host>:${console_port}"
}
