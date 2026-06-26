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
    # If the compose file uses a variable (e.g. ${CONTAINER_NAME:-websoft9}), strip it to the default
    name="${name#\$\{CONTAINER_NAME:-}"
    name="${name%\}}"
  fi
  echo "${name:-$MODERN_CONTAINER_NAME}"
}

# compose 默认环境变量（与 docker-compose.yml 的 ${VAR:-default} 一致）
DEFAULT_IMAGE_REPO="websoft9dev/websoft9"
DEFAULT_IMAGE_TAG="latest"
DEFAULT_NETWORK_NAME="websoft9"
DEFAULT_CONSOLE_PORT="9000"
DEFAULT_INSTALL_PATH="/opt/websoft9"
DEFAULT_WEBSOFT9_DATA_ROOT="/opt/websoft9/data"

# 制品分发根（单文件 install.sh 在无本地物料时从此处按通道下载部署物料）
DEFAULT_ARTIFACT_BASE="https://artifact.websoft9.com/websoft9"

# ---------------------------------------------------------------------------
# 旧版（Cockpit 多容器时代）运行时事实
# ---------------------------------------------------------------------------
LEGACY_CONTAINER_NAMES=(websoft9-apphub websoft9-deployment websoft9-git websoft9-proxy)
LEGACY_CONTAINER_CANDIDATES=(websoft9-apphub websoft9-deployment websoft9-git websoft9-proxy websoft9-appmanage websoft9-portainer websoft9-gitea websoft9-nginxproxymanager websoft9-redis)
LEGACY_VOLUME_NAMES=(apphub_logs apphub_media apphub_config apphub_data portainer gitea nginx_data nginx_letsencrypt nginx_modsec nginx_var)
LEGACY_VOLUME_ROLES=(apphub_logs apphub_media apphub_config apphub_data portainer gitea nginx_data nginx_letsencrypt nginx_modsec nginx_var)
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

# dry-run 感知执行：W9_DRY_RUN=1 时只打印不执行
run_cmd() {
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) $*"
    return 0
  fi
  "$@"
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
    apphub_data) printf '%s\n' apphub_data w9appmanage_data websoft9_apphub_data websoft9_data ;; 
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
  local candidates=(
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
  local image_repo="$2"
  local image_tag="$3"
  local network_name="$4"
  local console_port="$5"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) writing .env -> $env_path"
    return 0
  fi

  cat >"$env_path" <<EOF
# Generated by Websoft9 installer on $(_w9_ts)
IMAGE_REPO=${image_repo}
IMAGE_TAG=${image_tag}
NETWORK_NAME=${network_name}
CONSOLE_PORT=${console_port}
CONTAINER_NAME=${CONTAINER_NAME}
WEBSOFT9_DATA_ROOT=${WEBSOFT9_DATA_ROOT:-$DEFAULT_WEBSOFT9_DATA_ROOT}
EOF
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

  if [ -z "$data_root" ] && [ -f "$env_file" ]; then
    data_root="$(grep -m1 '^WEBSOFT9_DATA_ROOT=' "$env_file" 2>/dev/null | cut -d= -f2-)"
  fi
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
  # (/opt/websoft9/data) so that all Websoft9 data lives under one clean
  # directory.  The Alpine transform container receives ${data_root}:/data
  # so writes to /data inside the container land on the new host path.
  if _runtime_data_root_has_modern_markers /data; then
    echo "$DEFAULT_WEBSOFT9_DATA_ROOT"
    return 0
  fi

  if _runtime_data_root_has_modern_markers "$DEFAULT_WEBSOFT9_DATA_ROOT"; then
    echo "$DEFAULT_WEBSOFT9_DATA_ROOT"
    return 0
  fi

  # Legacy install with compose workspace only — migrate to new default.
  if [ "$include_legacy_fallback" = "1" ] && [ -d "$LEGACY_HOST_COMPOSE_DIR" ]; then
    echo "$DEFAULT_WEBSOFT9_DATA_ROOT"
    return 0
  fi

  echo "$DEFAULT_WEBSOFT9_DATA_ROOT"
}

resolve_runtime_data_root() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local env_file="${install_path}/.env"
  local data_root="${WEBSOFT9_DATA_ROOT:-}"
  if [ -z "$data_root" ] && [ -f "$env_file" ]; then
    data_root="$(grep -m1 '^WEBSOFT9_DATA_ROOT=' "$env_file" 2>/dev/null | cut -d= -f2-)"
  fi
  echo "${data_root:-$DEFAULT_WEBSOFT9_DATA_ROOT}"
}

resolve_modern_compose_project() {
  local install_path="${1:-$DEFAULT_INSTALL_PATH}"
  local env_file="${install_path}/.env"
  local container_name="${CONTAINER_NAME:-}"

  if [ -z "$container_name" ] && [ -f "$env_file" ]; then
    container_name="$(grep -m1 '^CONTAINER_NAME=' "$env_file" 2>/dev/null | cut -d= -f2-)"
  fi

  case "${container_name:-}" in
    websoft9-dev) echo "websoft9-dev" ;;
    websoft9-rc) echo "websoft9-rc" ;;
    *) echo "$MODERN_COMPOSE_PROJECT" ;;
  esac
}

ensure_shared_network() {
  local network_name="${1:-$DEFAULT_NETWORK_NAME}"
  if docker network inspect "$network_name" >/dev/null 2>&1; then
    log_info "Reusing shared Docker network: $network_name"
    return 0
  fi
  log_step "Creating shared Docker network: $network_name"
  run_cmd docker network create "$network_name" >/dev/null
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

  if [ "$had_original" -eq 1 ]; then
    cp -a "$backup_file" "$daemon_file"
  else
    rm -f "$daemon_file"
  fi
  rm -f "$backup_file"

  if ! restart_docker_service; then
    log_error "Failed to restore the original Docker daemon configuration"
    restore_status=1
  fi

  if [ "$restore_status" -ne 0 ]; then
    return 1
  fi

  return "$pull_status"
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
    image_repo="$(grep -m1 '^IMAGE_REPO=' "$env_file" 2>/dev/null | cut -d= -f2-)"
    image_tag="$(grep -m1 '^IMAGE_TAG=' "$env_file" 2>/dev/null | cut -d= -f2-)"
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
