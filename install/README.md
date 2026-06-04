# Websoft9 Install

Single-container runtime install and uninstall scripts.

## Quick Install

```bash
# Default install (release channel, latest version)
curl -fsSL https://websoft9.github.io/websoft9/install/install.sh | sudo bash

# With options
sudo bash install.sh --channel release --version latest --console_port 9000
```

## Quick Uninstall

```bash
# Remove container + data volumes
curl -fsSL https://websoft9.github.io/websoft9/install/uninstall.sh | sudo bash

# Remove container only (keep data)
sudo bash uninstall.sh --keep-data

# Remove everything including images
sudo bash uninstall.sh --purge
```

## Scripts

| Script | Purpose |
|---|---|
| `install.sh` | Main entry point — installs Docker, pulls image, starts container |
| `uninstall.sh` | Stop container, remove data, optional image purge |
| `install_docker.sh` | Standalone Docker + Compose installation |
| `install_podman.sh` | Standalone Podman installation (alternative) |

## Install Options

| Option | Default | Description |
|---|---|---|
| `--version` | latest | Image version tag |
| `--channel` | release | Release channel: release / rc / dev |
| `--console_port` | 9000 | Console web UI port |
| `--path` | /opt/websoft9 | Installation directory |
| `--mirrors` | — | Comma-separated Docker registry mirrors |
| `--proxy` | — | HTTP proxy for downloads |

## Uninstall Options

| Option | Description |
|---|---|
| `--keep-data` | Remove container only, preserve named volumes |
| `--purge` | Remove container + volumes + images |
| `--path` | Installation path (default: /opt/websoft9) |

## Architecture

- **No systemd service** — Docker `restart: always` handles lifecycle
- **No Cockpit** — Console UI is bundled in the container image
- **No plugins** — All frontend is built into the single image
- **Single container** — All services run in one container

## Develop

```bash
# Build and test locally
cd docker
docker compose up -d

# Check health
docker exec websoft9 /websoft9/script/platform-healthcheck.sh --readiness

# View logs
docker logs websoft9 -f
```
