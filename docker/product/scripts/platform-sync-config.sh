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

write_apphub_gateway_auth() {
  local trust_key=""
  local internal_gateway_auth_dir="${WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR:-/etc/custom/internal-gateway-auth}"
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
  set_config gitea base_url "${WEBSOFT9_GITEA_API_URL:-http://127.0.0.1:3001/api/v1}"
  set_config portainer base_url "${WEBSOFT9_PORTAINER_API_URL:-https://127.0.0.1:9443/api}"
  set_config nginx_proxy_manager base_url "${WEBSOFT9_NPM_API_URL:-http://127.0.0.1:81/api}"
  set_config nginx_proxy_manager ssl_cert "${WEBSOFT9_NPM_CERT_MARKER:-/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert}"
  set_config nginx_proxy_manager ssl_key "${WEBSOFT9_NPM_SSL_KEY_PATH:-/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.key}"
  set_system_config docker_library path "${WEBSOFT9_LIBRARY_PATH:-/websoft9/library/apps}"
  set_system_config app_media path "${WEBSOFT9_MEDIA_PATH:-/websoft9/media/json}"
  write_apphub_gateway_auth
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