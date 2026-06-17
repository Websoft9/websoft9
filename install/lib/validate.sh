#!/bin/bash
# validate.sh — 统一校验层（§5.6 / §6.6 / §11）
# 职责：健康检查、入口验证、关键 API 验证、产品状态与结果收口。
# 不负责：数据迁移与环境识别。

# 等待容器进入 running，并尽量等待 healthcheck 通过
validate_container_health() {
  local timeout="${1:-180}"
  local waited=0 interval=5
  log_step "校验容器健康: $MODERN_CONTAINER_NAME (超时 ${timeout}s)"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过容器健康等待"
    return 0
  fi

  while [ "$waited" -lt "$timeout" ]; do
    if container_running "$MODERN_CONTAINER_NAME"; then
      local health
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
      case "$health" in
        healthy) log_info "容器健康检查通过 (healthy)"; return 0 ;;
        none)    log_info "容器运行中（未定义 healthcheck，视为就绪）"; return 0 ;;
        *)       : ;;  # starting / unhealthy -> 继续等待
      esac
    fi
    sleep "$interval"
    waited=$((waited + interval))
  done
  log_error "容器在 ${timeout}s 内未达到健康状态"
  return 1
}

# 校验控制台入口端口可达
validate_console_entry() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  log_step "校验控制台入口: 127.0.0.1:${console_port}"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过入口探测"
    return 0
  fi
  local i
  for i in $(seq 1 30); do
    if curl -fsS -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/" \
       || curl -fsS -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/api"; then
      log_info "控制台入口可达"
      return 0
    fi
    sleep 3
  done
  log_error "控制台入口 ${console_port} 不可达"
  return 1
}

# 校验产品 API 根路径可达
validate_api() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  log_step "校验产品 API: /api"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过 API 探测"
    return 0
  fi
  local i
  for i in $(seq 1 30); do
    if curl -fsS -o /dev/null --max-time 5 "http://127.0.0.1:${console_port}/api"; then
      log_info "产品 API 根路径可达"
      return 0
    fi
    sleep 3
  done
  log_error "产品 API 根路径不可达"
  return 1
}

# 校验主数据卷已挂载到 /data 且关键子树可读
validate_data_root() {
  log_step "校验主数据根: ${MODERN_DATA_VOLUME}:${MODERN_DATA_MOUNT}"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过数据根校验"
    return 0
  fi
  if ! volume_exists "$MODERN_DATA_VOLUME"; then
    log_error "主数据卷不存在: $MODERN_DATA_VOLUME"
    return 1
  fi
  if container_running "$MODERN_CONTAINER_NAME"; then
    if docker exec "$MODERN_CONTAINER_NAME" sh -c '[ -d /data/config ]' >/dev/null 2>&1; then
      log_info "主数据根就绪且关键子树可读"
      return 0
    fi
  fi
  log_warn "主数据根关键子树尚未就绪（可能仍在初始化）"
  return 1
}

# 校验产品运行时状态（版本接续 / edition），读取 product runtime state
validate_product_state() {
  log_step "校验产品运行时状态"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过产品状态校验"
    return 0
  fi
  if ! container_running "$MODERN_CONTAINER_NAME"; then
    log_error "容器未运行，无法校验产品状态"
    return 1
  fi
  local out
  out="$(docker exec "$MODERN_CONTAINER_NAME" python3 -c \
    'import sys; sys.path.insert(0, "/websoft9/apphub"); from src.services.product_metadata import read_product_metadata; m=read_product_metadata(); print(m.get("version"), m.get("edition_key"), m.get("state_source"))' 2>/dev/null)"
  if [ -n "$out" ]; then
    log_info "产品运行时状态: ${out}"
    return 0
  fi
  log_warn "未能读取产品运行时状态"
  return 1
}

# 全新安装最小验收（§5.6）
validate_install() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  local rc=0
  validate_container_health 180 || rc=1
  validate_console_entry "$console_port" || rc=1
  validate_api "$console_port" || rc=1
  validate_data_root || rc=1
  validate_product_state || rc=1
  return $rc
}

# 升级/迁移后验收（§6.6 / §11）：同样要求容器健康 + 入口 + API + 状态接续
validate_upgrade() {
  local console_port="${1:-$DEFAULT_CONSOLE_PORT}"
  local rc=0
  validate_container_health 240 || rc=1
  validate_console_entry "$console_port" || rc=1
  validate_api "$console_port" || rc=1
  validate_data_root || rc=1
  validate_product_state || rc=1
  return $rc
}
