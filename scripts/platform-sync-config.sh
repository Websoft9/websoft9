#!/usr/bin/env bash

set -euo pipefail

mode="base"

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

set_config_if_missing() {
  python3 - "$1" "$2" "$3" <<'PY'
import configparser
import sys

section, key, value = sys.argv[1:4]
config = configparser.ConfigParser()
config.read('/websoft9/apphub/src/config/config.ini')
if not config.has_section(section):
    config.add_section(section)
if not config.has_option(section, key):
    config.set(section, key, value)
    with open('/websoft9/apphub/src/config/config.ini', 'w', encoding='utf-8') as file:
        config.write(file)
PY
}

set_system_config() {
  websoft9 setsysconfig --section "$1" --key "$2" --value "$3" >/dev/null
}

sync_base() {
  set_config_if_missing platform_gateway https_enabled "${WEBSOFT9_PLATFORM_HTTPS_ENABLED:-false}"
  set_config_if_missing platform_gateway ssl_cert "${WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH:-/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.cert}"
  set_config_if_missing platform_gateway ssl_key "${WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH:-/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.key}"
  set_system_config docker_library path "${WEBSOFT9_LIBRARY_PATH:-/websoft9/library/apps}"
  set_system_config app_media path "${WEBSOFT9_MEDIA_PATH:-/websoft9/media/json}"
}

sync_credentials() {
  python3 - <<'PY'
import configparser

config_path = '/websoft9/apphub/src/config/config.ini'
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