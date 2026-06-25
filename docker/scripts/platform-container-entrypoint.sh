#!/usr/bin/env bash

set -euo pipefail

data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"

# Export credential paths BEFORE init_nginx.sh runs so that the NPM
# credential bootstrap file and the rest of the system (Python credential
# provider, health-check markers) agree on the same file path.
export WEBSOFT9_NPM_CREDENTIAL_PATH="${WEBSOFT9_NPM_CREDENTIAL_PATH:-$data_root/credential.json}"
export WEBSOFT9_NPM_DATABASE_PATH="${WEBSOFT9_NPM_DATABASE_PATH:-$data_root/database.sqlite}"
export WEBSOFT9_NPM_SSL_DIR="${WEBSOFT9_NPM_SSL_DIR:-$data_root/custom_ssl}"
export WEBSOFT9_NPM_NGINX_ROOT="${WEBSOFT9_NPM_NGINX_ROOT:-$data_root/nginx}"
export WEBSOFT9_NPM_LETSENCRYPT_DIR="${WEBSOFT9_NPM_LETSENCRYPT_DIR:-$data_root/letsencrypt}"
export WEBSOFT9_NPM_ACME_ROOT="${WEBSOFT9_NPM_ACME_ROOT:-$data_root/letsencrypt-acme-challenge}"

/app/init_nginx.sh --prepare-only

exec /websoft9/script/platform-entrypoint.sh