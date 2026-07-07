#!/usr/bin/env bash

set -euo pipefail

mode="base"
data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
runtime_config_path="${WEBSOFT9_APPHUB_CONFIG_PATH:-$data_root/config/apphub/config.ini}"
runtime_system_config_path="${WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH:-$data_root/config/apphub/system.ini}"
bundled_config_path="/websoft9/apphub/src/config/config.ini"
bundled_system_config_path="/websoft9/apphub/src/config/system.ini"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      mode="$2"
      shift 2
      ;;
    *)
      echo "unsupported argument: $1" >&2
      exit 1
      ;;
  esac
done

set_config() {
  websoft9 setconfig --section "$1" --key "$2" --value "$3" >/dev/null
}

bootstrap_runtime_config() {
  local source_path="$1"
  local target_path="$2"

  mkdir -p "$(dirname "$target_path")"
  if [[ ! -f "$target_path" && -f "$source_path" ]]; then
    cp -a "$source_path" "$target_path"
  fi
}

ensure_runtime_config_files() {
  bootstrap_runtime_config "$bundled_config_path" "$runtime_config_path"
  bootstrap_runtime_config "$bundled_system_config_path" "$runtime_system_config_path"
}

set_config_if_missing() {
  python3 - "$runtime_config_path" "$1" "$2" "$3" <<'PY'
import configparser
import sys

config_path, section, key, value = sys.argv[1:5]
config = configparser.ConfigParser()
config.read(config_path)
if not config.has_section(section):
    config.add_section(section)
if not config.has_option(section, key):
    config.set(section, key, value)
    with open(config_path, 'w', encoding='utf-8') as file:
        config.write(file)
PY
}

set_system_config() {
  websoft9 setsysconfig --section "$1" --key "$2" --value "$3" >/dev/null
}

write_apphub_gateway_auth() {
  local trust_key=""
  local internal_gateway_auth_dir="${WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR:-$data_root/config/internal-gateway-auth}"
  local internal_gateway_trust_key_file="$internal_gateway_auth_dir/trust_key"
  local gateway_dir="/etc/websoft9/platform-gateway"
  local gateway_auth_file="$gateway_dir/apphub-auth.conf"

  mkdir -p "$gateway_dir"
  mkdir -p "$internal_gateway_auth_dir"

  if [[ -f "$internal_gateway_trust_key_file" ]]; then
    trust_key="$(tr -d '[:space:]' < "$internal_gateway_trust_key_file")"
  fi

  if [[ -z "$trust_key" ]]; then
    trust_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    printf '%s\n' "$trust_key" > "$internal_gateway_trust_key_file"
    chmod 600 "$internal_gateway_trust_key_file"
  fi

  cat >"$gateway_auth_file" <<EOF
proxy_set_header x-api-key "";
proxy_set_header x-websoft9-internal-request "1";
proxy_set_header x-websoft9-internal-secret "$trust_key";
EOF
}

sync_base() {
  ensure_runtime_config_files
  set_config_if_missing platform_gateway https_enabled "${WEBSOFT9_PLATFORM_HTTPS_ENABLED:-false}"
  set_config platform_gateway ssl_cert "${WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH:-$data_root/config/platform-gateway/ssl/websoft9-platform-gateway.cert}"
  set_config platform_gateway ssl_key "${WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH:-$data_root/config/platform-gateway/ssl/websoft9-platform-gateway.key}"
  set_system_config docker_library path "${WEBSOFT9_LIBRARY_PATH:-/websoft9/library/apps}"
  set_system_config app_media path "${WEBSOFT9_MEDIA_PATH:-/websoft9/media/json}"
  set_system_config volume_backup repopath "$data_root/backup/restic-repo"
  write_apphub_gateway_auth
}

sync_credentials() {
  ensure_runtime_config_files
  python3 - "$runtime_config_path" <<'PY'
import configparser
import sys

config_path = sys.argv[1]
config = configparser.ConfigParser()
config.read(config_path, encoding='utf-8')

changed = False

for section in ('gitea', 'portainer', 'nginx_proxy_manager'):
  if config.remove_section(section):
    changed = True

if changed:
  with open(config_path, 'w', encoding='utf-8') as file:
    config.write(file)
PY

  write_apphub_gateway_auth
}

case "$mode" in
  base)
    sync_base
    ;;
  credentials)
    sync_credentials
    ;;
  *)
    echo "unsupported mode: $mode" >&2
    exit 1
    ;;
esac