#!/bin/bash
# legacy-discovery.sh — 旧版本谱系识别与迁移清单输出

legacy_detect_generation() {
  if legacy_service_root_dir >/dev/null 2>&1; then
    echo "legacy-v1"
    return 0
  fi
  if legacy_resolve_volume_for_role apphub_media >/dev/null 2>&1; then
    echo "legacy-v2"
    return 0
  fi
  if _detect_legacy_strong; then
    echo "legacy-v3"
    return 0
  fi
  echo "legacy-unknown"
}

legacy_collect_containers() {
  local name
  for name in "${LEGACY_CONTAINER_CANDIDATES[@]}"; do
    container_exists "$name" && echo "$name"
  done
}

legacy_collect_role_mappings() {
  local role resolved
  for role in "${LEGACY_VOLUME_ROLES[@]}"; do
    resolved="$(legacy_resolve_volume_for_role "$role" 2>/dev/null || true)"
    [ -n "$resolved" ] && printf '%s=%s\n' "$role" "$resolved"
  done
}

legacy_resolved_volume_mountpoint() {
  local role resolved
  resolved="$(legacy_resolve_volume_for_role "$1" 2>/dev/null || true)"
  [ -n "$resolved" ] || return 1
  docker volume inspect --format '{{ .Mountpoint }}' "$resolved" 2>/dev/null
}

legacy_find_config_candidates() {
  local root file
  for root in /data /legacy/apphub_config; do
    [ -d "$root" ] || continue
    while IFS= read -r file; do
      [ -n "$file" ] && echo "$file"
    done < <(find "$root" -name config.ini -type f 2>/dev/null)
  done
  local extra
  extra="$(legacy_service_root_dir 2>/dev/null || true)"
  if [ -n "$extra" ]; then
    find "$extra" -name config.ini -type f 2>/dev/null || true
  fi
  extra="$(legacy_download_root_dir 2>/dev/null || true)"
  if [ -n "$extra" ]; then
    find "$extra" -name config.ini -type f 2>/dev/null || true
  fi
}

legacy_find_system_ini_candidates() {
  local root file
  for root in /data /legacy/apphub_config; do
    [ -d "$root" ] || continue
    while IFS= read -r file; do
      [ -n "$file" ] && echo "$file"
    done < <(find "$root" -name system.ini -type f 2>/dev/null)
  done
  local extra
  extra="$(legacy_service_root_dir 2>/dev/null || true)"
  if [ -n "$extra" ]; then
    find "$extra" -name system.ini -type f 2>/dev/null || true
  fi
  extra="$(legacy_download_root_dir 2>/dev/null || true)"
  if [ -n "$extra" ]; then
    find "$extra" -name system.ini -type f 2>/dev/null || true
  fi
}

legacy_count_gitea_repositories() {
  local mountpoint repo_root
  mountpoint="$(legacy_resolved_volume_mountpoint gitea 2>/dev/null || true)"
  [ -n "$mountpoint" ] || { echo 0; return 0; }

  for repo_root in "$mountpoint/git/repositories" "$mountpoint/repositories"; do
    if [ -d "$repo_root" ]; then
      find "$repo_root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | awk '{print $1}'
      return 0
    fi
  done
  echo 0
}

legacy_count_npm_proxy_hosts() {
  local mountpoint db_path
  mountpoint="$(legacy_resolved_volume_mountpoint nginx_data 2>/dev/null || true)"
  [ -n "$mountpoint" ] || { echo 0; return 0; }
  db_path="${mountpoint}/database.sqlite"
  [ -f "$db_path" ] || { echo 0; return 0; }

  NPM_DB_PATH="$db_path" python3 - <<'PY'
import os
import sqlite3

db_path = os.environ.get("NPM_DB_PATH", "")
if not db_path:
    print(0)
    raise SystemExit(0)

try:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM proxy_host").fetchone()
    print(int(row[0] if row else 0))
except Exception:
    print(0)
finally:
    try:
        conn.close()
    except Exception:
        pass
PY
}

legacy_count_host_compose_entries() {
  local path
  path="$(legacy_host_compose_dir 2>/dev/null || true)"
  [ -n "$path" ] || { echo 0; return 0; }
  find "$path" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l | awk '{print $1}'
}

legacy_password_sidefile_exists() {
  [ -f /usr/password.txt ] && echo true || echo false
}

legacy_write_manifest() {
  local output_dir="$1"
  local manifest_path="${output_dir}/legacy-manifest.json"
  local generation host_compose service_root download_root containers role_mappings config_candidates system_ini_candidates gitea_repo_count npm_proxy_count host_compose_entries password_sidefile_exists

  generation="$(legacy_detect_generation)"
  host_compose="$(legacy_host_compose_dir 2>/dev/null || true)"
  service_root="$(legacy_service_root_dir 2>/dev/null || true)"
  download_root="$(legacy_download_root_dir 2>/dev/null || true)"
  containers="$(legacy_collect_containers)"
  role_mappings="$(legacy_collect_role_mappings)"
  config_candidates="$(legacy_find_config_candidates | awk '!seen[$0]++')"
  system_ini_candidates="$(legacy_find_system_ini_candidates | awk '!seen[$0]++')"
  gitea_repo_count="$(legacy_count_gitea_repositories)"
  npm_proxy_count="$(legacy_count_npm_proxy_hosts)"
  host_compose_entries="$(legacy_count_host_compose_entries)"
  password_sidefile_exists="$(legacy_password_sidefile_exists)"

  run_cmd mkdir -p "$output_dir"

  LEGACY_MANIFEST_PATH="$manifest_path" \
  LEGACY_GENERATION="$generation" \
  LEGACY_HOST_COMPOSE="$host_compose" \
  LEGACY_SERVICE_ROOT="$service_root" \
  LEGACY_DOWNLOAD_ROOT="$download_root" \
  LEGACY_CONTAINERS="$containers" \
  LEGACY_ROLE_MAPPINGS="$role_mappings" \
  LEGACY_CONFIG_CANDIDATES="$config_candidates" \
  LEGACY_SYSTEM_INI_CANDIDATES="$system_ini_candidates" \
  LEGACY_GITEA_REPO_COUNT="$gitea_repo_count" \
  LEGACY_NPM_PROXY_COUNT="$npm_proxy_count" \
  LEGACY_HOST_COMPOSE_ENTRIES="$host_compose_entries" \
  LEGACY_PASSWORD_SIDEFILE_EXISTS="$password_sidefile_exists" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

def lines(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [line.strip() for line in raw.splitlines() if line.strip()]

role_map = {}
for item in lines("LEGACY_ROLE_MAPPINGS"):
    key, _, value = item.partition("=")
    if key and value:
        role_map[key] = value

payload = {
    "generation": os.environ.get("LEGACY_GENERATION", "legacy-unknown"),
    "containers": lines("LEGACY_CONTAINERS"),
    "volumes_by_role": role_map,
    "host_paths": {
        "compose": os.environ.get("LEGACY_HOST_COMPOSE", ""),
        "service_root": os.environ.get("LEGACY_SERVICE_ROOT", ""),
        "download_root": os.environ.get("LEGACY_DOWNLOAD_ROOT", ""),
    },
    "config_candidates": lines("LEGACY_CONFIG_CANDIDATES"),
    "system_ini_candidates": lines("LEGACY_SYSTEM_INI_CANDIDATES"),
    "snapshot": {
      "gitea_repository_roots": int(os.environ.get("LEGACY_GITEA_REPO_COUNT", "0") or 0),
      "npm_proxy_hosts": int(os.environ.get("LEGACY_NPM_PROXY_COUNT", "0") or 0),
      "host_compose_entries": int(os.environ.get("LEGACY_HOST_COMPOSE_ENTRIES", "0") or 0),
      "password_sidefile_exists": os.environ.get("LEGACY_PASSWORD_SIDEFILE_EXISTS", "false").lower() == "true",
    },
}

path = Path(os.environ["LEGACY_MANIFEST_PATH"])
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

  log_info "Legacy manifest created: $manifest_path"
}