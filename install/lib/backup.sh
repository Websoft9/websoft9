#!/bin/bash
# backup.sh — 备份与回退层（§6.2 / §6.4 / §7.6）
# 职责：配置、卷、镜像标签、部署物料与入口相关备份与恢复。
# 不负责：决定业务路径或升级策略。

# 备份根目录
W9_BACKUP_ROOT="${W9_BACKUP_ROOT:-/var/lib/websoft9/backups}"

# 生成一个新的备份目录路径（不创建内容，仅返回路径）
backup_new_dir() {
  local tag="${1:-backup}"
  echo "${W9_BACKUP_ROOT}/${tag}-$(date +%Y%m%d%H%M%S)"
}

# 备份安装目录下的部署物料（.env / docker-compose.yml）与当前镜像标签
backup_modern_material() {
  local install_path="$1"
  local backup_dir="$2"

  run_cmd mkdir -p "$backup_dir"

  if [ -f "${install_path}/.env" ]; then
    run_cmd cp -a "${install_path}/.env" "${backup_dir}/.env"
  fi
  if [ -f "${install_path}/docker-compose.yml" ]; then
    run_cmd cp -a "${install_path}/docker-compose.yml" "${backup_dir}/docker-compose.yml"
  fi

  # 记录当前运行容器的镜像引用，便于回退到旧镜像
  if container_exists "$MODERN_CONTAINER_NAME"; then
    local image_ref
    image_ref="$(docker inspect --format '{{.Config.Image}}' "$MODERN_CONTAINER_NAME" 2>/dev/null)"
    if [ -n "$image_ref" ]; then
      if [ "${W9_DRY_RUN:-0}" = "1" ]; then
        log_info "(dry-run) recording image ref ${image_ref} -> ${backup_dir}/image-ref.txt"
      else
        echo "$image_ref" >"${backup_dir}/image-ref.txt"
      fi
    fi
  fi

  log_info "Deployment material and image ref backed up to: $backup_dir"
}

# 备份一个命名卷到 backup_dir 下的 tar（通过临时容器）
backup_volume() {
  local volume_name="$1"
  local backup_dir="$2"
  if ! volume_exists "$volume_name"; then
    log_warn "Volume not found, skipping backup: $volume_name"
    return 0
  fi
  run_cmd mkdir -p "$backup_dir"
  log_step "Backing up volume: $volume_name"
  run_cmd docker run --rm \
    -v "${volume_name}:/w9src:ro" \
    -v "${backup_dir}:/w9backup" \
    alpine:3.20 \
    sh -c "cd /w9src && tar czf /w9backup/${volume_name}.tar.gz ."
}

# 从备份 tar 恢复一个命名卷（覆盖式）
restore_volume() {
  local volume_name="$1"
  local backup_dir="$2"
  local archive="${backup_dir}/${volume_name}.tar.gz"
  if [ ! -f "$archive" ]; then
    log_warn "Volume backup not found, skipping restore: $archive"
    return 1
  fi
  run_cmd docker volume create "$volume_name" >/dev/null
  log_step "Restoring volume: $volume_name"
  run_cmd docker run --rm \
    -v "${volume_name}:/w9dst" \
    -v "${backup_dir}:/w9backup:ro" \
    alpine:3.20 \
    sh -c "cd /w9dst && rm -rf ./* && tar xzf /w9backup/${volume_name}.tar.gz"
}

# 升级前现代备份点：物料 + 主数据卷
backup_modern_pre_upgrade() {
  local install_path="$1"
  local backup_dir="$2"
  backup_modern_material "$install_path" "$backup_dir"
  backup_volume "$MODERN_DATA_VOLUME" "$backup_dir"
  log_info "Pre-upgrade backup created: $backup_dir"
}

# 迁移前旧版备份点：所有旧卷 + 旧宿主机 compose 目录
backup_legacy_pre_migration() {
  local backup_dir="$1"
  run_cmd mkdir -p "$backup_dir"
  local v
  for v in "${LEGACY_VOLUME_NAMES[@]}"; do
    backup_volume "$v" "$backup_dir"
  done
  if [ -d "$LEGACY_HOST_COMPOSE_DIR" ]; then
    log_step "Backing up legacy host compose dir: $LEGACY_HOST_COMPOSE_DIR"
    run_cmd tar czf "${backup_dir}/host-compose.tar.gz" -C "$(dirname "$LEGACY_HOST_COMPOSE_DIR")" "$(basename "$LEGACY_HOST_COMPOSE_DIR")"
  fi
  log_info "Pre-migration legacy backup created: $backup_dir"
}
