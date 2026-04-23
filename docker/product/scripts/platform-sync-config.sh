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
  apphub setconfig --section "$1" --key "$2" --value "$3" >/dev/null
}

set_system_config() {
  apphub setsysconfig --section "$1" --key "$2" --value "$3" >/dev/null
}

sync_base() {
  set_config gitea base_url "${WEBSOFT9_GITEA_API_URL:-http://127.0.0.1:3001/api/v1}"
  set_config portainer base_url "${WEBSOFT9_PORTAINER_API_URL:-https://127.0.0.1:9443/api}"
  set_config nginx_proxy_manager base_url "${WEBSOFT9_NPM_API_URL:-http://127.0.0.1:81/api}"
  set_config nginx_proxy_manager ssl_cert "${WEBSOFT9_NPM_CERT_MARKER:-/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert}"
  set_config nginx_proxy_manager ssl_key "${WEBSOFT9_NPM_SSL_KEY_PATH:-/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.key}"
  set_system_config docker_library path "${WEBSOFT9_LIBRARY_PATH:-/websoft9/library/apps}"
  set_system_config app_media path "${WEBSOFT9_MEDIA_PATH:-/websoft9/media/json}"
}

sync_credentials() {
  local gitea_credential_path="${WEBSOFT9_GITEA_CREDENTIAL_PATH:-/data/gitea/credential}"
  local portainer_credential_path="${WEBSOFT9_PORTAINER_CREDENTIAL_PATH:-/data/portainer/credential}"
  local npm_credential_path="${WEBSOFT9_NPM_CREDENTIAL_PATH:-/data/nginx-proxy-manager/credential.json}"

  if [[ -f "$gitea_credential_path" ]]; then
    set_config gitea user_name "$(jq -r '.username' "$gitea_credential_path")"
    set_config gitea user_email "$(jq -r '.email' "$gitea_credential_path")"
    set_config gitea user_pwd "$(jq -r '.password' "$gitea_credential_path")"
  fi

  if [[ -f "$portainer_credential_path" ]]; then
    set_config portainer user_name "${WEBSOFT9_PORTAINER_ADMIN_USER:-admin}"
    set_config portainer user_pwd "$(cat "$portainer_credential_path")"
  fi

  if [[ -f "$npm_credential_path" ]]; then
    set_config nginx_proxy_manager user_name "$(jq -r '.username' "$npm_credential_path")"
    set_config nginx_proxy_manager user_pwd "$(jq -r '.password' "$npm_credential_path")"
  fi
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