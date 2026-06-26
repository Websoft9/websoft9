#!/bin/bash
# upgrade-legacy.sh - legacy-to-modern migration flow (§7)
# Scope: cross-generation migration for legacy environments (control-plane cutover,
# deterministic data transform, credential synthesis, built-in reconciliation).
# Out of scope: modern upgrades and unknown historical variants.

# Stage 3: stop the legacy runtime, free 80/443/9000, and stop legacy writers.
_legacy_stop_runtime() {
  log_step "Stopping legacy runtime writers and freeing 80/443/9000"

  # Stop legacy containers one by one.
  local name
  for name in "${LEGACY_CONTAINER_NAMES[@]}"; do
    if container_running "$name"; then
      run_cmd docker stop "$name" || log_warn "Failed to stop legacy container: $name"
    fi
  done

  # Stop legacy systemd control-plane units without removing them yet.
  if command_exists systemctl; then
    local unit
    for unit in "${LEGACY_SYSTEMD_UNITS[@]}"; do
      if systemd_unit_present "$unit"; then
        run_cmd systemctl stop "$unit" 2>/dev/null || log_warn "Failed to stop legacy systemd unit: $unit"
      fi
    done
  fi
}

_legacy_read_console_port_from_socket() {
  local candidate
  for candidate in \
    /etc/systemd/system/cockpit.socket \
    /usr/lib/systemd/system/cockpit.socket \
    /lib/systemd/system/cockpit.socket
  do
    [ -f "$candidate" ] || continue
    sed -nE 's|^[[:space:]]*ListenStream=([0-9]+)[[:space:]]*$|\1|p' "$candidate" | head -n 1
    return 0
  done
  return 0
}

_legacy_is_proxy_fronted_platform() {
  local cockpit_conf="/etc/cockpit/cockpit.conf"
  [ -f "$cockpit_conf" ] || return 1
  grep -q "Origins" "$cockpit_conf"
}

_legacy_read_platform_entry_port_from_config() {
  local candidate
  for candidate in \
    /data/apps/websoft9/apphub/src/config/config.ini \
    /data/websoft9/apphub/src/config/config.ini \
    /opt/websoft9/apphub/src/config/config.ini \
    /usr/share/websoft9/apphub/src/config/config.ini
  do
    [ -f "$candidate" ] || continue
    awk '
      $0=="[nginx_proxy_manager]" {section="nginx_proxy_manager"; next}
      $0=="[platform_gateway]" {section="platform_gateway"; next}
      /^\[/ {section=""}
      section=="nginx_proxy_manager" && $0 ~ /^[[:space:]]*listen_port[[:space:]]*=/ {
        sub(/^[[:space:]]*listen_port[[:space:]]*=[[:space:]]*/, "", $0)
        gsub(/[[:space:]]+$/, "", $0)
        print $0
        exit
      }
      section=="platform_gateway" && $0 ~ /^[[:space:]]*listen_port[[:space:]]*=/ {
        sub(/^[[:space:]]*listen_port[[:space:]]*=[[:space:]]*/, "", $0)
        gsub(/[[:space:]]+$/, "", $0)
        print $0
        exit
      }
    ' "$candidate" | head -n 1
    return 0
  done
  return 0
}

_legacy_resolve_console_port() {
  local requested_port="$1"
  local resolved_port="${requested_port:-$DEFAULT_CONSOLE_PORT}"

  if [ "${W9_CONSOLE_PORT_EXPLICIT:-0}" = "1" ]; then
    echo "$resolved_port"
    return 0
  fi

  if [ -n "$requested_port" ] && [ "$requested_port" != "$DEFAULT_CONSOLE_PORT" ]; then
    echo "$requested_port"
    return 0
  fi

  local legacy_socket_port legacy_config_port
  legacy_socket_port="$(_legacy_read_console_port_from_socket)"
  legacy_config_port="$(_legacy_read_platform_entry_port_from_config)"

  if _legacy_is_proxy_fronted_platform; then
    if [ -n "$legacy_config_port" ]; then
      echo "$legacy_config_port"
      return 0
    fi
    echo "$resolved_port"
    return 0
  fi

  if [ -n "$legacy_socket_port" ]; then
    echo "$legacy_socket_port"
    return 0
  fi

  if [ -n "$legacy_config_port" ]; then
    echo "$legacy_config_port"
    return 0
  fi

  echo "$resolved_port"
}

# Render the transform script executed inside the one-shot Alpine worker.
_legacy_write_transform_script() {
  local script_path="$1"
  cat >"$script_path" <<'TRANSFORM'
#!/bin/sh
set -e
ts() { date +"%Y-%m-%d %H:%M:%S"; }
log_step() { echo "[transform][$(ts)][STEP ] $*"; }
log_info() { echo "[transform][$(ts)][INFO ] $*"; }

# Minimal INI reader: ini_get <file> <section> <key>
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

# Read an app.ini key without constraining the section.
ini_get_any() {
  f="$1"; key="$2"
  [ -f "$f" ] || return 0
  awk -v k="$key" '$0 ~ "^[ \t]*"k"[ \t]*=" { sub("^[ \t]*"k"[ \t]*=[ \t]*","",$0); print $0; exit }' "$f"
}

is_primary_legacy_config() {
  f="$1"
  [ -f "$f" ] || return 1
  grep -Eq '^\[(platform_gateway|docker_mirror|nginx_proxy_manager|portainer|favorite_apps|domain)\]' "$f"
}

pick_legacy_config() {
  for root in "$@"; do
    [ -d "$root" ] || continue
    for candidate in \
      "$root/apphub/src/config/config.ini" \
      "$root/src/config/config.ini" \
      "$root/config/config.ini"
    do
      if is_primary_legacy_config "$candidate"; then
        echo "$candidate"
        return 0
      fi
    done
  done

  for root in "$@"; do
    [ -d "$root" ] || continue
    for candidate in $(find "$root" -path '*/apphub/src/config/config.ini' -type f 2>/dev/null); do
      if is_primary_legacy_config "$candidate"; then
        echo "$candidate"
        return 0
      fi
    done
  done

  for root in "$@"; do
    [ -d "$root" ] || continue
    for candidate in $(find "$root" -name config.ini -type f 2>/dev/null); do
      if is_primary_legacy_config "$candidate"; then
        echo "$candidate"
        return 0
      fi
    done
  done

  for root in "$@"; do
    [ -d "$root" ] || continue
    candidate="$(find "$root" -name config.ini -type f 2>/dev/null | head -n1)"
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 0
}

pick_legacy_system_ini() {
  for root in "$@"; do
    [ -d "$root" ] || continue
    for candidate in \
      "$root/apphub/src/config/system.ini" \
      "$root/src/config/system.ini" \
      "$root/config/system.ini"
    do
      if [ -f "$candidate" ]; then
        echo "$candidate"
        return 0
      fi
    done
  done

  for root in "$@"; do
    [ -d "$root" ] || continue
    candidate="$(find "$root" -name system.ini -type f 2>/dev/null | head -n1)"
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 0
}

mkdir -p /data

# ---------------- NPM (nginx_data) ----------------
if [ -d /legacy/nginx_data ]; then
  log_step "Copying NPM database and nginx config (excluding logs/)"
  [ -f /legacy/nginx_data/database.sqlite ] && cp -a /legacy/nginx_data/database.sqlite /data/database.sqlite || true
  if [ -d /legacy/nginx_data/nginx ]; then
    mkdir -p /data/nginx
    cp -a /legacy/nginx_data/nginx/. /data/nginx/ 2>/dev/null || true
  fi
  # Custom SSL certificates are user-managed and the NPM DB references them
  # at /data/custom_ssl. Keep the single canonical path matching the old layout.
  if [ -d /legacy/nginx_data/custom_ssl ]; then
    mkdir -p /data/custom_ssl
    cp -a /legacy/nginx_data/custom_ssl/. /data/custom_ssl/ 2>/dev/null || true
  fi
  [ -d /legacy/nginx_data/letsencrypt ] && { mkdir -p /data/letsencrypt; cp -a /legacy/nginx_data/letsencrypt/. /data/letsencrypt/ 2>/dev/null || true; } || true
fi
# Separate legacy letsencrypt volume (old /etc/letsencrypt) - best effort.
if [ -d /legacy/nginx_letsencrypt ]; then
  log_step "Copying letsencrypt certificate directory (best effort)"
  mkdir -p /data/letsencrypt
  cp -a /legacy/nginx_letsencrypt/. /data/letsencrypt/ 2>/dev/null || true
fi

# ---------------- Legacy /etc/custom ----------------
if [ -d /legacy/nginx_var/product-auth ]; then
  log_step "Copying legacy product auth data from /etc/custom"
  mkdir -p /data/config/product-auth
  cp -a /legacy/nginx_var/product-auth/. /data/config/product-auth/ 2>/dev/null || true
fi

# ---------------- Gitea ----------------
# Legacy layout (mounted at old /data): /legacy/gitea/gitea (app+conf+db),
# /legacy/gitea/git (repositories/lfs).
if [ -d /legacy/gitea ]; then
  log_step "Migrating Gitea with path remap and preserved SECRET_KEY / INTERNAL_TOKEN"
  old_g="/legacy/gitea/gitea"
  old_git="/legacy/gitea/git"
  mkdir -p /data/gitea/conf /data/gitea/data /data/gitea/git /data/gitea/log

  # Database
  [ -f "$old_g/gitea.db" ] && cp -a "$old_g/gitea.db" /data/gitea/gitea.db || true

  # Repositories and LFS objects
  [ -d "$old_git/repositories" ] && cp -a "$old_git/repositories" /data/gitea/git/ 2>/dev/null || true
  [ -d "$old_git/lfs" ] && cp -a "$old_git/lfs" /data/gitea/git/ 2>/dev/null || true

  # App data (avatars, attachments, ...) lands in APP_DATA_PATH=/data/gitea/data.
  if [ -d "$old_g" ]; then
    for sub in avatars repo-avatars attachments packages actions_log actions_artifacts queues sessions indexers; do
      [ -e "$old_g/$sub" ] && cp -a "$old_g/$sub" /data/gitea/data/ 2>/dev/null || true
    done
    # Merge older layouts that already used a nested data/ subtree.
    [ -d "$old_g/data" ] && cp -a "$old_g/data/." /data/gitea/data/ 2>/dev/null || true
  fi

  # Rebuild app.ini with modern paths while preserving legacy secrets.
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
  log_step "Copying Portainer data for BoltDB self-migration on first start"
  mkdir -p /data/portainer
  cp -a /legacy/portainer/. /data/portainer/ 2>/dev/null || true
fi

# ---------------- /data/compose (host bind -> named volume) ----------------
if [ -d /legacy/host-compose ]; then
  log_step "Copying host /data/compose into managed /data/compose"
  mkdir -p /data/compose
  cp -a /legacy/host-compose/. /data/compose/ 2>/dev/null || true
fi

# ---------------- Legacy AppHub logs (archive only) ----------------
if [ -d /legacy/apphub_logs ]; then
  mkdir -p /data/logs/legacy-apphub
  cp -a /legacy/apphub_logs/. /data/logs/legacy-apphub/ 2>/dev/null || true
fi

# ---------------- Legacy AppHub backup (restic-repo) ----------------
if [ -d /legacy/apphub_data/backup/restic-repo ]; then
  log_step "Copying legacy app backup repository (restic-repo)"
  mkdir -p /data/backup/restic-repo
  cp -a /legacy/apphub_data/backup/restic-repo/. /data/backup/restic-repo/ 2>/dev/null || true
fi

# ---------------- Legacy config handoff ----------------
cfg=""
sysini=""
product_auth_dir=""
legacy_roots="/legacy/apphub_config /legacy/service-root /legacy/download-root"
cfg="$(pick_legacy_config $legacy_roots)"
sysini="$(pick_legacy_system_ini $legacy_roots)"
for root in $legacy_roots; do
  [ -d "$root" ] || continue
  if [ -z "$product_auth_dir" ]; then
    product_auth_dir="$(find "$root" -name product-auth.sqlite -type f 2>/dev/null | head -n1)"
    [ -n "$product_auth_dir" ] && product_auth_dir="$(dirname "$product_auth_dir")"
  fi
  [ -z "$product_auth_dir" ] && product_auth_dir="$(find "$root" -type d -name product-auth 2>/dev/null | head -n1)"
done
[ -n "$cfg" ] && log_info "Selected legacy config source: $cfg"
[ -n "$sysini" ] && log_info "Selected legacy system.ini source: $sysini"
[ -n "$cfg" ] && [ -f "$cfg" ] && { mkdir -p /data/.w9-migration; cp -a "$cfg" /data/.w9-migration/legacy-config.ini; } || true
[ -n "$sysini" ] && { mkdir -p /data/.w9-migration; cp -a "$sysini" /data/.w9-migration/system.ini; } || true
[ -f /legacy/docker-daemon.json ] && { mkdir -p /data/.w9-migration; cp -a /legacy/docker-daemon.json /data/.w9-migration/legacy-daemon.json; } || true

if [ -n "$product_auth_dir" ] && [ -d "$product_auth_dir" ]; then
  log_step "Copying legacy product auth data"
  mkdir -p /data/config/product-auth
  cp -a "$product_auth_dir"/. /data/config/product-auth/ 2>/dev/null || true
fi

if [ -n "$cfg" ] && [ -f "$cfg" ]; then
  log_step "Synthesizing third-party credential files from legacy config"

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
    mkdir -p /data
    printf '{"username":"%s","password":"%s","nickname":"%s","display_name":"%s"}\n' \
      "${n_user:-admin}" "$n_pwd" "${n_nick:-admin}" "${n_nick:-admin}" >/data/credential.json
    chmod 600 /data/credential.json || true
  fi

  # Stage the legacy API key for the post-start config import.
  api_key="$(ini_get "$cfg" api_key key)"
  if [ -n "$api_key" ]; then
    mkdir -p /data/.w9-migration
    printf '%s' "$api_key" >/data/.w9-migration/legacy-api-key
  fi
fi

log_info "Data transform and legacy credential synthesis completed"
TRANSFORM
}

# Stage 4 + 5: deterministic data transform + credential synthesis.
_legacy_transform_volumes() {
  local install_path="$1"
  log_step "Running legacy data transform and credential synthesis"

  local data_root
  data_root="$(resolve_runtime_data_root "$install_path")"
  run_cmd mkdir -p "$data_root"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping the actual data transform"
    return 0
  fi

  local tmpdir
  tmpdir="$(mktemp -d)"
  _legacy_write_transform_script "${tmpdir}/transform.sh"

  # Assemble mounts for the legacy data that actually exists on the host.
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
  _add_ro_volume apphub_data       apphub_data
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
  if [ -f /etc/docker/daemon.json ]; then
    mounts+=(-v "/etc/docker/daemon.json:/legacy/docker-daemon.json:ro")
  fi

  if ! docker run --rm "${mounts[@]}" alpine:3.20 sh /w9script/transform.sh; then
    rm -rf "$tmpdir"
    die "$EXIT_RUNTIME" "Legacy data transform failed"
  fi
  rm -rf "$tmpdir"
}

 # Import staged legacy runtime settings into the modern config model.
_legacy_finalize_runtime_config() {
  log_step "Importing legacy runtime settings into the modern config model"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping runtime config import"
    return 0
  fi
  if ! container_running "$MODERN_CONTAINER_NAME"; then
    log_warn "Container is not running, skipping runtime config import"
    return 0
  fi

  docker exec -i "$MODERN_CONTAINER_NAME" python3 - <<'PY' 2>/dev/null || log_warn "Legacy runtime config import is best-effort and did not complete"
import configparser
import json
import os
import shutil
import sys
from pathlib import Path

data_root = Path(os.environ.get("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))

legacy_config_path = data_root / ".w9-migration/legacy-config.ini"
legacy_daemon_path = data_root / ".w9-migration/legacy-daemon.json"
runtime_config_path = Path("/websoft9/apphub/src/config/config.ini")
default_cert_path = data_root / "config/platform-gateway/ssl/websoft9-platform-gateway.cert"
default_key_path = data_root / "config/platform-gateway/ssl/websoft9-platform-gateway.key"
legacy_product_auth_credential_path = data_root / "product-auth/credential.json"

if not runtime_config_path.is_file() or (not legacy_config_path.is_file() and not legacy_daemon_path.is_file()):
    raise SystemExit(0)


def read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser


def ensure_section(parser: configparser.ConfigParser, section: str) -> None:
    if not parser.has_section(section):
        parser.add_section(section)


def get_first(parser: configparser.ConfigParser, candidates: list[tuple[str, str]]) -> str:
    for section, key in candidates:
        if parser.has_option(section, key):
            value = parser.get(section, key).strip()
            if value:
                return value
    return ""


def normalize_bool(value: str) -> str:
    lowered = (value or "").strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return "true"
    if lowered in {"0", "false", "no", "off"}:
        return "false"
    return ""


def normalize_registry_mirror(value: str) -> str:
    normalized = (value or "").strip().rstrip("/")
    if normalized.startswith("http://"):
        normalized = normalized[7:]
    elif normalized.startswith("https://"):
        normalized = normalized[8:]
    return normalized


def get_legacy_daemon_mirror(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    mirrors = payload.get("registry-mirrors")
    if isinstance(mirrors, str):
        mirrors = [mirrors]
    if not isinstance(mirrors, list):
        return ""

    normalized = [normalize_registry_mirror(str(entry)) for entry in mirrors if str(entry).strip()]
    normalized = [entry for entry in normalized if entry]
    return ",".join(normalized)


def set_if_value(parser: configparser.ConfigParser, section: str, key: str, value: str) -> bool:
    if not value:
        return False
    ensure_section(parser, section)
    current = parser.get(section, key, fallback="")
    if current == value:
        return False
    parser.set(section, key, value)
    return True


def copy_platform_cert(cert_source: Path, key_source: Path) -> bool:
    if not cert_source.is_file() or not key_source.is_file():
        return False
    default_cert_path.parent.mkdir(parents=True, exist_ok=True)
    default_key_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cert_source, default_cert_path)
    shutil.copy2(key_source, default_key_path)
    return True


legacy = read_ini(legacy_config_path) if legacy_config_path.is_file() else configparser.ConfigParser()
runtime = read_ini(runtime_config_path)
changed = False

legacy_api_key = get_first(legacy, [("api_key", "key")])
legacy_wildcard_domain = get_first(legacy, [("domain", "wildcard_domain"), ("domain", "default_domain"), ("domain", "domain")])
legacy_bound_domain = get_first(legacy, [("platform_gateway", "bound_domain"), ("cockpit", "domain"), ("cockpit", "default_domain"), ("domain", "platform_domain")])
legacy_docker_mirror = get_legacy_daemon_mirror(legacy_daemon_path) or get_first(legacy, [("docker_mirror", "url"), ("docker_mirror", "mirror_url"), ("docker_mirror", "registry_mirror")])
legacy_favorite_apps = get_first(legacy, [("favorite_apps", "keys")])
legacy_https_enabled = normalize_bool(get_first(legacy, [("platform_gateway", "https_enabled"), ("cockpit", "https_enabled")]))
legacy_force_https = normalize_bool(get_first(legacy, [("platform_gateway", "force_https"), ("cockpit", "force_https")]))
legacy_ssl_cert = get_first(legacy, [("platform_gateway", "ssl_cert"), ("cockpit", "ssl_cert"), ("cockpit", "cert_path")])
legacy_ssl_key = get_first(legacy, [("platform_gateway", "ssl_key"), ("cockpit", "ssl_key"), ("cockpit", "key_path")])

if set_if_value(runtime, "api_key", "key", legacy_api_key):
    changed = True
if set_if_value(runtime, "domain", "wildcard_domain", legacy_wildcard_domain):
    changed = True
if set_if_value(runtime, "docker_mirror", "url", legacy_docker_mirror):
    changed = True
if set_if_value(runtime, "platform_gateway", "bound_domain", legacy_bound_domain):
    changed = True

cert_candidates: list[tuple[Path, Path]] = []
if legacy_ssl_cert and legacy_ssl_key:
    cert_candidates.append((Path(legacy_ssl_cert), Path(legacy_ssl_key)))
if legacy_bound_domain:
    cert_candidates.append((Path(f"/data/letsencrypt/live/{legacy_bound_domain}/fullchain.pem"), Path(f"/data/letsencrypt/live/{legacy_bound_domain}/privkey.pem")))
if legacy_wildcard_domain:
    wildcard_domain = legacy_wildcard_domain[2:] if legacy_wildcard_domain.startswith("*.") else legacy_wildcard_domain
    cert_candidates.append((Path(f"/data/letsencrypt/live/{wildcard_domain}/fullchain.pem"), Path(f"/data/letsencrypt/live/{wildcard_domain}/privkey.pem")))
cert_candidates.append((Path("/data/custom_ssl/websoft9-self-signed.cert"), Path("/data/custom_ssl/websoft9-self-signed.key")))

copied_legacy_cert = False
for cert_candidate, key_candidate in cert_candidates:
    if copy_platform_cert(cert_candidate, key_candidate):
        copied_legacy_cert = True
        break

if copied_legacy_cert:
    if set_if_value(runtime, "platform_gateway", "ssl_cert", str(default_cert_path)):
        changed = True
    if set_if_value(runtime, "platform_gateway", "ssl_key", str(default_key_path)):
        changed = True
    if set_if_value(runtime, "platform_gateway", "https_enabled", "true"):
        changed = True
elif legacy_https_enabled:
    if set_if_value(runtime, "platform_gateway", "https_enabled", legacy_https_enabled):
        changed = True
    if legacy_https_enabled == "true":
        if set_if_value(runtime, "platform_gateway", "ssl_cert", str(default_cert_path)):
            changed = True
        if set_if_value(runtime, "platform_gateway", "ssl_key", str(default_key_path)):
            changed = True

if legacy_force_https:
    if set_if_value(runtime, "platform_gateway", "force_https", legacy_force_https):
        changed = True

favorite_keys = [item.strip().lower() for item in legacy_favorite_apps.replace("\n", ",").split(",") if item.strip()] if legacy_favorite_apps else []
favorite_keys = list(dict.fromkeys(favorite_keys))
if favorite_keys:
  sys.path.insert(0, "/websoft9/apphub")
  from src.services.product_auth import ProductAuthService

  credential_payload = {}
  if legacy_product_auth_credential_path.is_file():
    try:
      credential_payload = json.loads(legacy_product_auth_credential_path.read_text(encoding="utf-8"))
    except Exception:
      credential_payload = {}

  product_auth_service = ProductAuthService()
  if credential_payload.get("username") and credential_payload.get("password"):
    product_auth_service.bootstrap_operator_if_missing(
      username=str(credential_payload.get("username")),
      password=str(credential_payload.get("password")),
      display_name=str(credential_payload.get("display_name") or "Websoft9 User"),
    )

  product_auth_service.import_migrated_favorites(favorite_keys)

if changed:
    with runtime_config_path.open("w", encoding="utf-8") as handle:
        runtime.write(handle)

print("legacy-runtime-config-imported")
PY
}

# Stage 8: import product version / edition from legacy system.ini.
_legacy_finalize_product_state() {
  log_step "Importing product runtime state from legacy system.ini"
  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) skipping product runtime state import"
    return 0
  fi
  if ! container_running "$MODERN_CONTAINER_NAME"; then
    log_warn "Container is not running, skipping product runtime state import"
    return 0
  fi
  # system.ini was staged earlier at /data/.w9-migration/system.ini.
  docker exec "$MODERN_CONTAINER_NAME" sh -c '
    set -e
    if [ -f /data/.w9-migration/system.ini ]; then
      python3 -c "import sys; sys.path.insert(0,\"/websoft9/apphub\"); from src.services.product_metadata import migrate_product_metadata; from src.services.product_runtime_state import read_release_version; migrate_product_metadata(version=read_release_version(), legacy_system_ini_file=\"/data/.w9-migration/system.ini\")" || echo "[w9] product state migration best-effort failed"
    fi
  ' 2>/dev/null || log_warn "Product runtime state import is best-effort and did not block the migration"
}

# Main legacy migration flow.
run_upgrade_legacy() {
  local console_port="$1"
  local install_path="$2"
  local image_repo="$3"
  local image_tag="$4"
  local network_name="$5"
  local requested_console_port="$console_port"

  console_port="$(_legacy_resolve_console_port "$console_port")"

  if [ "${W9_CONSOLE_PORT_EXPLICIT:-0}" != "1" ] && [ -n "$console_port" ] && [ "$console_port" != "${requested_console_port:-$DEFAULT_CONSOLE_PORT}" ]; then
    if _legacy_is_proxy_fronted_platform; then
      log_info "Detected proxy-fronted legacy platform entry port: ${console_port}"
    elif [ "$console_port" = "$(_legacy_read_console_port_from_socket)" ]; then
      log_info "Detected legacy Cockpit listen port from cockpit.socket: ${console_port}"
    elif [ "$console_port" = "$(_legacy_read_platform_entry_port_from_config)" ]; then
      log_info "Detected legacy platform entry port from config.ini: ${console_port}"
    fi
  fi

  log_info "==== Legacy-to-modern migration started ===="
  require_root
  WEBSOFT9_DATA_ROOT="$(resolve_existing_runtime_data_root "$install_path" 1)"
  export WEBSOFT9_DATA_ROOT
  log_info "Migration data root resolved to: ${WEBSOFT9_DATA_ROOT}"

  # Stage 1: entry detection already happened; confirm there is no modern runtime.
  if _detect_modern_strong; then
    die "$EXIT_ENV_GUARD" "Modern runtime detected; the legacy migration path refuses to run in a mixed environment"
  fi

  # Stage 2: mandatory pre-migration backup.
  local backup_dir
  backup_dir="$(backup_new_dir legacy-migration)"
  legacy_write_manifest "$backup_dir"
  backup_legacy_pre_migration "$backup_dir"

  # Prepare modern deployment material without touching the transformed data root.
  install_prepare_material "$install_path" "$image_repo" "$image_tag" "$network_name" "$console_port"

  if [ "${W9_DRY_RUN:-0}" = "1" ]; then
    log_info "(dry-run) pre-cutover migration steps completed; stopping before the modern runtime takeover"
    log_info "Pre-migration backup point: $backup_dir"
    return 0
  fi

  log_step "Pulling the modern image before stopping the legacy runtime"
  if ! pull_image_with_mirrors "$install_path"; then
    die "$EXIT_RUNTIME" "Migration failed while pulling the modern image. Legacy runtime remains active. Backup: $backup_dir"
  fi

  # Stage 3: stop legacy writers and free ports.
  _legacy_stop_runtime

  # Stage 4 + 5: data transform + credential synthesis.
  _legacy_transform_volumes "$install_path"

  # Stage 6: start the modern runtime.
  log_step "Starting the modern runtime takeover"
  if ! modern_compose "$install_path" up -d; then
    die "$EXIT_RUNTIME" "Migration failed while starting the modern runtime. Legacy assets are still present for manual rollback. Backup: $backup_dir"
  fi

  # Stage 8a: import staged runtime settings and product state before validation.
  _legacy_finalize_runtime_config
  _legacy_finalize_product_state

  # Stage 7: validate the migrated runtime.
  if ! validate_upgrade "$console_port"; then
    log_error "Post-migration validation failed"
    log_warn "Legacy runtime assets are still present. Backup retained at: $backup_dir"
    log_warn "You can stop the modern container and restart the legacy systemd units or containers for a manual rollback"
    die "$EXIT_VALIDATE" "Migration failed during post-cutover validation"
  fi

  # Stage 8b: remove the legacy control plane and assets by default.
  log_step "Removing legacy Cockpit / systemd / containers / volumes by default"
  _uninstall_legacy "purge" "0" "1" "1"

  log_info "==== Legacy-to-modern migration completed successfully ===="
}
