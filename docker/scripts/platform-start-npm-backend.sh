#!/usr/bin/env bash

set -euo pipefail

export PUID="${PUID:-0}"
export PGID="${PGID:-0}"
export NPMUSER="${NPMUSER:-npm}"
export NPMGROUP="${NPMGROUP:-npm}"
export NPMHOME="${NPMHOME:-/tmp/npmuserhome}"
export HOME="$NPMHOME"
export IP_RANGES_FETCH_ENABLED="${IP_RANGES_FETCH_ENABLED:-false}"
# NPM's certificate flow shells out to the system certbot. Keep that child
# process on Debian's default Python path instead of AppHub's extra packages.
unset PYTHONPATH
data_root="${WEBSOFT9_DATA_ROOT:-/opt/websoft9/data}"
service_log_root="${WEBSOFT9_SERVICE_LOG_ROOT:-$data_root/logs}"

reconcile_proxy_host_configs() {
	PYTHONPATH="/opt/websoft9-pydeps:/websoft9/apphub:/websoft9/apphub/src" \
	python3 - <<'PY'
import os
import time

from src.services.proxy_manager import ProxyManager


def certificate_paths_for(proxy_host: dict, certificate: dict | None) -> list[str]:
    certificate_id = proxy_host.get("certificate_id") or 0
    if not isinstance(certificate_id, int) or certificate_id <= 0:
        return []

    provider = (certificate or {}).get("provider")
    if provider == "letsencrypt":
        cert_dir = f"/etc/letsencrypt/live/npm-{certificate_id}"
    elif provider == "other":
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        cert_dir = f"{os.getenv('WEBSOFT9_NPM_SSL_DIR', f'{data_root}/custom_ssl')}/npm-{certificate_id}"
    else:
        return []

    return [f"{cert_dir}/fullchain.pem", f"{cert_dir}/privkey.pem"]


def find_matching_letsencrypt_certificate(certificates: dict[int, dict], domain_names: list[str]) -> dict | None:
    normalized_domains = sorted(domain_names or [])
    if not normalized_domains:
        return None

    for certificate in certificates.values():
        if certificate.get("provider") != "letsencrypt":
            continue
        if sorted(certificate.get("domain_names") or []) == normalized_domains:
            return certificate
    return None


for attempt in range(30):
    try:
        proxy_manager = ProxyManager()
        proxy_hosts = proxy_manager.get_proxy_hosts()
        certificates = {
            item.get("id"): item
            for item in proxy_manager.get_all_certificates()
            if isinstance(item, dict) and item.get("id") is not None
        }
        for proxy_host in proxy_hosts:
            proxy_id = proxy_host.get("id")
            if not proxy_host.get("enabled") or not isinstance(proxy_id, int):
                continue

            conf_root = os.getenv("WEBSOFT9_NPM_NGINX_ROOT", f"{os.getenv('WEBSOFT9_DATA_ROOT', '/opt/websoft9/data')}/nginx")
            conf_path = f"{conf_root}/proxy_host/{proxy_id}.conf"
            certificate_id = proxy_host.get("certificate_id") or 0
            ssl_forced = bool(proxy_host.get("ssl_forced"))
            desired_ssl_forced = ssl_forced
            domain_names = proxy_host.get("domain_names") or []
            certificate = certificates.get(certificate_id)
            certificate_paths = certificate_paths_for(proxy_host, certificate)
            certificate_missing = bool(certificate_paths) and not all(os.path.exists(path) for path in certificate_paths)
            recovery_certificate = (
                certificate
                if certificate and certificate.get("provider") == "letsencrypt"
                else find_matching_letsencrypt_certificate(certificates, domain_names) if not certificate_id else None
            )

            if recovery_certificate is not None:
                desired_ssl_forced = True

            if certificate and certificate.get("provider") == "other" and certificate_missing:
                print(f"Custom certificate files missing for proxy host {proxy_id}; preserving SSL binding for certificate npm-{certificate_id}")

            if (
                recovery_certificate is not None
                and (
                    certificate_missing
                    or (not certificate_id and not os.path.exists(conf_path))
                )
            ):
                print(f"Rebuilding proxy host {proxy_id} without missing certificate npm-{certificate_id}")
                meta = proxy_host.get("meta") or {}
                certificate = recovery_certificate or {}
                certificate_meta = certificate.get("meta") or {}
                email = (meta.get("letsencrypt_email") or certificate_meta.get("letsencrypt_email") or "").strip()
                domain_names = domain_names or (certificate.get("domain_names") or [])
                proxy_manager.update_proxy_host_settings(
                    proxy_id=proxy_id,
                    domain_names=domain_names,
                    forward_host=proxy_host.get("forward_host") or "",
                    forward_port=int(proxy_host.get("forward_port") or 0),
                    forward_scheme=proxy_host.get("forward_scheme") or "http",
                    certificate_id=None,
                    ssl_forced=False,
                )

                if email and domain_names:
                    certificate = proxy_manager.request_letsencrypt_certificate(email, domain_names, proxy_id)
                    certificate_id = certificate.get("id")
                    ssl_forced = desired_ssl_forced
                    proxy_manager.update_proxy_host_settings(
                        proxy_id=proxy_id,
                        domain_names=domain_names,
                        forward_host=proxy_host.get("forward_host") or "",
                        forward_port=int(proxy_host.get("forward_port") or 0),
                        forward_scheme=proxy_host.get("forward_scheme") or "http",
                        certificate_id=certificate_id,
                        ssl_forced=ssl_forced,
                    )
                    print(f"Reissued missing certificate for proxy host {proxy_id} as npm-{certificate_id}")
                else:
                    certificate_id = None
                    ssl_forced = False

            if not os.path.exists(conf_path):
                proxy_manager.update_proxy_host_settings(
                    proxy_id=proxy_id,
                    domain_names=proxy_host.get("domain_names") or [],
                    forward_host=proxy_host.get("forward_host") or "",
                    forward_port=int(proxy_host.get("forward_port") or 0),
                    forward_scheme=proxy_host.get("forward_scheme") or "http",
                    certificate_id=certificate_id,
                    ssl_forced=ssl_forced,
                )
                print(f"Rebuilt missing proxy host config for {proxy_id}")

        break
    except Exception as exc:
        if attempt == 29:
            print(f"Skipping proxy-host reconciliation: {exc}")
            break
        time.sleep(2)
PY
}

mkdir -p "$NPMHOME" "$service_log_root" "$service_log_root/npm"

reconcile_proxy_host_configs &

cd /app
exec /usr/bin/node --abort_on_uncaught_exception --max_old_space_size=250 index.js