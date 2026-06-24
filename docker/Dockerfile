# Websoft9 Single-Container Runtime Image
# Build: docker build -f docker/Dockerfile -t websoft9dev/websoft9:dev .
FROM node:22-bookworm-slim AS console-builder

WORKDIR /build/console
COPY console/package.json console/package-lock.json ./
RUN npm ci
COPY console ./
RUN npm run build

FROM golang:1.24 AS portainer-init-builder

WORKDIR /build
COPY docker/deployment/init_portainer.go /build/init_portainer.go
RUN CGO_ENABLED=0 go build -o /build/init_portainer /build/init_portainer.go

FROM python:3.11-slim AS python-deps-builder

ARG WEBSOFT9_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG WEBSOFT9_PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /build
COPY apphub/requirements.txt /build/requirements.txt
RUN set -e; \
    export PIP_PROGRESS_BAR=off; \
    export PIP_DEFAULT_TIMEOUT=120; \
    export PIP_DISABLE_PIP_VERSION_CHECK=1; \
    if [ -n "$WEBSOFT9_PIP_INDEX_URL" ]; then export PIP_INDEX_URL="$WEBSOFT9_PIP_INDEX_URL"; fi; \
    if [ -n "$WEBSOFT9_PIP_TRUSTED_HOST" ]; then export PIP_TRUSTED_HOST="$WEBSOFT9_PIP_TRUSTED_HOST"; fi; \
    mkdir -p /tmp/pip-cache; \
    for attempt in 1 2 3; do \
        python -m pip install \
            --cache-dir /tmp/pip-cache \
            --retries 10 \
            --timeout 120 \
            --target /opt/websoft9-pydeps \
            -r /build/requirements.txt \
            supervisor && break; \
        if [ "$attempt" -eq 3 ]; then \
            exit 1; \
        fi; \
        echo "pip install failed on attempt $attempt, retrying..."; \
    done

FROM gitea/gitea:1.25.5 AS gitea-runtime
FROM portainer/portainer-ce:2.40.0 AS portainer-runtime
FROM jc21/nginx-proxy-manager:2.12.6 AS npm-runtime

FROM python:3.11-slim

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL org.opencontainers.image.title="Websoft9 Product Container"
LABEL org.opencontainers.image.description="Converged Websoft9 runtime with AppHub, Gitea, Portainer, and Nginx Proxy Manager"

ENV WEBSOFT9_RUNTIME_LAYOUT=single-container-target \
    WEBSOFT9_APPHUB_HEALTH_URL=http://127.0.0.1:8080/api/healthz \
    WEBSOFT9_MEDIA_HEALTH_URL=http://127.0.0.1:8081/healthz \
    WEBSOFT9_CUSTOM_ROOT=/data/config \
    WEBSOFT9_INTERNAL_GATEWAY_AUTH_DIR=/data/config/internal-gateway-auth \
    WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE=/data/config/internal-gateway-auth/trust_key \
    WEBSOFT9_HOST_ACCESS_DATA_DIR=/data/config/host-access \
    WEBSOFT9_INSTALL_TRACKING_DIR=/data/config/apphub \
    WEBSOFT9_PRODUCT_AUTH_DATA_DIR=/data/config/product-auth \
    WEBSOFT9_GITEA_CREDENTIAL_PATH=/data/gitea/credential \
    WEBSOFT9_PORTAINER_CREDENTIAL_PATH=/data/portainer/credential \
    WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH=/data/config/platform-gateway/ssl/websoft9-platform-gateway.cert \
    WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH=/data/config/platform-gateway/ssl/websoft9-platform-gateway.key \
    WEBSOFT9_NPM_CREDENTIAL_PATH=/data/nginx-proxy-manager/credential.json \
    WEBSOFT9_NPM_SSL_DIR=/data/nginx-proxy-manager/custom_ssl \
    WEBSOFT9_NPM_CERT_MARKER=/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert \
    WEBSOFT9_NPM_SSL_KEY_PATH=/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.key \
    WEBSOFT9_SERVICE_LOG_ROOT=/data/logs \
    WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH=/data/logs/platform-runtime.log \
    WEBSOFT9_SUPERVISOR_CONFIG=/etc/supervisor/conf.d/websoft9-platform.conf \
    WEBSOFT9_SUPERVISOR_SOCKET=/run/supervisor.sock \
    WEBSOFT9_SUPERVISOR_PIDFILE=/run/supervisord.pid \
    NPMHOME=/tmp/npmuserhome \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONPATH=/opt/websoft9-pydeps:/websoft9/apphub:/websoft9/apphub/src \
    PYTHONUNBUFFERED=1

WORKDIR /websoft9

# Keep system package installation BEFORE ARG declarations so that
# changing WEBSOFT9_PRODUCT_VERSION/EDITION_KEY does not invalidate
# this expensive apt cache layer on every build.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    bash \
    bzip2 \
    ca-certificates \
    certbot \
    cron \
    curl \
    git \
    jq \
    libstdc++6 \
    logrotate \
    openssl \
    sqlite3 && \
    rm -rf /var/lib/apt/lists/*

ARG WEBSOFT9_PRODUCT_VERSION=
ARG WEBSOFT9_PRODUCT_EDITION_KEY=
ARG WEBSOFT9_APPSTORE_CHANNEL=release

# Restic backup binary — single static build, no runtime deps
# Retry with mirror fallback for Chinese network environments
RUN RESTIC_URL="https://github.com/restic/restic/releases/download/v0.17.3/restic_0.17.3_linux_amd64.bz2" \
    RESTIC_MIRROR="https://ghproxy.com/${RESTIC_URL}" \
    && for url in "$RESTIC_URL" "$RESTIC_MIRROR"; do \
         echo "Trying: $url" \
         && if curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 300 "$url" | bzip2 -d > /usr/local/bin/restic; then \
              chmod +x /usr/local/bin/restic \
              && restic version \
              && echo "Restic installed from: $url" \
              && break; \
         fi; \
         echo "Failed: $url, trying next..."; \
       done \
    && [ -x /usr/local/bin/restic ] || (echo "All Restic download sources failed" && false)

COPY --from=npm-runtime /app /app
COPY --from=npm-runtime /etc/letsencrypt.ini /etc/letsencrypt.ini
COPY --from=npm-runtime /etc/nginx /etc/nginx
COPY --from=npm-runtime /etc/logrotate.d/nginx-proxy-manager /etc/logrotate.d/nginx-proxy-manager
COPY --from=npm-runtime /usr/bin/node /usr/bin/node
COPY --from=npm-runtime /usr/sbin/nginx /usr/sbin/nginx
COPY --from=npm-runtime /lib/x86_64-linux-gnu/libpcre.so.3 /lib/x86_64-linux-gnu/libpcre.so.3
COPY --from=npm-runtime /lib/x86_64-linux-gnu/libpcre.so.3.13.3 /lib/x86_64-linux-gnu/libpcre.so.3.13.3

RUN mkdir -p /opt/websoft9-npm-frontend && cp -a /app/frontend/. /opt/websoft9-npm-frontend/

RUN getent group npm >/dev/null || groupadd --system npm && \
    id -u npm >/dev/null 2>&1 || useradd --system --gid npm --home-dir /tmp/npmuserhome --shell /usr/sbin/nologin npm

RUN getent group git >/dev/null || groupadd --gid 1000 git && \
    id -u git >/dev/null 2>&1 || useradd --uid 1000 --gid 1000 --home-dir /data/gitea --shell /bin/bash git

COPY --from=python-deps-builder /opt/websoft9-pydeps /opt/websoft9-pydeps
COPY --from=gitea-runtime /usr/local/bin/gitea /usr/local/bin/gitea
COPY --from=gitea-runtime /app/gitea/gitea /app/gitea/gitea
COPY --from=gitea-runtime /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=gitea-runtime /lib/libc.musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1
COPY --from=portainer-runtime /portainer /portainer
COPY --from=portainer-runtime /public /opt/websoft9-portainer/public
COPY --from=portainer-init-builder /build/init_portainer /usr/local/bin/init_portainer

COPY version.json /websoft9/version.json
COPY apphub /websoft9/apphub
RUN WEBSOFT9_PRODUCT_VERSION="${WEBSOFT9_PRODUCT_VERSION}" WEBSOFT9_PRODUCT_EDITION_KEY="${WEBSOFT9_PRODUCT_EDITION_KEY}" WEBSOFT9_APPSTORE_CHANNEL="${WEBSOFT9_APPSTORE_CHANNEL}" python3 - <<'PY'
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, "/websoft9/apphub")

from src.services.product_runtime_state import initialize_product_runtime_state, read_release_version_file

version_path = Path("/websoft9/version.json")
payload = read_release_version_file(version_path)

version = (os.environ.get("WEBSOFT9_PRODUCT_VERSION") or str(payload.get("version") or "")).strip()
edition_key = (os.environ.get("WEBSOFT9_PRODUCT_EDITION_KEY") or str(payload.get("edition_key") or "")).strip()
channel = (os.environ.get("WEBSOFT9_APPSTORE_CHANNEL") or str(payload.get("channel") or "release")).strip().lower()

if not version:
    raise SystemExit("WEBSOFT9_PRODUCT_VERSION is required for product image builds")

if channel not in {"release", "rc", "dev"}:
    raise SystemExit(f"Unsupported WEBSOFT9_APPSTORE_CHANNEL: {channel}")

payload["version"] = version
payload["edition_key"] = edition_key
payload["channel"] = channel
version_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

initialize_product_runtime_state()
PY
COPY --from=console-builder /build/console/dist /etc/websoft9/console
COPY docker/proxy/config/http.conf /data/nginx/custom/http.conf
COPY docker/proxy/init_nginx.sh /app/init_nginx.sh
COPY docker/gateway/nginx.conf /etc/websoft9/platform-gateway/nginx.conf
COPY docker/gateway/default.conf /etc/websoft9/platform-gateway/default.conf
COPY docker/gateway/platform-gateway-routes.conf /etc/websoft9/platform-gateway/platform-gateway-routes.conf
COPY docker/apphub/logging_config.yaml /etc/supervisor/conf.d/logging_config.yaml
COPY docker/supervisord.conf /etc/supervisor/conf.d/websoft9-platform.conf
COPY docker/scripts/platform-container-entrypoint.sh /websoft9/script/platform-container-entrypoint.sh
COPY docker/scripts/platform-entrypoint.sh /websoft9/script/platform-entrypoint.sh
COPY docker/scripts/platform-healthcheck.sh /websoft9/script/platform-healthcheck.sh
COPY docker/scripts/platform-service-control.sh /websoft9/script/platform-service-control.sh
COPY docker/scripts/platform-start-gateway.sh /websoft9/script/platform-start-gateway.sh
COPY docker/scripts/platform-start-gitea.sh /websoft9/script/platform-start-gitea.sh
COPY docker/scripts/platform-start-npm-backend.sh /websoft9/script/platform-start-npm-backend.sh
COPY docker/scripts/platform-start-npm-nginx.sh /websoft9/script/platform-start-npm-nginx.sh
COPY docker/scripts/platform-start-portainer.sh /websoft9/script/platform-start-portainer.sh
COPY docker/scripts/platform-sync-config.sh /websoft9/script/platform-sync-config.sh
COPY docker/scripts/platform-ensure-product-metadata.py /websoft9/script/platform-ensure-product-metadata.py
COPY docker/scripts/platform-sync-runtime-assets.py /websoft9/script/platform-sync-runtime-assets.py
COPY docker/crontab /etc/cron.d/websoft9-appstore

RUN chmod 0644 /etc/cron.d/websoft9-appstore

# Pre-populate app store assets during image build so first-load browsing uses
# a prepared local dataset instead of waiting for runtime warm-up.
# Non-fatal: build continues even if remote assets are unavailable (runtime cron retries).
RUN WEBSOFT9_RUNTIME_ASSET_SYNC_MODE=build \
    WEBSOFT9_RUNTIME_ASSET_CHANNEL="${WEBSOFT9_APPSTORE_CHANNEL}" \
    python3 /websoft9/script/platform-sync-runtime-assets.py || true

RUN printf '%s\n' '#!/bin/sh' 'exec python3 -m supervisor.supervisord "$@"' > /usr/local/bin/supervisord && \
    printf '%s\n' '#!/bin/sh' 'exec python3 -m supervisor.supervisorctl "$@"' > /usr/local/bin/supervisorctl && \
    printf '%s\n' '#!/bin/sh' 'exec python3 /websoft9/apphub/src/cli/apphub_cli.py "$@"' > /usr/local/bin/apphub && \
    chmod +x /usr/local/bin/supervisord /usr/local/bin/supervisorctl /usr/local/bin/apphub

RUN chmod +x /app/init_nginx.sh \
    /websoft9/script/platform-container-entrypoint.sh \
    /websoft9/script/platform-entrypoint.sh \
    /websoft9/script/platform-healthcheck.sh \
    /websoft9/script/platform-service-control.sh \
    /websoft9/script/platform-start-gateway.sh \
    /websoft9/script/platform-start-gitea.sh \
    /websoft9/script/platform-start-npm-backend.sh \
    /websoft9/script/platform-start-npm-nginx.sh \
    /websoft9/script/platform-start-portainer.sh \
    /websoft9/script/platform-ensure-product-metadata.py \
    /websoft9/script/platform-sync-config.sh \
    /websoft9/script/platform-sync-runtime-assets.py && \
    mkdir -p /etc/websoft9 \
    /etc/websoft9/console \
    /etc/websoft9/platform-gateway \
    /run/nginx \
    /run/websoft9 \
    /tmp/nginx/body \
    /tmp/npmuserhome \
    /var/cache/nginx \
    /var/lib/nginx/cache/private \
    /var/lib/nginx/cache/public \
    /var/log/nginx \
    /data/config \
    /data/logs \
    /data/nginx/custom \
    /data/nginx/default_host \
    /data/nginx/default_www \
    /data/nginx/dead_host \
    /data/nginx/proxy_host \
    /data/nginx/redirection_host \
    /data/nginx/stream \
    /data/nginx/temp \
    /data/nginx-proxy-manager/custom_ssl \
    /data/gitea/conf \
    /data/portainer \
    /websoft9/media \
    /websoft9/library/apps \
    /websoft9/apphub/swagger-ui

HEALTHCHECK --interval=15s --timeout=5s --retries=6 CMD ["/websoft9/script/platform-healthcheck.sh", "--readiness"]

WORKDIR /websoft9
ENTRYPOINT ["/websoft9/script/platform-container-entrypoint.sh"]