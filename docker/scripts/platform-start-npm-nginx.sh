#!/usr/bin/env bash

set -euo pipefail

service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-/data/logs}"
letsencrypt_dir="${WEBSOFT9_NPM_LETSENCRYPT_DIR:-/data/letsencrypt}"

quarantine_orphaned_ssl_configs() {
	local nginx_root="/data/nginx"
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
	/data/letsencrypt-acme-challenge/.well-known/acme-challenge \
	/data/logs \
	/data/nginx/custom \
	/data/nginx/default_host \
	/data/nginx/default_www \
	/data/nginx/dead_host \
	/data/nginx/proxy_host \
	/data/nginx/redirection_host \
	/data/nginx/stream \
	/data/nginx/temp \
	"$service_log_root/npm"
rm -f /run/nginx/nginx.pid
quarantine_orphaned_ssl_configs

exec /usr/sbin/nginx