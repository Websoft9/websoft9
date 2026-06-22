#!/bin/bash
# detect.sh — 环境识别层（§4）
# 职责：读取容器、卷、systemd、路径、端口/配置信号，输出 empty / legacy / modern / mixed。
# 不负责：安装、升级、卸载等具体动作。

# 强信号：现代运行实体是否存在
_detect_modern_data_root() {
  local data_root
  data_root="$(resolve_runtime_data_root "$DEFAULT_INSTALL_PATH")"
  [ -f "${data_root}/config/apphub/install-tracking.sqlite" ] && return 0
  [ -d "${data_root}/portainer/compose" ] && return 0
  return 1
}

_detect_modern_strong() {
  container_exists "$MODERN_CONTAINER_NAME" || [ -f "${DEFAULT_INSTALL_PATH}/docker-compose.yml" ] || _detect_modern_data_root
}

# 强信号：旧版运行实体（容器或卷）是否存在
_detect_legacy_strong() {
  local name
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_exists "$name" && return 0
  done
  for name in "${LEGACY_VOLUME_NAMES[@]}"; do
    volume_exists "$name" && return 0
  done
  return 1
}

# 辅助信号：旧版宿主机路径 / systemd 遗留（仅作观察，不单独触发 legacy/mixed）
_detect_legacy_auxiliary() {
  [ -d "$LEGACY_HOST_COMPOSE_DIR" ] && return 0
  [ -d "$LEGACY_INSTALL_DIR" ] && return 0
  local unit
  for unit in "${LEGACY_SYSTEMD_UNITS[@]}"; do
    systemd_unit_present "$unit" && return 0
  done
  return 1
}

# 打印关键观察信号（供 detect 命令做人工审计）
detect_print_signals() {
  log_info "Modern container exists: $(container_exists "$MODERN_CONTAINER_NAME" && echo yes || echo no)"
  log_info "Modern deployment material exists: $([ -f "${DEFAULT_INSTALL_PATH}/docker-compose.yml" ] && echo yes || echo no)"
  log_info "Modern data root configured: $(resolve_runtime_data_root "$DEFAULT_INSTALL_PATH")"
  log_info "Modern data root markers exist: $(_detect_modern_data_root && echo yes || echo no)"
  local name found_c="" found_v=""
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    container_exists "$name" && found_c="${found_c} ${name}"
  done
  for name in "${LEGACY_VOLUME_NAMES[@]}"; do
    volume_exists "$name" && found_v="${found_v} ${name}"
  done
  log_info "Legacy containers:${found_c:- none}"
  log_info "Legacy volumes:${found_v:- none}"
  log_info "Legacy host/systemd signals: $(_detect_legacy_auxiliary && echo yes || echo no)"
}

# 主识别函数：将结果回显到 stdout（empty|legacy|modern|mixed）
# 设计纪律：
# - modern 强信号 + legacy 强信号 => mixed（不自动处理）
# - 仅 modern 强信号 => modern（辅助旧路径残留不降级为 mixed，避免误判）
# - 仅 legacy 强信号 => legacy
# - 都没有强信号 => empty（辅助信号不足以判定 legacy）
detect_environment() {
  local has_modern="no" has_legacy="no"
  _detect_modern_strong && has_modern="yes"
  _detect_legacy_strong && has_legacy="yes"

  if [ "$has_modern" = "yes" ] && [ "$has_legacy" = "yes" ]; then
    echo "mixed"; return 0
  fi
  if [ "$has_modern" = "yes" ]; then
    echo "modern"; return 0
  fi
  if [ "$has_legacy" = "yes" ]; then
    echo "legacy"; return 0
  fi
  echo "empty"
}
