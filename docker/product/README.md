# Websoft9 Product Container

This directory contains the converged single-container build assets introduced for Story 1.4 and hardened for the Story 1.5 runtime split.

The product container keeps Nginx Proxy Manager as the PID 1 runtime because its native s6 overlay requires that ownership. A dedicated platform-gateway nginx process, plus AppHub, Gitea, and Portainer, are started under an embedded supervisord layer that is attached as an additional s6 service.

Key runtime assets:

- `Dockerfile`: builds the converged image without relying on `docker/apphub/media.zip`
- `runtime-asset-boundaries.yaml`: canonical asset-boundary manifest for backup, restore, and migration planning
- `supervisord.conf`: supervises AppHub, media, Gitea, Portainer, and cron
- `gateway/`: image-managed config for the dedicated platform-gateway process that serves product-origin ingress on 9000 inside the container
- `s6/`: adds the `websoft9-supervisor` service into the NPM base image's s6 service graph
- `proxy/`, `deployment/`, `apphub/`, and `scripts/`: product-localized build inputs so the converged image no longer copies runtime assets directly from legacy docker sibling directories

Edition and release control:

- Product edition definitions are code-owned in `apphub/src/core/product_catalog.py`.
- Current supported editions are `free` (2 apps), `starter` (3 apps), `standard` (10 apps), and `enterprise` (unlimited apps).
- Runtime metadata in `apphub/src/config/product_metadata.json` is only the active release pointer: semantic version plus `edition_key`.
- Product image builds can set the active release directly with Docker build args instead of editing files before publishing.
- Preferred release command: `scripts/build_product_image.sh --tag <image:tag> --version 2.2.17 --edition-key free`

Inside the running container:

- `platform-entrypoint.sh` owns runtime bootstrap and status-file updates
- `platform-service-control.sh` provides per-service start, stop, restart, and status operations
- `platform-healthcheck.sh` distinguishes ready, degraded, and failed states
- `platform-start-gateway.sh` starts the dedicated platform-gateway nginx process under supervisord using `/usr/sbin/nginx` and image-managed gateway config under `/etc/websoft9/platform-gateway`

Files workspace runtime requirement:

- The converged product container must have access to the host Docker volumes root if the native Files workspace is enabled, because the in-container `files-agent` performs real filesystem operations inside approved volume roots.
- Do not hard-code `/var/lib/docker/volumes` as that source path. The product sync/recreate flow should detect Docker's active data-root, bind the resolved `<DockerRootDir>/volumes` path into the container, and pass the same resolved root to `files-agent` through `WEBSOFT9_FILES_AGENT_ALLOWED_ROOTS`.
- The browser-facing Files workspace should remain rooted at the virtual `/volumes` path. Host absolute paths, Docker `Mountpoint` values, and `_data` implementation details should stay behind AppHub and `files-agent`.

Portainer runtime requirement:

- The converged product container must have `/var/run/docker.sock` mounted if Portainer is expected to auto-create and manage the local Docker environment. Without that bind mount, Portainer admin initialization can succeed while local environment initialization fails, leaving the UI in the Environment Wizard with no endpoint.

Proxy responsibility split for Story 1.5:

- Product entry on `/` now serves the built console SPA from `/etc/websoft9/console`, and the dedicated `platform-gateway` nginx process under supervisord now owns internal port `9000` plus reserved prefixes such as `/api/`, `/media/`, `/w9deployment/`, `/w9proxy/`, `/w9git/`, and `/w9gateway/healthz`.
- User application domains remain under Nginx Proxy Manager `proxy_host` configs and keep NPM as the app-access owner in MVP.
- The single-container delivery model still holds, but platform ingress is no longer served by the NPM default-host runtime or cockpit-era fallback pages; the gateway process now owns product-origin routing and platform TLS assets explicitly instead of reusing NPM `custom_ssl.conf`.

Recoverability boundary split for Story 1.6:

- Stable mounted service assets are `/data/gitea`, `/data/portainer`, `/data/nginx-proxy-manager`, `/etc/letsencrypt`, `/etc/modsec`, `/etc/custom`, and `/var/log/websoft9`.
- Platform gateway TLS material now lives under `/etc/custom/platform-gateway`, separate from NPM-managed `/data/nginx-proxy-manager/custom_ssl`.
- Copy-forward assets that should not be shadowed by empty Docker volumes are `/websoft9/library` and `/websoft9/media`.
- Ephemeral runtime state such as `/run/websoft9` remains rebuildable and is not treated as a backup source of truth.
- The machine-readable source of truth for these boundaries is `/etc/websoft9/runtime-asset-boundaries.yaml` inside the built image.
- The base NPM image still exposes a legacy `/data` volume. Treat that inherited root as compatibility-only and use the service-owned subpaths above as the real backup and migration boundaries.