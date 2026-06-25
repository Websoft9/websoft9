#!/usr/bin/env bash

set -euo pipefail

data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-$data_root/logs}"
letsencrypt_dir="${WEBSOFT9_NPM_LETSENCRYPT_DIR:-$data_root/letsencrypt}"
acme_root="${WEBSOFT9_NPM_ACME_ROOT:-$data_root/letsencrypt-acme-challenge}"
nginx_root="${WEBSOFT9_NPM_NGINX_ROOT:-$data_root/nginx}"

quarantine_orphaned_ssl_configs() {
	local quarantine_root="$nginx_root/quarantine/orphaned-ssl"
	local config_dir
	local conf_file
	local cert_path

	for config_dir in proxy_host redirection_host dead_host default_host default_www stream; do
		[[ -d "$nginx_root/$config_dir" ]] || continue

		while IFS= read -r -d '' conf_file; do
			cert_path="$(awk '$1 == "ssl_certificate" { gsub(/;$/, "", $2); print $2; exit }' "$conf_file")"
			[[ -n "$cert_path" ]] || continue

			if [[ ! -e "$cert_path" ]]; then
				mkdir -p "$quarantine_root/$config_dir"
				mv "$conf_file" "$quarantine_root/$config_dir/"
				echo "Quarantined orphaned SSL config: $conf_file (missing $cert_path)"
			fi
		done < <(find "$nginx_root/$config_dir" -maxdepth 1 -type f -name '*.conf' -print0)
	done
}

if [[ ! -L /etc/letsencrypt ]]; then
	mkdir -p "$letsencrypt_dir"
	if [[ -d /etc/letsencrypt ]]; then
		cp -a /etc/letsencrypt/. "$letsencrypt_dir/" 2>/dev/null || true
		rm -rf /etc/letsencrypt
	elif [[ -e /etc/letsencrypt ]]; then
		rm -f /etc/letsencrypt
	fi
	ln -s "$letsencrypt_dir" /etc/letsencrypt
fi

mkdir -p \
	/run/nginx \
	/tmp/nginx/body \
	/var/cache/nginx \
	/var/lib/nginx/cache/private \
	/var/lib/nginx/cache/public \
	/var/log/nginx \
	"$acme_root/.well-known/acme-challenge" \
	"$service_log_root" \
	"$nginx_root/custom" \
	"$nginx_root/default_host" \
	"$nginx_root/default_www" \
	"$nginx_root/dead_host" \
	"$nginx_root/proxy_host" \
	"$nginx_root/redirection_host" \
	"$nginx_root/stream" \
	"$nginx_root/temp" \
	"$service_log_root/npm"
rm -f /run/nginx/nginx.pid
quarantine_orphaned_ssl_configs

# Migrate upstream NPM nginx configs from legacy /data/ to current data root.
# The npm-runtime image ships configs with hardcoded /data/logs/ paths;
# we sed-replace them at runtime so they always match $service_log_root.
npm_runtime_config_dir="/run/websoft9/npm-nginx"
mkdir -p "$npm_runtime_config_dir"
cp -a /etc/nginx/. "$npm_runtime_config_dir/"
find "$npm_runtime_config_dir" -name '*.conf' -print0 \
  | xargs -0 sed -i "s#/data/logs/#$service_log_root/#g"

exec /usr/sbin/nginx -c "$npm_runtime_config_dir/nginx.conf"