FROM node:22-bookworm-slim AS console-builder

WORKDIR /build/console
COPY console/package.json console/package-lock.json ./
RUN npm ci
COPY console ./
RUN npm run build

FROM golang:1.24 AS portainer-init-builder

WORKDIR /build
COPY docker/product/deployment/init_portainer.go /build/init_portainer.go
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

# Reuse the NPM base image's bundled openresty/nginx binary for the dedicated
# platform-gateway process instead of installing a second nginx package.
FROM jc21/nginx-proxy-manager:2.12.6

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL org.opencontainers.image.title="Websoft9 Product Container"
LABEL org.opencontainers.image.description="Converged Websoft9 runtime with AppHub, Gitea, Portainer, and Nginx Proxy Manager"

ENV WEBSOFT9_RUNTIME_LAYOUT=single-container-target \
    WEBSOFT9_APPHUB_HEALTH_URL=http://127.0.0.1:8080/api/healthz \
    WEBSOFT9_MEDIA_HEALTH_URL=http://127.0.0.1:8081/healthz \
    WEBSOFT9_GITEA_CREDENTIAL_PATH=/data/gitea/credential \
    WEBSOFT9_PORTAINER_CREDENTIAL_PATH=/data/portainer/credential \
    WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH=/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.cert \
    WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH=/etc/custom/platform-gateway/ssl/websoft9-platform-gateway.key \
    WEBSOFT9_NPM_CREDENTIAL_PATH=/data/nginx-proxy-manager/credential.json \
    WEBSOFT9_NPM_SSL_DIR=/data/nginx-proxy-manager/custom_ssl \
    WEBSOFT9_NPM_CERT_MARKER=/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.cert \
    WEBSOFT9_NPM_SSL_KEY_PATH=/data/nginx-proxy-manager/custom_ssl/websoft9-self-signed.key \
    WEBSOFT9_SUPERVISOR_CONFIG=/etc/supervisor/conf.d/websoft9-platform.conf \
    WEBSOFT9_SUPERVISOR_SOCKET=/run/supervisor.sock \
    WEBSOFT9_SUPERVISOR_PIDFILE=/run/supervisord.pid \
    PYTHONPATH=/opt/websoft9-pydeps:/websoft9/apphub:/websoft9/apphub/src \
    PYTHONUNBUFFERED=1

ARG WEBSOFT9_PRODUCT_VERSION=
ARG WEBSOFT9_PRODUCT_EDITION_KEY=

WORKDIR /websoft9

RUN apt-get update && \
    apt-get install --no-install-recommends -y sqlite3 && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/websoft9-npm-frontend && cp -a /app/frontend/. /opt/websoft9-npm-frontend/

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

COPY apphub /websoft9/apphub
RUN WEBSOFT9_PRODUCT_VERSION="${WEBSOFT9_PRODUCT_VERSION}" WEBSOFT9_PRODUCT_EDITION_KEY="${WEBSOFT9_PRODUCT_EDITION_KEY}" python3 - <<'PY'
import json
import os
from pathlib import Path

from src.core.product_catalog import PRODUCT_EDITION_ALIASES, PRODUCT_EDITIONS

metadata_path = Path("/websoft9/apphub/src/config/product_metadata.json")
payload = json.loads(metadata_path.read_text(encoding="utf-8"))

version = (os.environ.get("WEBSOFT9_PRODUCT_VERSION") or str(payload.get("version") or "")).strip()
edition_key = (os.environ.get("WEBSOFT9_PRODUCT_EDITION_KEY") or str(payload.get("edition_key") or "")).strip()
canonical_edition_key = PRODUCT_EDITION_ALIASES.get(edition_key, edition_key)

if not version:
    raise SystemExit("WEBSOFT9_PRODUCT_VERSION is required for product image builds")
if canonical_edition_key not in PRODUCT_EDITIONS:
    supported = ", ".join(sorted(PRODUCT_EDITIONS))
    raise SystemExit(f"Unsupported WEBSOFT9_PRODUCT_EDITION_KEY: {edition_key}. Supported keys: {supported}")

metadata_path.write_text(
    json.dumps({"version": version, "edition_key": canonical_edition_key}, indent=4) + "\n",
    encoding="utf-8",
)
PY
COPY media /websoft9/media
COPY --from=console-builder /build/console/dist /etc/websoft9/console
COPY docker/product/proxy/README.md /data/nginx/README.md
COPY docker/product/proxy/config/http.conf /data/nginx/custom/http.conf
COPY docker/product/proxy/init_nginx.sh /app/init_nginx.sh
COPY docker/product/gateway/nginx.conf /etc/websoft9/platform-gateway/nginx.conf
COPY docker/product/gateway/default.conf /etc/websoft9/platform-gateway/default.conf
COPY docker/product/gateway/platform-gateway-routes.conf /etc/websoft9/platform-gateway/platform-gateway-routes.conf
COPY docker/product/runtime-asset-boundaries.yaml /etc/websoft9/runtime-asset-boundaries.yaml
COPY docker/product/apphub/logging_config.yaml /etc/supervisor/conf.d/logging_config.yaml
COPY docker/product/supervisord.conf /etc/supervisor/conf.d/websoft9-platform.conf
COPY docker/product/s6/websoft9-supervisor/type /etc/s6-overlay/s6-rc.d/websoft9-supervisor/type
COPY docker/product/s6/websoft9-supervisor/run /etc/s6-overlay/s6-rc.d/websoft9-supervisor/run
COPY docker/product/s6/websoft9-supervisor/dependencies.d/prepare /etc/s6-overlay/s6-rc.d/websoft9-supervisor/dependencies.d/prepare
COPY docker/product/s6/user-contents/websoft9-supervisor /etc/s6-overlay/s6-rc.d/user/contents.d/websoft9-supervisor
COPY docker/product/scripts/platform-entrypoint.sh /websoft9/script/platform-entrypoint.sh
COPY docker/product/scripts/platform-healthcheck.sh /websoft9/script/platform-healthcheck.sh
COPY docker/product/scripts/platform-service-control.sh /websoft9/script/platform-service-control.sh
COPY docker/product/scripts/platform-start-gateway.sh /websoft9/script/platform-start-gateway.sh
COPY docker/product/scripts/platform-start-gitea.sh /websoft9/script/platform-start-gitea.sh
COPY docker/product/scripts/platform-start-portainer.sh /websoft9/script/platform-start-portainer.sh
COPY docker/product/scripts/platform-sync-config.sh /websoft9/script/platform-sync-config.sh
COPY docker/product/scripts/platform-sync-runtime-assets.py /websoft9/script/platform-sync-runtime-assets.py

RUN printf '%s\n' '#!/bin/sh' 'exec python3 -m supervisor.supervisord "$@"' > /usr/local/bin/supervisord && \
    printf '%s\n' '#!/bin/sh' 'exec python3 -m supervisor.supervisorctl "$@"' > /usr/local/bin/supervisorctl && \
    printf '%s\n' '#!/bin/sh' 'exec python3 /websoft9/apphub/src/cli/apphub_cli.py "$@"' > /usr/local/bin/apphub && \
    chmod +x /usr/local/bin/supervisord /usr/local/bin/supervisorctl /usr/local/bin/apphub

RUN chmod +x /app/init_nginx.sh \
    /websoft9/script/platform-entrypoint.sh \
    /websoft9/script/platform-healthcheck.sh \
    /websoft9/script/platform-service-control.sh \
    /websoft9/script/platform-start-gateway.sh \
    /websoft9/script/platform-start-gitea.sh \
    /websoft9/script/platform-start-portainer.sh \
    /websoft9/script/platform-sync-config.sh \
    /websoft9/script/platform-sync-runtime-assets.py \
    /etc/s6-overlay/s6-rc.d/websoft9-supervisor/run && \
    mkdir -p /etc/websoft9 \
    /etc/websoft9/console \
    /etc/websoft9/platform-gateway \
    /etc/letsencrypt \
    /etc/s6-overlay/s6-rc.d/websoft9-supervisor/dependencies.d \
    /run/websoft9 \
    /var/log/websoft9 \
    /data/nginx/custom \
    /data/nginx-proxy-manager/custom_ssl \
    /data/gitea/conf \
    /data/portainer \
    /websoft9/library/apps \
    /websoft9/apphub/swagger-ui

VOLUME ["/data/gitea", "/data/portainer", "/data/nginx-proxy-manager", "/etc/letsencrypt", "/etc/modsec", "/etc/custom", "/var/log/websoft9"]

HEALTHCHECK --interval=15s --timeout=5s --retries=6 CMD ["/websoft9/script/platform-healthcheck.sh", "--readiness"]

WORKDIR /app
ENTRYPOINT ["/app/init_nginx.sh"]