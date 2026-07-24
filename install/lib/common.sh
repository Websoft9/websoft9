#!/bin/bash
# common.sh — Websoft9 生命周期脚本共享层
# 职责：固定代码事实常量、统一日志、统一退出码、通用工具函数。
# 不负责：环境识别、安装、升级、迁移、卸载等具体路径动作。

# ---------------------------------------------------------------------------
# 现代运行时事实（对齐 docker/docker-compose.yml 与入口脚本）
# ---------------------------------------------------------------------------
MODERN_CONTAINER_NAME="websoft9"
MODERN_COMPOSE_PROJECT="websoft9"
MODERN_DATA_VOLUME="websoft9_data"
MODERN_DATA_MOUNT="/data"

# Resolve the container name for a given channel.
# Keeps channel→name mapping in one place (used by install-fresh and upgrade-modern).
resolve_container_name_by_channel() {
  case "${1:-${W9_CHANNEL:-release}}" in
    dev) echo "websoft9-dev" ;;
    rc)  echo "websoft9-rc" ;;
    *)   echo "websoft9" ;;
  esac
}

# Detect a running Websoft9 container on the host.
# Returns the container name, or empty if none found.
# Identifies by IMAGE (websoft9dev/websoft9:*), not by container name.
# This handles custom container names set by the user in .env.
# Prefers running containers over stopped ones.
_detect_websoft9_container() {
  local name image running_name stopped_name
  while IFS='|' read -r name image; do
    [ -z "$name" ] && continue
    [[ "$image" == websoft9dev/websoft9:* ]] || continue
    if container_running "$name"; then
      running_name="$name"
      break
    elif [ -z "$stopped_name" ]; then
      stopped_name="$name"
    fi
  done < <(docker ps -a --format '{{.Names}}|{{.Image}}' 2>/dev/null)

  echo "${running_name:-$stopped_name}"
}

# Resolve the actual container name. Priority:
#   1) CONTAINER_NAME env var (set by the caller based on channel)
#   2) Hardcoded container_name: line in the compose file
#   3) Default MODERN_CONTAINER_NAME
_resolve_container_name() {
  local compose_file="$1"
  [ -n "${CONTAINER_NAME:-}" ] && { echo "$CONTAINER_NAME"; return 0; }
  local name
  if [ -f "$compose_file" ]; then
    name="$(grep -m1 'container_name:' "$compose_file" 2>/dev/null | awk '{print $2}' | tr -d "'\"")"
    # Strip common variable patterns from compose files.
    # Order matters: longer prefixes (:- and -) must be matched first,
    # otherwise the bare ${CONTAINER_NAME} prefix would consume them.
    #   ${CONTAINER_NAME:-websoft9} → websoft9
    #   ${CONTAINER_NAME-websoft9}  → websoft9
    #   ${CONTAINER_NAME}           → (empty, falls back to default)
    name="${name#\$\{CONTAINER_NAME:-}"          # ${CONTAINER_NAME:-...}
    name="${name#\$\{CONTAINER_NAME-}"           # ${CONTAINER_NAME-...}
    name="${name#\$\{CONTAINER_NAME\}}"          # ${CONTAINER_NAME} (bare)
    name="${name%\}}"
  fi
  echo "${name:-$MODERN_CONTAINER_NAME}"
}

_strip_wrapping_quotes() {
  local value="$1"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value#\"}"
    value="${value%\"}"
  elif [[ "$value" == "'"* && "$value" == *"'" ]]; then
    value="${value#"'"}"
    value="${value%"'"}"
  fi
  echo "$value"
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  [ -f "$env_file" ] || return 1
  local value
  value="$(grep -m1 "^${key}=" "$env_file" 2>/dev/null | cut -d= -f2-)"
  [ -n "$value" ] || return 1
  _strip_wrapping_quotes "$value"
}

# compose 默认环境变量（与 docker-compose.yml 的 ${VAR:-default} 一致）
DEFAULT_IMAGE_REPO="websoft9dev/websoft9"
DEFAULT_IMAGE_TAG="latest"
DEFAULT_NETWORK_NAME="websoft9"
DEFAULT_CONSOLE_PORT="9000"
DEFAULT_INSTALL_PATH="/opt/websoft9"
DEFAULT_WEBSOFT9_DATA_ROOT="/opt/websoft9/data"
DEFAULT_DOCKER_VOLUMES_ROOT="/var/lib/docker/volumes"

# 制品分发根（单文件 install.sh 在无本地物料时从此处按通道下载部署物料）
DEFAULT_ARTIFACT_BASE="https://artifact.websoft9.com/websoft9"

# ---------------------------------------------------------------------------
# 旧版（Cockpit 多容器时代）运行时事实
# ---------------------------------------------------------------------------
LEGACY_CONTAINER_NAMES=(websoft9-apphub websoft9-deployment websoft9-git websoft9-proxy)
LEGACY_CONTAINER_CANDIDATES=(websoft9-apphub websoft9-deployment websoft9-git websoft9-proxy websoft9-appmanage websoft9-portainer websoft9-gitea websoft9-nginxproxymanager websoft9-redis)
LEGACY_VOLUME_NAMES=(apphub_logs apphub_media apphub_config portainer gitea nginx_data nginx_letsencrypt nginx_modsec nginx_var)
LEGACY_VOLUME_ROLES=(apphub_logs apphub_media apphub_config portainer gitea nginx_data nginx_letsencrypt nginx_modsec nginx_var)
LEGACY_SYSTEMD_UNITS=(websoft9.service cockpit.socket cockpit.service)
LEGACY_HOST_COMPOSE_DIR="/data/compose"
LEGACY_INSTALL_DIR="/data/websoft9/source"
LEGACY_SERVICE_ROOT_DIR="/data/apps/w9services"
LEGACY_DOWNLOAD_ROOT_DIR="/data/apps/websoft9"
LEGACY_COMPOSE_PROJECT="websoft9"

# ---------------------------------------------------------------------------
# 统一退出码
# ---------------------------------------------------------------------------
EXIT_OK=0
EXIT_USAGE=2
EXIT_PRECHECK=3
EXIT_ENV_GUARD=4      # mixed / unknown / 环境不匹配目标路径
EXIT_RUNTIME=5        # 启动 / 切换 / 运行时失败
EXIT_VALIDATE=6       # 健康检查 / 验收失败
EXIT_ROLLBACK=7       # 回退过程失败

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
_w9_ts() { date +"%Y-%m-%d %H:%M:%S"; }

log_info()  { echo "[Websoft9][$(_w9_ts)][INFO ] $*"; }
log_warn()  { echo "[Websoft9][$(_w9_ts)][WARN ] $*" >&2; }
log_error() { echo "[Websoft9][$(_w9_ts)][ERROR] $*" >&2; }
log_step()  { echo "[Websoft9][$(_w9_ts)][STEP ] $*"; }
log_done()  { echo "[Websoft9][$(_w9_ts)][DONE ] $*"; }

_log_with_level() {
  local level="$1"
  shift
  case "$level" in
    STEP) log_step "$*" ;;
    WARN) log_warn "$*" ;;
    ERROR) log_error "$*" ;;
    *) log_info "$*" ;;
  esac
}

# dry-run 感知执行：W9_DRY_RUN=1 时只打印不执行
run_cmd() {
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) $*"
    return 0
  fi
  "$@"
}

run_cmd_logged() {
  local level="$1"
  shift

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) $*"
    return 0
  fi

  local stream_pipe reader_pid rc
  stream_pipe="$(mktemp -u)"
  mkfifo "$stream_pipe" || return 1

  while IFS= read -r line; do
    line="${line//$'\r'/}"
    [ -n "$line" ] && _log_with_level "$level" "  $line"
  done < "$stream_pipe" &
  reader_pid=$!

  "$@" > "$stream_pipe" 2>&1
  rc=$?

  wait "$reader_pid"
  rm -f "$stream_pipe"
  return $rc
}

die() {
  local code="$1"; shift
  log_error "$*"
  exit "$code"
}

# ---------------------------------------------------------------------------
# 通用探测工具
# ---------------------------------------------------------------------------
command_exists() { command -v "$@" >/dev/null 2>&1; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "$EXIT_PRECHECK" "Root privileges are required. Please re-run this command with sudo or as root."
  fi
}

# Docker 可用性
docker_available() {
  command_exists docker && docker info >/dev/null 2>&1
}

# compose 可用性
compose_available() {
  command_exists docker && docker compose version >/dev/null 2>&1
}

# 容器是否存在（任意状态）
container_exists() {
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

# 容器是否正在运行
container_running() {
  docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

# 命名卷是否存在
volume_exists() {
  docker volume inspect "$1" >/dev/null 2>&1
}

legacy_role_candidates() {
  case "$1" in
    apphub_logs) printf '%s\n' apphub_logs ;;
    apphub_media) printf '%s\n' apphub_media ;;
    apphub_config) printf '%s\n' apphub_config ;;
    portainer) printf '%s\n' portainer portainer_data ;;
    gitea) printf '%s\n' gitea gitea_data ;;
    nginx_data) printf '%s\n' nginx_data ;;
    nginx_letsencrypt) printf '%s\n' nginx_letsencrypt ;;
    nginx_modsec) printf '%s\n' nginx_modsec ;;
    nginx_var) printf '%s\n' nginx_var ;;
    *) return 1 ;;
  esac
}

legacy_resolve_volume_for_role() {
  local role="$1"
  local candidate volume matched=""
  local candidates
  candidates="$(legacy_role_candidates "$role" 2>/dev/null || true)"
  [ -n "$candidates" ] || return 1

  while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    if volume_exists "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done <<EOF
$candidates
EOF

  while IFS= read -r volume; do
    [ -n "$volume" ] || continue
    while IFS= read -r candidate; do
      [ -n "$candidate" ] || continue
      if [ "$volume" = "$candidate" ] || [[ "$volume" == *_"$candidate" ]]; then
        if [ -n "$matched" ] && [ "$matched" != "$volume" ]; then
          log_warn "Multiple legacy volume candidates for role ${role}: ${matched}, ${volume}; using ${matched}"
          echo "$matched"
          return 0
        fi
        matched="$volume"
      fi
    done <<EOF
$candidates
EOF
  done < <(docker volume ls --format '{{.Name}}' 2>/dev/null)

  [ -n "$matched" ] || return 1
  echo "$matched"
}

legacy_list_resolved_volumes() {
  local role resolved
  for role in "${LEGACY_VOLUME_ROLES[@]}"; do
    resolved="$(legacy_resolve_volume_for_role "$role" 2>/dev/null || true)"
    [ -n "$resolved" ] && echo "$resolved"
  done | awk '!seen[$0]++'
}

legacy_host_compose_dir() {
  [ -d "$LEGACY_HOST_COMPOSE_DIR" ] && { echo "$LEGACY_HOST_COMPOSE_DIR"; return 0; }
  return 1
}

legacy_service_root_dir() {
  [ -d "$LEGACY_SERVICE_ROOT_DIR" ] && { echo "$LEGACY_SERVICE_ROOT_DIR"; return 0; }
  return 1
}

legacy_download_root_dir() {
  [ -d "$LEGACY_DOWNLOAD_ROOT_DIR" ] && { echo "$LEGACY_DOWNLOAD_ROOT_DIR"; return 0; }
  return 1
}

LEGACY_HOST_BACKUP_DIR="/data/backup"

legacy_host_backup_dir() {
  [ -d "$LEGACY_HOST_BACKUP_DIR" ] && { echo "$LEGACY_HOST_BACKUP_DIR"; return 0; }
  return 1
}

# systemd 单元是否存在
systemd_unit_present() {
  command_exists systemctl || return 1
  systemctl list-unit-files "$1" 2>/dev/null | grep -q "$1"
}

# 端口是否被占用（返回 0 表示被占用）
port_in_use() {
  local port="$1"
  if command_exists ss; then
    ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  elif command_exists netstat; then
    netstat -lnt 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  else
    return 1
  fi
}

# ---------------------------------------------------------------------------
# 部署物料定位
# ---------------------------------------------------------------------------
# 解析仓库内 docker-compose.yml 源路径（供安装/升级复制到安装目录）。
# 优先使用当前工作区内的 compose，兼容源码入口与 dist 单文件入口。
resolve_bundled_compose() {
  local preferred_compose="docker-compose.yml"
  if [ "${W9_CHANNEL:-release}" = "dev" ]; then
    preferred_compose="docker-compose.dev.yml"
  fi
  local candidates=(
    "${W9_ROOT_DIR}/../docker/${preferred_compose}"
    "${W9_ROOT_DIR}/../../docker/${preferred_compose}"
    "${W9_LIB_DIR}/../../docker/${preferred_compose}"
    "${W9_LIB_DIR}/../${preferred_compose}"
    "${W9_LIB_DIR}/${preferred_compose}"
    "${W9_ROOT_DIR}/../docker/docker-compose.yml"
    "${W9_ROOT_DIR}/../../docker/docker-compose.yml"
    "${W9_LIB_DIR}/../../docker/docker-compose.yml"
    "${W9_LIB_DIR}/../docker-compose.yml"
    "${W9_LIB_DIR}/docker-compose.yml"
  )
  local c dir base
  for c in "${candidates[@]}"; do
    if [ -f "$c" ]; then
      dir="$(cd "$(dirname "$c")" && pwd)"
      base="$(basename "$c")"
      echo "${dir}/${base}"
      return 0
    fi
  done
  return 1
}

default_data_root_for_install_path() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  echo "${install_path%/}/data"
}

# HTTP 抓取到 stdout（curl 优先，回落 wget）
_w9_fetch() {
  local url="$1"
  if command_exists curl; then
    curl -fsSL --max-time 30 "$url" 2>/dev/null
  elif command_exists wget; then
    wget -qO- --timeout=30 "$url" 2>/dev/null
  else
    return 1
  fi
}

# HTTP 下载到文件（curl 优先，回落 wget）
_w9_download() {
  local url="$1" dst="$2"
  if command_exists curl; then
    curl -fsSL --max-time 60 "$url" -o "$dst" 2>/dev/null
  elif command_exists wget; then
    wget -q --timeout=60 -O "$dst" "$url" 2>/dev/null
  else
    return 1
  fi
}

# 确保部署物料（docker-compose.yml）就位：
# 1) 优先使用脚本相邻或仓库/解压包内的 compose（开发与 bundle 解压场景）；
# 2) 否则按通道从制品分发根下载（单文件 install.sh 真实安装场景）。
# 物料落到 install_path/docker-compose.yml。
ensure_deployment_material() {
  local install_path="$1"
  local channel="${2:-${W9_CHANNEL:-release}}"
  local compose_dst="${install_path}/docker-compose.yml"

  run_cmd mkdir -p "$install_path"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    local local_compose
    if local_compose="$(resolve_bundled_compose)"; then
      log_info "(dry-run) using local deployment material: $local_compose"
    else
      log_info "(dry-run) will download deployment material from: ${W9_ARTIFACT_BASE:-$DEFAULT_ARTIFACT_BASE}/${channel}"
    fi
    return 0
  fi

  local local_compose
  if local_compose="$(resolve_bundled_compose)"; then
    log_info "Using local deployment material: $local_compose"
    cp -a "$local_compose" "$compose_dst"
    return 0
  fi

  # 远程制品：从同源目录下载 manifest -> compose_file -> compose
  local base="${W9_ARTIFACT_BASE:-$DEFAULT_ARTIFACT_BASE}/${channel}"
  log_info "No local material found, downloading from: $base"
  local manifest compose_name
  manifest="$(_w9_fetch "${base}/manifest.json")" || manifest=""
  compose_name="$(printf '%s' "$manifest" | sed -n 's/.*"compose_file"[^"]*"\([^"]*\)".*/\1/p' | head -n1)"
  [ -z "$compose_name" ] && compose_name="docker-compose.yml"

  if ! _w9_download "${base}/${compose_name}" "$compose_dst"; then
    die "$EXIT_PRECHECK" "Failed to download deployment material: ${base}/${compose_name}"
  fi
  # 元数据为可选增强项，失败不阻塞
  _w9_download "${base}/version.json" "${install_path}/version.json" || true
  _w9_download "${base}/mirrors.json" "${install_path}/mirrors.json" || true
  log_info "Deployment material downloaded to: $compose_dst"
}

# 确保 Docker 就绪：优先本地 install_docker.sh，否则按通道从制品分发根下载后执行。
ensure_docker_installed() {
  local channel="${1:-${W9_CHANNEL:-release}}"
  local candidates=(
    "${W9_LIB_DIR}/../install_docker.sh"
    "${W9_LIB_DIR}/install_docker.sh"
  )
  local c
  for c in "${candidates[@]}"; do
    if [ -f "$c" ]; then
      log_info "Using local Docker install script: $c"
      bash "$c"
      return $?
    fi
  done

  local base="${W9_ARTIFACT_BASE:-$DEFAULT_ARTIFACT_BASE}/${channel}"
  local tmp
  tmp="$(mktemp)"
  log_info "No local Docker install script found, downloading from: ${base}/install_docker.sh"
  if _w9_download "${base}/install_docker.sh" "$tmp"; then
    bash "$tmp"
    local rc=$?
    rm -f "$tmp"
    return $rc
  fi
  rm -f "$tmp"
  return 1
}

# 生成标准 .env（仅写入与现代 compose 事实对齐的键）
write_env_file() {
  local env_path="$1"
  local image_tag="$2"
  local console_port="$3"
  local install_path="$4"
  local data_root_default
  local docker_volumes_root
  data_root_default="$(default_data_root_for_install_path "$install_path")"
  docker_volumes_root="$(resolve_docker_volumes_root)"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) writing .env -> $env_path"
    return 0
  fi

  cat >"$env_path" <<EOF
# Generated by Websoft9 installer on $(_w9_ts)
IMAGE_REPO=${DEFAULT_IMAGE_REPO}
IMAGE_TAG=${image_tag}
CONSOLE_PORT=${console_port}
CONTAINER_NAME=${CONTAINER_NAME}
WEBSOFT9_DATA_ROOT=${WEBSOFT9_DATA_ROOT:-$data_root_default}
WEBSOFT9_DOCKER_VOLUMES_ROOT=${WEBSOFT9_DOCKER_VOLUMES_ROOT:-$docker_volumes_root}
EOF
}

resolve_docker_volumes_root() {
  local docker_root=""
  local candidate=""

  if [ -n "${WEBSOFT9_DOCKER_VOLUMES_ROOT:-}" ] && [ -d "${WEBSOFT9_DOCKER_VOLUMES_ROOT}" ]; then
    echo "${WEBSOFT9_DOCKER_VOLUMES_ROOT}"
    return 0
  fi

  if docker_available; then
    docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null | head -n 1)"
    if [ -n "$docker_root" ] && [ -d "${docker_root}/volumes" ]; then
      echo "${docker_root}/volumes"
      return 0
    fi
  fi

  for candidate in \
    "$DEFAULT_DOCKER_VOLUMES_ROOT" \
    "/data/docker/volumes" \
    "/opt/docker/volumes"
  do
    if [ -d "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  echo "$DEFAULT_DOCKER_VOLUMES_ROOT"
}

_runtime_data_root_has_modern_markers() {
  local data_root="$1"
  [ -n "$data_root" ] || return 1
  [ -f "${data_root}/config/apphub/install-tracking.sqlite" ] && return 0
  [ -d "${data_root}/portainer/compose" ] && return 0
  [ -f "${data_root}/portainer/credential" ] && return 0
  [ -f "${data_root}/gitea/credential" ] && return 0
  return 1
}

_resolve_existing_container_data_root() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local compose_file="${install_path}/docker-compose.yml"
  local container_name
  container_name="$(_resolve_container_name "$compose_file")"
  container_exists "$container_name" || return 1

  docker inspect --format '{{range .Mounts}}{{if eq .Type "bind"}}{{if or (eq .Destination "/data") (eq .Destination "/opt/websoft9/data")}}{{.Source}}{{println}}{{end}}{{end}}{{end}}' "$container_name" 2>/dev/null \
    | sed '/^$/d' \
    | head -n 1
}

resolve_existing_runtime_data_root() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local include_legacy_fallback="${2:-0}"
  local env_file="${install_path}/.env"
  local data_root="${WEBSOFT9_DATA_ROOT:-}"
  local default_data_root
  default_data_root="$(default_data_root_for_install_path "$install_path")"

  if [ -z "$data_root" ] && [ -f "$env_file" ]; then
    data_root="$(read_env_value "$env_file" WEBSOFT9_DATA_ROOT 2>/dev/null || true)"
  fi
  data_root="$(_strip_wrapping_quotes "$data_root")"
  if [ -n "$data_root" ]; then
    echo "$data_root"
    return 0
  fi

  data_root="$(_resolve_existing_container_data_root "$install_path")"
  if [ -n "$data_root" ]; then
    echo "$data_root"
    return 0
  fi

  # Legacy data at /data should be migrated to the canonical data root
  # (${install_path}/data) so that all Websoft9 data lives under one clean
  # directory.  The Alpine transform container receives ${data_root}:/data
  # so writes to /data inside the container land on the new host path.
  if _runtime_data_root_has_modern_markers /data; then
    echo "$default_data_root"
    return 0
  fi

  if _runtime_data_root_has_modern_markers "$default_data_root"; then
    echo "$default_data_root"
    return 0
  fi

  # Legacy install with compose workspace only — migrate to new default.
  if [ "$include_legacy_fallback" = "1" ] && [ -d "$LEGACY_HOST_COMPOSE_DIR" ]; then
    echo "$default_data_root"
    return 0
  fi

  echo "$default_data_root"
}

resolve_runtime_data_root() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local env_file="${install_path}/.env"
  local data_root="${WEBSOFT9_DATA_ROOT:-}"
  local default_data_root
  default_data_root="$(default_data_root_for_install_path "$install_path")"
  if [ -z "$data_root" ] && [ -f "$env_file" ]; then
    data_root="$(read_env_value "$env_file" WEBSOFT9_DATA_ROOT 2>/dev/null || true)"
  fi
  data_root="$(_strip_wrapping_quotes "$data_root")"
  echo "${data_root:-$default_data_root}"
}

resolve_modern_compose_project() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local env_file="${install_path}/.env"
  local container_name="${CONTAINER_NAME:-}"

  if [ -z "$container_name" ] && [ -f "$env_file" ]; then
    container_name="$(read_env_value "$env_file" CONTAINER_NAME 2>/dev/null || true)"
  fi
  container_name="$(_strip_wrapping_quotes "$container_name")"

  if [ -n "$container_name" ]; then
    echo "$container_name"
    return 0
  fi

  echo "$MODERN_COMPOSE_PROJECT"
}

ensure_shared_network() {
  if docker network inspect "$DEFAULT_NETWORK_NAME" >/dev/null 2>&1; then
    log_info "Reusing shared Docker network: $DEFAULT_NETWORK_NAME"
    return 0
  fi
  log_step "Creating shared Docker network: $DEFAULT_NETWORK_NAME"
  run_cmd docker network create "$DEFAULT_NETWORK_NAME" >/dev/null
}

remove_modern_deployment_material() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  run_cmd rm -f \
    "${install_path}/docker-compose.yml" \
    "${install_path}/.env" \
    "${install_path}/version.json" \
    "${install_path}/mirrors.json" \
    2>/dev/null || true
}

print_runtime_summary() {
  local action="$1"
  local install_path="$2"
  local console_port="$3"
  local backup_dir="${4:-}"
  local compose_file="${install_path}/docker-compose.yml"
  local container_name data_root image_ref version_label

  container_name="$(_resolve_container_name "$compose_file")"
  data_root="$(resolve_runtime_data_root "$install_path")"
  image_ref="$(docker inspect --format '{{.Config.Image}}' "$container_name" 2>/dev/null || true)"
  version_label="$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$container_name" 2>/dev/null || true)"

  log_done "============================================================"
  log_done "Websoft9 ${action} completed successfully"
  log_done "Console: http://<host>:${console_port}"
  log_done "Container: ${container_name}"
  log_done "Image: ${image_ref:-unknown}"
  log_done "Version: ${version_label:-unknown}"
  log_done "Install path: ${install_path}"
  log_done "Data root: ${data_root}"
  log_done "Compose file: ${compose_file}"
  [ -n "$backup_dir" ] && log_done "Backup point: ${backup_dir}"
  log_done "Channel: ${W9_CHANNEL:-release}"
  log_done "============================================================"
}

doctor_report() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local console_port="${2:-$DEFAULT_CONSOLE_PORT}"
  local compose_file="${install_path}/docker-compose.yml"
  local bundled_compose data_root container_name image_ref env_kind

  env_kind="$(detect_environment 2>/dev/null || echo unknown)"
  bundled_compose="$(resolve_bundled_compose 2>/dev/null || true)"
  data_root="$(resolve_runtime_data_root "$install_path")"
  container_name="$(_resolve_container_name "$compose_file")"
  image_ref="$(docker inspect --format '{{.Config.Image}}' "$container_name" 2>/dev/null || true)"

  log_info "Doctor report:"
  log_info "  Environment kind: ${env_kind}"
  log_info "  Channel: ${W9_CHANNEL:-release}"
  log_info "  Install path: ${install_path}"
  log_info "  Data root: ${data_root}"
  log_info "  Compose in install path: $([ -f "$compose_file" ] && echo yes || echo no)"
  log_info "  Local bundled compose: ${bundled_compose:-none}"
  log_info "  Container name: ${container_name}"
  log_info "  Container exists: $(container_exists "$container_name" && echo yes || echo no)"
  log_info "  Container running: $(container_running "$container_name" && echo yes || echo no)"
  log_info "  Container image: ${image_ref:-unknown}"
  log_info "  Docker available: $(docker_available && echo yes || echo no)"
  log_info "  Compose available: $(compose_available && echo yes || echo no)"
  log_info "  Console port (${console_port}) in use: $(port_in_use "$console_port" && echo yes || echo no)"
  log_info "  HTTP port (80) in use: $(port_in_use 80 && echo yes || echo no)"
  log_info "  HTTPS port (443) in use: $(port_in_use 443 && echo yes || echo no)"
  detect_print_signals
}

# 统一的 compose 调用封装（固定项目名与 env 文件）
modern_compose() {
  local install_path="$1"; shift
  local compose_project
  compose_project="$(resolve_modern_compose_project "$install_path")"
  docker compose \
    -p "$compose_project" \
    --env-file "${install_path}/.env" \
    -f "${install_path}/docker-compose.yml" \
    "$@"
}

restart_docker_service() {
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) would restart Docker service"
    return 0
  fi

  if command_exists systemctl; then
    run_cmd systemctl restart docker || return 1
  elif command_exists service; then
    run_cmd service docker restart || return 1
  else
    log_error "Unable to restart Docker: neither systemctl nor service is available"
    return 1
  fi

  if ! docker_available; then
    log_error "Docker did not become available after restart"
    return 1
  fi

  return 0
}

# ────────────────────────────────────────────────────────────
# Mirror config bootstrap — write mirrors.json to config.ini
# once during install / upgrade when the value is empty.
# ────────────────────────────────────────────────────────────
ensure_docker_mirror_config() {
  local install_path="$1"
  local data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
  local config_path="${data_root}/config/apphub/config.ini"

  if [ ! -f "$config_path" ]; then
    log_info "docker_mirror: config.ini not found at $config_path, skipping"
    return 0
  fi

  python3 - "$config_path" "$install_path" <<'PY'
import json, os, sys, configparser

config_path, install_path = sys.argv[1], sys.argv[2]

config = configparser.ConfigParser()
config.read(config_path, encoding="utf-8")

configured = config.get("docker_mirror", "url", fallback="").strip()
if configured:
    print("docker_mirror: already configured, skipping")
    sys.exit(0)

mirrors_file = os.path.join(install_path, "mirrors.json")
if not os.path.exists(mirrors_file):
    print("docker_mirror: no mirrors.json found, skipping")
    sys.exit(0)

with open(mirrors_file, encoding="utf-8") as fh:
    payload = json.load(fh)
entries = payload.get("mirrors", []) if isinstance(payload, dict) else []
if not entries:
    print("docker_mirror: mirrors.json is empty, skipping")
    sys.exit(0)

normalized = "\n".join(
    str(e).strip().rstrip("/").removeprefix("http://").removeprefix("https://")
    for e in entries if str(e).strip()
)
if not normalized:
    print("docker_mirror: no valid entries after normalization, skipping")
    sys.exit(0)

if not config.has_section("docker_mirror"):
    config.add_section("docker_mirror")
config.set("docker_mirror", "url", normalized)
with open(config_path, "w", encoding="utf-8") as fh:
    config.write(fh)
print(f"docker_mirror: bootstrapped with {len(normalized.splitlines())} entries")
PY
}

load_mirror_entries() {
  local install_path="$1"
  local channel="${W9_CHANNEL:-release}"
  local mirrors_url="https://artifact.websoft9.com/websoft9/${channel}/mirrors.json"
  local mirrors_file="${install_path}/mirrors.json"
  local cleanup_file=""

  if [ ! -f "$mirrors_file" ]; then
    cleanup_file="/tmp/websoft9-mirrors-$$.json"
    mirrors_file="$cleanup_file"
    if ! _w9_download "$mirrors_url" "$mirrors_file"; then
      log_error "Failed to download mirror list from $mirrors_url"
      rm -f "$cleanup_file"
      return 1
    fi
  fi

  local mirrors
  mirrors="$(grep -o '"[^"]*"' "$mirrors_file" | tr -d '"' | grep -v '^mirrors$')"

  if [ -n "$cleanup_file" ]; then
    rm -f "$cleanup_file"
  fi

  if [ -z "$mirrors" ]; then
    log_error "No mirrors found in mirror list"
    return 1
  fi

  printf '%s\n' "$mirrors"
}

pull_image_via_prefixed_mirrors() {
  local image_repo="$1"
  local image_tag="$2"
  local image_ref="$3"
  local mirrors="$4"

  local mirror success=1
  while IFS= read -r mirror; do
    [ -z "$mirror" ] && continue
    local mirror_image="${mirror}/${image_repo}:${image_tag}"
    log_info "Trying mirror: $mirror"

    if docker pull "$mirror_image"; then
      docker tag "$mirror_image" "$image_ref"
      if [ "$mirror_image" != "$image_ref" ]; then
        docker rmi "$mirror_image" >/dev/null 2>&1 || true
      fi
      log_info "Pull succeeded via mirror: $mirror"
      success=0
      break
    fi

    log_warn "Mirror $mirror failed, trying next..."
  done <<< "$mirrors"

  return "$success"
}

write_temp_daemon_json_from_mirrors() {
  local daemon_file="$1"
  local mirrors="$2"

  {
    printf '{\n  "registry-mirrors": [\n'
    local first=1
    local mirror mirror_url
    while IFS= read -r mirror; do
      [ -z "$mirror" ] && continue
      mirror_url="$mirror"
      case "$mirror_url" in
        http://*|https://*) ;;
        *) mirror_url="https://${mirror_url}" ;;
      esac
      if [ "$first" -eq 1 ]; then
        first=0
      else
        printf ',\n'
      fi
      printf '    "%s"' "$mirror_url"
    done <<< "$mirrors"
    printf '\n  ]\n}\n'
  } > "$daemon_file"
}

pull_image_via_temporary_daemon_mirrors() {
  local install_path="$1"
  local mirrors="$2"
  local daemon_file="/etc/docker/daemon.json"
  local backup_file="/tmp/websoft9-daemon-backup-$$.json"
  local had_original=0
  local pull_status=1
  local restore_status=0

  if [ -f "$daemon_file" ]; then
    cp -a "$daemon_file" "$backup_file"
    had_original=1
  else
    rm -f "$backup_file"
  fi

  # Restore the original daemon.json even if the script exits mid-flight.
  export W9_TRAP_DAEMON_FILE="$daemon_file"
  export W9_TRAP_BACKUP_FILE="$backup_file"
  export W9_TRAP_HAD_ORIGINAL="$had_original"
  trap '_restore_daemon_json "$W9_TRAP_DAEMON_FILE" "$W9_TRAP_BACKUP_FILE" "$W9_TRAP_HAD_ORIGINAL"' EXIT

  write_temp_daemon_json_from_mirrors "$daemon_file" "$mirrors"

  log_warn "Direct and explicit mirror pulls failed, retrying with a temporary Docker daemon mirror configuration"
  if ! restart_docker_service; then
    log_error "Failed to restart Docker after writing temporary daemon.json"
    pull_status=1
  elif modern_compose "$install_path" pull; then
    log_info "Pull succeeded via temporary Docker daemon mirror configuration"
    pull_status=0
  else
    log_warn "Pull failed even after applying temporary Docker daemon mirror configuration"
    pull_status=1
  fi

  # Restore now (trap also covers this, but explicit restore gives better error handling).
  _restore_daemon_json "$daemon_file" "$backup_file" "$had_original"
  trap - EXIT
  unset W9_TRAP_DAEMON_FILE W9_TRAP_BACKUP_FILE W9_TRAP_HAD_ORIGINAL

  return "$pull_status"
}

# Restore original daemon.json (called via trap and inline in pull path).
_restore_daemon_json() {
  local daemon_file="$1" backup_file="$2" had_original="$3"
  if [ "$had_original" = "1" ] && [ -f "$backup_file" ]; then
    cp -a "$backup_file" "$daemon_file" 2>/dev/null || true
  elif [ "$had_original" != "1" ]; then
    rm -f "$daemon_file" 2>/dev/null || true
  fi
  rm -f "$backup_file" 2>/dev/null || true
  restart_docker_service 2>/dev/null || true
}

# 镜像拉取（带镜像加速回退）
# 先尝试 docker compose pull 直拉；失败后使用 mirrors.json 中的地址显式拉取；
# 若仍失败，则临时写入全新的 /etc/docker/daemon.json 并重启 Docker 后再试一次；
# 结束后恢复原 daemon.json。全部失败返回 1。
pull_image_with_mirrors() {
  local install_path="$1"

  # 从 .env 读取镜像名（已由 install_prepare_material 写入）
  local env_file="${install_path}/.env"
  local image_repo image_tag
  if [ -f "$env_file" ]; then
    image_repo="$(read_env_value "$env_file" IMAGE_REPO 2>/dev/null || true)"
    image_tag="$(read_env_value "$env_file" IMAGE_TAG 2>/dev/null || true)"
  fi
  image_repo="${image_repo:-$DEFAULT_IMAGE_REPO}"
  image_tag="${image_tag:-$DEFAULT_IMAGE_TAG}"
  local image_ref="${image_repo}:${image_tag}"

  # 1. 先尝试直拉（利用 Docker daemon 已配置的镜像加速）
  log_info "Pulling image: $image_ref"
  if modern_compose "$install_path" pull; then
    return 0
  fi
  log_warn "Direct pull failed, trying mirror accelerators..."

  local mirrors
  if ! mirrors="$(load_mirror_entries "$install_path")"; then
    return 1
  fi

  log_info "Loaded $(echo "$mirrors" | wc -l) mirror(s), trying in order..."

  if pull_image_via_prefixed_mirrors "$image_repo" "$image_tag" "$image_ref" "$mirrors"; then
    return 0
  fi

  if pull_image_via_temporary_daemon_mirrors "$install_path" "$mirrors"; then
    return 0
  fi

  log_error "Direct pull, explicit mirrors, and temporary Docker daemon mirror configuration all failed"
  return 1
}
