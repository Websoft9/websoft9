#!/usr/bin/env bash

set -euo pipefail

data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
data_dir="${WEBSOFT9_GITEA_DATA_DIR:-$data_root/gitea}"
config_dir="$data_dir/conf"
config_file="$config_dir/app.ini"
credential_path="${WEBSOFT9_GITEA_CREDENTIAL_PATH:-$data_dir/credential}"
admin_user="${WEBSOFT9_GITEA_ADMIN_USER:-websoft9}"
admin_email="${WEBSOFT9_GITEA_ADMIN_EMAIL:-admin@mydomain.com}"
gitea_port="${WEBSOFT9_GITEA_HTTP_PORT:-3001}"
platform_public_origin="${WEBSOFT9_PLATFORM_PUBLIC_ORIGIN:-http://127.0.0.1:${WEBSOFT9_PLATFORM_HTTP_PORT:-9000}}"
root_url="${WEBSOFT9_GITEA_ROOT_URL:-${platform_public_origin%/}/w9git/}"
local_root_url="${WEBSOFT9_GITEA_LOCAL_ROOT_URL:-http://127.0.0.1:${gitea_port}/}"
static_url_prefix="${WEBSOFT9_GITEA_STATIC_URL_PREFIX:-/w9git}"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [platform-start-gitea] $*"
}

random_secret() {
  openssl rand -hex 24
}

ensure_config_value() {
  local key="$1"
  local value="$2"

  if grep -Eq "^${key} = " "$config_file"; then
    sed -i "s#^${key} = .*#${key} = ${value}#" "$config_file"
    return
  fi

  sed -i "/^\[server\]/a ${key} = ${value}" "$config_file"
}

load_or_create_credentials() {
  if [[ -f "$credential_path" ]]; then
    read -r admin_user admin_email admin_password < <(jq -r '.username + " " + .email + " " + .password' "$credential_path")
    return
  fi

  admin_password="$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9@#%+=' | head -c 16)"
  mkdir -p "$(dirname "$credential_path")"
  cat >"$credential_path" <<EOF
{"username":"$admin_user","email":"$admin_email","password":"$admin_password"}
EOF
  chmod 600 "$credential_path"
}

write_config() {
  if [[ -f "$config_file" ]]; then
    return
  fi

  mkdir -p "$config_dir" "$data_dir/git/repositories" "$data_dir/git/lfs" "$data_dir/log" "$data_dir/data"

  cat >"$config_file" <<EOF
[server]
APP_DATA_PATH = $data_dir/data
DOMAIN = 127.0.0.1
HTTP_PORT = $gitea_port
ROOT_URL = $root_url
LOCAL_ROOT_URL = $local_root_url
STATIC_URL_PREFIX = $static_url_prefix
DISABLE_SSH = true
SSH_DOMAIN = 127.0.0.1

[database]
DB_TYPE = sqlite3
PATH = $data_dir/gitea.db

[security]
INSTALL_LOCK = true
SECRET_KEY = $(random_secret)
INTERNAL_TOKEN = $(random_secret)
PASSWORD_HASH_ALGO = pbkdf2

[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = false

[repository]
ROOT = $data_dir/git/repositories

[lfs]
PATH = $data_dir/git/lfs

[log]
ROOT_PATH = $data_dir/log
EOF
}

reconcile_config() {
  ensure_config_value "DOMAIN" "127.0.0.1"
  ensure_config_value "HTTP_PORT" "$gitea_port"
  ensure_config_value "ROOT_URL" "$root_url"
  ensure_config_value "LOCAL_ROOT_URL" "$local_root_url"
  ensure_config_value "STATIC_URL_PREFIX" "$static_url_prefix"
  ensure_config_value "DISABLE_SSH" "true"
  ensure_config_value "SSH_DOMAIN" "127.0.0.1"
}

ensure_admin_user() {
  local output

  if ! output="$(su -s /bin/bash git -c "/usr/local/bin/gitea admin user create --admin --username '$admin_user' --email '$admin_email' --password '$admin_password' --config '$config_file'" 2>&1)"; then
    if [[ "$output" == *"already exists"* ]]; then
      return 0
    fi

    log "admin user create failed output=$output"
    return 1
  fi
}

wait_for_gitea() {
  local attempts=30

  while (( attempts > 0 )); do
    if curl --silent --show-error --max-time 2 --output /dev/null "http://127.0.0.1:${gitea_port}/"; then
      return 0
    fi

    sleep 2
    attempts=$((attempts - 1))
  done

  return 1
}

main() {
  local gitea_pid

  if [[ "${WEBSOFT9_SIMULATE_GITEA_FAILURE:-0}" == "1" ]]; then
    log "simulated gitea bootstrap failure requested"
    exit 1
  fi

  load_or_create_credentials
  write_config
  reconcile_config

  mkdir -p /var/lib/gitea
  chown -R git:git "$data_dir" /var/lib/gitea

  log "starting gitea"
  su -s /bin/bash git -c "/usr/local/bin/gitea web --config '$config_file'" &
  gitea_pid=$!

  if ! wait_for_gitea; then
    log "gitea failed to become healthy"
    kill "$gitea_pid" >/dev/null 2>&1 || true
    wait "$gitea_pid" || true
    exit 1
  fi

  ensure_admin_user
  wait "$gitea_pid"
}

main "$@"