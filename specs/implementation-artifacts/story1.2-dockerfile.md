# Story 1.2: Container Image Build

**Epic**: Epic 1 - Infrastructure & Build System  
**Priority**: P0  
**Status**: ✅ Completed (2026-02-10)

## Goal

Define the container image build for the Websoft9 all-in-one console — a single container running all platform services managed by Supervisor.

## Architecture

All services run inside one container, exposed on port 80 via Nginx reverse proxy.

```
┌─────────────────────────────────────────┐
│          websoft9 container              │
│              Port 80                     │
├─────────────────────────────────────────┤
│                                         │
│   Nginx (reverse proxy & static files)  │
│   ┌───────────────────────────────────┐ │
│   │ /            → Dashboard (React)  │ │
│   │ /baas/       → Convex :3210       │ │
│   │ /cockpit/    → cockpit-ws :9090   │ │
│   │ /w9git/      → Gitea :3000        │ │
│   │ /w9deployment/ → Portainer :9000  │ │
│   │ /w9media/    → static files       │ │
│   └───────────────────────────────────┘ │
│                                         │
│   Supervisor-managed services:          │
│   dbus → sshd → cockpit-ws →           │
│   portainer → gitea → nginx → convex   │
│                                         │
│   Volume: /websoft9/data                │
│   Socket: /var/run/docker.sock          │
└─────────────────────────────────────────┘
```

## Image Build

### Multi-Stage Build (`build/Dockerfile`)

The base image `websoft9-base:latest` is built from `build/Dockerfile.base` (Ubuntu 24.04 + pre-installed packages) and is reused in both Stage 1 and Stage 4.

| Stage | FROM | Purpose |
|-------|------|---------|
| 1 - builder | websoft9-base:latest | Download Gitea, Media, Library; copy Dashboard dist |
| 2 - convex | ghcr.io/get-convex/convex-backend:latest | Extract Convex backend binary |
| 3 - portainer | portainer/portainer-ce:2.21.5-alpine | Extract Portainer components |
| 4 - final | websoft9-base:latest (same base) | COPY artifacts from stages 1-3, configure services |

### Base Image (`build/Dockerfile.base`)

Ubuntu 24.04 with pre-installed packages:
- cockpit, cockpit-ws, cockpit-bridge
- supervisor, nginx-light, openssh-server, dbus
- Build tools: unzip, git, curl

### Services

| Service | Binary / Path | Internal Port | Supervisor Priority |
|---------|--------------|---------------|-------------------|
| dbus | /usr/bin/dbus-daemon | - | 10 |
| sshd | /usr/sbin/sshd | 22 (localhost) | 15 |
| cockpit-ws | /usr/lib/cockpit/cockpit-ws | 9090 | 20 |
| portainer | /portainer | 9000 | 25 |
| gitea | /usr/local/bin/gitea | 3000 | 26 |
| nginx | /usr/sbin/nginx | 80 | 30 |
| convex | /usr/local/bin/convex-backend | 3210 | 40 |

### Nginx Routing

| Path | Target | Notes |
|------|--------|-------|
| `/` | `/usr/share/nginx/html/dashboard` | React SPA (try_files → /index.html) |
| `/baas/` | `http://127.0.0.1:3210/` | Convex BaaS API + WebSocket |
| `/cockpit/` | `http://127.0.0.1:9090` | Cockpit WebSocket (for cockpit.js) |
| `/w9git/` | `http://127.0.0.1:3000/` | Gitea |
| `/w9deployment/` | `http://127.0.0.1:9000/` | Portainer + CORS |
| `/w9media/` | `/websoft9/runtime/media/` | Static media files |

### Data Layout

```
/websoft9/data/          ← VOLUME, persistent
├── baas/                ← Convex data
├── portainer/           ← Portainer data
└── gitea/               ← Gitea repos, config, sessions

/websoft9/runtime/       ← baked into image
├── media/               ← static media assets
└── library/             ← library plugin
```

### Configuration Files (copied from `build/`)

| Source | Destination |
|--------|------------|
| build/supervisord.conf | /etc/supervisor/supervisord.conf |
| build/nginx.conf | /etc/nginx/nginx.conf |
| build/cockpit.conf | /etc/cockpit/cockpit.conf |
| build/gitea.ini | /etc/gitea/app.ini |
| build/entrypoint.sh | /entrypoint.sh |
| build/menu_override/*.json | /etc/cockpit/ |

### Container Runtime

- **Expose**: Port 80
- **Volume**: `/websoft9/data`
- **Entrypoint**: `/entrypoint.sh` → initializes directories, sets permissions, starts dbus, then `exec supervisord`
- **Health check**: `supervisorctl status | grep RUNNING`
- **Default user**: websoft9 / websoft9 (sudo, NOPASSWD)

## Build & Run

```bash
make build-base    # Build websoft9-base:latest
make build         # Build websoft9:latest
make start         # Start container on port 9091
make stop          # Stop container
make logs          # View logs
```

## Acceptance Criteria

- [x] All 7 services start and remain RUNNING under Supervisor
- [x] Dashboard accessible at `/`
- [x] Convex API reachable at `/baas/`
- [x] Cockpit WebSocket functional at `/cockpit/`
- [x] Gitea accessible at `/w9git/`
- [x] Portainer accessible at `/w9deployment/`
- [x] Media files served at `/w9media/`
- [x] `/websoft9/data` volume persists across container restarts
- [x] Health check passes
- [x] Image builds successfully via `make build`

## References

- [build/Dockerfile](../../build/Dockerfile)
- [build/Dockerfile.base](../../build/Dockerfile.base)
- [build/supervisord.conf](../../build/supervisord.conf)
- [build/nginx.conf](../../build/nginx.conf)
- [build/entrypoint.sh](../../build/entrypoint.sh)
- [Story 1.4: Makefile](./story1.4-makefile.md)
