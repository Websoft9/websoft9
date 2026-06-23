#!/bin/bash
# upgrade-legacy.sh — 旧版到新版迁移路径（§7）
# 职责：legacy 环境的跨代迁移（控制面替换 + 卷确定性结构转换 + 凭据合成 + 内置对账）。
# 不负责：modern 环境、未知历史变种的自动迁移。
#
# 8 阶段（§7.6）：识别 -> 备份 -> 停旧运行时释放端口 -> 卷结构转换 ->
#                 凭据合成 -> 启动接管 -> 验证 -> 收口

# --- 阶段 3：停旧运行时，释放 80/443/9000 并停止旧卷写入者（stop-only，可回退）---
_legacy_stop_runtime() {
  log_step "停止旧版运行时（释放 80/443/9000，不删除，便于回退）"

  # 停旧 compose 项目（容器名固定，逐个停）
  local name
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    if container_running "$name"; then
      run_cmd docker stop "$name" || log_warn "停止容器失败: $name"
    fi
  done

  # 停旧 systemd 控制面（仅停止，不 disable / 不删除）
  if command_exists systemctl; then
    local unit
    for unit in "${LEGACY_SYSTEMD_UNITS[@]}"; do
      if systemd_unit_present "$unit"; then
        run_cmd systemctl stop "$unit" 2>/dev/null || log_warn "停止 systemd 单元失败: $unit"
      fi
    done
  fi
}

# 生成卷结构转换脚本到临时文件（在 alpine 内执行）
_legacy_write_transform_script() {
  local script_path="$1"
  cat >"$script_path" <<'TRANSFORM'
#!/bin/sh
set -e
log() { echo "[transform] $*"; }

# 极简 ini 取值：ini_get <file> <section> <key>
ini_get() {
  f="$1"; sect="$2"; key="$3"
  [ -f "$f" ] || return 0
  awk -v s="[$sect]" -v k="$key" '
    $0==s {ins=1; next}
    /^\[/ {ins=0}
    ins && $0 ~ "^[ \t]*"k"[ \t]*=" {
      sub("^[ \t]*"k"[ \t]*=[ \t]*","",$0); print $0; exit
    }' "$f"
}

# 取 app.ini 中某 key 的值（无 section 限定，用于 SECRET_KEY/INTERNAL_TOKEN）
ini_get_any() {
  f="$1"; key="$2"
  [ -f "$f" ] || return 0
  awk -v k="$key" '$0 ~ "^[ \t]*"k"[ \t]*=" { sub("^[ \t]*"k"[ \t]*=[ \t]*","",$0); print $0; exit }' "$f"
}

mkdir -p /data

# ---------------- NPM (nginx_data) ----------------
if [ -d /legacy/nginx_data ]; then
  log "迁移 NPM 数据库与 nginx 配置（排除 logs/）"
  [ -f /legacy/nginx_data/database.sqlite ] && cp -a /legacy/nginx_data/database.sqlite /data/database.sqlite || true
  if [ -d /legacy/nginx_data/nginx ]; then
    mkdir -p /data/nginx
    cp -a /legacy/nginx_data/nginx/. /data/nginx/ 2>/dev/null || true
  fi
  # 证书：保留原始绝对路径 /data/custom_ssl 以维持 DB 内引用有效（best-effort）
  if [ -d /legacy/nginx_data/custom_ssl ]; then
    mkdir -p /data/custom_ssl /data/nginx-proxy-manager/custom_ssl
    cp -a /legacy/nginx_data/custom_ssl/. /data/custom_ssl/ 2>/dev/null || true
    cp -a /legacy/nginx_data/custom_ssl/. /data/nginx-proxy-manager/custom_ssl/ 2>/dev/null || true
  fi
  [ -d /legacy/nginx_data/letsencrypt ] && { mkdir -p /data/letsencrypt; cp -a /legacy/nginx_data/letsencrypt/. /data/letsencrypt/ 2>/dev/null || true; } || true
fi
# 独立 letsencrypt 卷（旧 /etc/letsencrypt）best-effort 搬入 /data/letsencrypt
if [ -d /legacy/nginx_letsencrypt ]; then
  log "迁移 letsencrypt 证书目录（best-effort）"
  mkdir -p /data/letsencrypt
  cp -a /legacy/nginx_letsencrypt/. /data/letsencrypt/ 2>/dev/null || true
fi

# ---------------- Gitea ----------------
# 旧卷布局（挂载于旧 /data）：/legacy/gitea/gitea（app+conf+db），/legacy/gitea/git（repos/lfs）
if [ -d /legacy/gitea ]; then
  log "迁移 Gitea（路径重映射，保留 SECRET_KEY/INTERNAL_TOKEN）"
  old_g="/legacy/gitea/gitea"
  old_git="/legacy/gitea/git"
  mkdir -p /data/gitea/conf /data/gitea/data /data/gitea/git /data/gitea/log

  # 数据库
  [ -f "$old_g/gitea.db" ] && cp -a "$old_g/gitea.db" /data/gitea/gitea.db || true

  # 仓库与 lfs
  [ -d "$old_git/repositories" ] && cp -a "$old_git/repositories" /data/gitea/git/ 2>/dev/null || true
  [ -d "$old_git/lfs" ] && cp -a "$old_git/lfs" /data/gitea/git/ 2>/dev/null || true

  # 应用数据（avatars/attachments 等）搬入新 APP_DATA_PATH=/data/gitea/data
  if [ -d "$old_g" ]; then
    for sub in avatars repo-avatars attachments packages actions_log actions_artifacts queues sessions indexers; do
      [ -e "$old_g/$sub" ] && cp -a "$old_g/$sub" /data/gitea/data/ 2>/dev/null || true
    done
    # 已是 data/ 子目录布局的旧版直接合并
    [ -d "$old_g/data" ] && cp -a "$old_g/data/." /data/gitea/data/ 2>/dev/null || true
  fi

  # 重建 app.ini：新路径 + 旧密钥
  old_ini="$old_g/conf/app.ini"
  SECRET_KEY="$(ini_get_any "$old_ini" SECRET_KEY)"
  INTERNAL_TOKEN="$(ini_get_any "$old_ini" INTERNAL_TOKEN)"
  [ -z "$SECRET_KEY" ] && SECRET_KEY="$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  [ -z "$INTERNAL_TOKEN" ] && INTERNAL_TOKEN="$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  cat >/data/gitea/conf/app.ini <<EOF
[server]
APP_DATA_PATH = /data/gitea/data
DOMAIN = 127.0.0.1
HTTP_PORT = 3001
DISABLE_SSH = true
SSH_DOMAIN = 127.0.0.1

[database]
DB_TYPE = sqlite3
PATH = /data/gitea/gitea.db

[security]
INSTALL_LOCK = true
SECRET_KEY = $SECRET_KEY
INTERNAL_TOKEN = $INTERNAL_TOKEN
PASSWORD_HASH_ALGO = pbkdf2

[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = false

[repository]
ROOT = /data/gitea/git/repositories

[lfs]
PATH = /data/gitea/git/lfs

[log]
ROOT_PATH = /data/gitea/log
EOF
fi

# ---------------- Portainer ----------------
if [ -d /legacy/portainer ]; then
  log "迁移 Portainer 数据（启动自迁移 bolt db）"
  mkdir -p /data/portainer
  cp -a /legacy/portainer/. /data/portainer/ 2>/dev/null || true
fi

# ---------------- /data/compose（宿主机 bind -> 命名卷）----------------
if [ -d /legacy/host-compose ]; then
  log "迁移宿主机 /data/compose 到命名卷内 /data/compose"
  mkdir -p /data/compose
  cp -a /legacy/host-compose/. /data/compose/ 2>/dev/null || true
fi

# ---------------- 旧 apphub 日志（归档，低优先）----------------
if [ -d /legacy/apphub_logs ]; then
  mkdir -p /data/logs/legacy-apphub
  cp -a /legacy/apphub_logs/. /data/logs/legacy-apphub/ 2>/dev/null || true
fi

# ---------------- 凭据合成（从旧 apphub config.ini）----------------
cfg=""
sysini=""
for root in /legacy/apphub_config /legacy/service-root /legacy/download-root; do
  [ -d "$root" ] || continue
  [ -z "$cfg" ] && cfg="$(find "$root" -name config.ini -type f 2>/dev/null | head -n1)"
  [ -z "$sysini" ] && sysini="$(find "$root" -name system.ini -type f 2>/dev/null | head -n1)"
done
[ -n "$sysini" ] && { mkdir -p /data/.w9-migration; cp -a "$sysini" /data/.w9-migration/system.ini; } || true

if [ -n "$cfg" ] && [ -f "$cfg" ]; then
  log "合成第三方凭据文件（用旧密码对账）"

  g_user="$(ini_get "$cfg" gitea user_name)"
  g_pwd="$(ini_get "$cfg" gitea user_pwd)"
  g_email="$(ini_get "$cfg" gitea user_email)"
  if [ -n "$g_pwd" ]; then
    mkdir -p /data/gitea
    printf '{"username":"%s","email":"%s","password":"%s"}\n' \
      "${g_user:-websoft9}" "${g_email:-admin@mydomain.com}" "$g_pwd" >/data/gitea/credential
    chmod 600 /data/gitea/credential || true
  fi

  p_pwd="$(ini_get "$cfg" portainer user_pwd)"
  if [ -n "$p_pwd" ]; then
    mkdir -p /data/portainer
    printf '%s' "$p_pwd" >/data/portainer/credential
    chmod 600 /data/portainer/credential || true
  fi

  n_user="$(ini_get "$cfg" nginx_proxy_manager user_name)"
  n_pwd="$(ini_get "$cfg" nginx_proxy_manager user_pwd)"
  n_nick="$(ini_get "$cfg" nginx_proxy_manager nike_name)"
  if [ -n "$n_pwd" ]; then
    mkdir -p /data/nginx-proxy-manager
    printf '{"username":"%s","password":"%s","nickname":"%s","display_name":"%s"}\n' \
      "${n_user:-admin}" "$n_pwd" "${n_nick:-admin}" "${n_nick:-admin}" >/data/nginx-proxy-manager/credential.json
    chmod 600 /data/nginx-proxy-manager/credential.json || true
  fi

  # api_key 抽取（归档到迁移暂存，供后续按需接续，不强行注入运行时）
  api_key="$(ini_get "$cfg" api_key key)"
  if [ -n "$api_key" ]; then
    mkdir -p /data/.w9-migration
    printf '%s' "$api_key" >/data/.w9-migration/legacy-api-key
  fi
fi

log "卷结构转换与凭据合成完成"
TRANSFORM
}

# --- 阶段 4 + 5：卷结构转换 + 凭据合成（单 alpine 容器内完成）---
_legacy_transform_volumes() {
  local install_path="$1"
  log_step "卷结构转换 + 凭据合成"

  local data_root
  data_root="$(resolve_runtime_data_root "$install_path")"
  run_cmd mkdir -p "$data_root"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过实际卷转换"
    return 0
  fi

  local tmpdir
  tmpdir="$(mktemp -d)"
  _legacy_write_transform_script "${tmpdir}/transform.sh"

  # 动态拼装存在的旧卷挂载
  local mounts=(-v "${data_root}:/data" -v "${tmpdir}:/w9script:ro")
  _add_ro_volume() {
    local resolved
    resolved="$(legacy_resolve_volume_for_role "$1" 2>/dev/null || true)"
    [ -n "$resolved" ] && mounts+=(-v "$resolved:/legacy/$2:ro")
  }
  _add_ro_volume nginx_data        nginx_data
  _add_ro_volume nginx_letsencrypt nginx_letsencrypt
  _add_ro_volume gitea             gitea
  _add_ro_volume portainer         portainer
  _add_ro_volume apphub_config     apphub_config
  _add_ro_volume apphub_logs       apphub_logs
  _add_ro_volume apphub_media      apphub_media
  local host_compose_dir service_root_dir download_root_dir
  host_compose_dir="$(legacy_host_compose_dir 2>/dev/null || true)"
  service_root_dir="$(legacy_service_root_dir 2>/dev/null || true)"
  download_root_dir="$(legacy_download_root_dir 2>/dev/null || true)"
  if [ -n "$host_compose_dir" ]; then
    mounts+=(-v "${host_compose_dir}:/legacy/host-compose:ro")
  fi
  if [ -n "$service_root_dir" ]; then
    mounts+=(-v "${service_root_dir}:/legacy/service-root:ro")
  fi
  if [ -n "$download_root_dir" ]; then
    mounts+=(-v "${download_root_dir}:/legacy/download-root:ro")
  fi

  if ! docker run --rm "${mounts[@]}" alpine:3.20 sh /w9script/transform.sh; then
    rm -rf "$tmpdir"
    die "$EXIT_RUNTIME" "卷结构转换失败"
  fi
  rm -rf "$tmpdir"
}

# --- 阶段 8 收口：产品版本/edition 接续（从旧 system.ini 推断）---
_legacy_finalize_product_state() {
  log_step "产品状态接续（旧 system.ini -> edition/version）"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 跳过产品状态接续"
    return 0
  fi
  if ! container_running "$MODERN_CONTAINER_NAME"; then
    log_warn "容器未运行，跳过产品状态接续"
    return 0
  fi
  # system.ini 已由转换阶段放入 /data/.w9-migration/system.ini
  docker exec "$MODERN_CONTAINER_NAME" sh -c '
    set -e
    if [ -f /data/.w9-migration/system.ini ]; then
      python3 -c "import sys; sys.path.insert(0,\"/websoft9/apphub\"); from src.services.product_metadata import migrate_product_metadata; from src.services.product_runtime_state import read_release_version; migrate_product_metadata(version=read_release_version(), legacy_system_ini_file=\"/data/.w9-migration/system.ini\")" || echo "[w9] product state migration best-effort failed"
    fi
  ' 2>/dev/null || log_warn "产品状态接续为 best-effort，未阻塞迁移"
}

# 迁移主流程
run_upgrade_legacy() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"

  log_info "==== 旧版到新版迁移开始 (legacy) ===="
  require_root

  # 阶段 1：识别已在入口完成；此处确认无现代强信号
  if _detect_modern_strong; then
    die "$EXIT_ENV_GUARD" "检测到现代运行时，疑似 mixed，迁移路径拒绝执行"
  fi

  # 阶段 2：迁移前备份（强制，不受 --keep-data 影响）
  local backup_dir
  backup_dir="$(backup_new_dir legacy-migration)"
  legacy_write_manifest "$backup_dir"
  backup_legacy_pre_migration "$backup_dir"

  # 阶段 3：停旧运行时释放端口
  _legacy_stop_runtime

  # 阶段 4 + 5：卷结构转换 + 凭据合成
  _legacy_transform_volumes "$install_path"

  # 准备现代部署物料（不覆盖已转换的宿主机数据根）
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) 迁移前置（识别/备份/停旧/转换/物料）完成，停止于启动接管前"
    log_info "迁移前备份点: $backup_dir"
    return 0
  fi

  # 阶段 6：启动接管
  log_step "启动现代运行时接管"
  if ! pull_image_with_mirrors "$install_path"; then
    die "$EXIT_RUNTIME" "迁移失败（镜像拉取）；旧运行时未删除，可人工回退。备份: $backup_dir"
  fi
  if ! modern_compose "$install_path" up -d; then
    die "$EXIT_RUNTIME" "迁移失败（容器启动）；旧运行时未删除，可人工回退。备份: $backup_dir"
  fi

  # 阶段 8（部分）：产品状态接续（须在校验前，使版本/edition 就绪）
  _legacy_finalize_product_state

  # 阶段 7：验证
  if ! validate_upgrade "$console_port"; then
    log_error "迁移后验证未通过"
    log_warn "旧运行时与旧卷均未删除，迁移前备份点保留: $backup_dir"
    log_warn "可停止现代容器并重启旧 systemd/容器进行人工回退"
    die "$EXIT_VALIDATE" "迁移失败（迁移后校验）"
  fi

  # 阶段 8：收口
  log_info "==== 旧版到新版迁移成功 ===="
  log_info "迁移前备份点保留于: $backup_dir"
  log_warn "旧 Cockpit / systemd / 旧容器与旧卷默认保留停用；回退窗口关闭后可用 uninstall 的独立清理开关处理。"
}
