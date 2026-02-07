# Story 1.2: Dockerfile Optimization & Cockpit Integration

**Epic**: Epic 1 - Infrastructure & Build System  
**Priority**: P0  
**Status**: ✅ Completed

## Objective
Integrate Cockpit, Portainer, Gitea, and Apphub into a single container image for fully containerized deployment.

## Implementation

### Image Architecture
**Two-layer Images**:
- `websoft9/cockpit-base:latest` - Base image (Cockpit + system dependencies)
- `websoft9/cockpit:latest` - Business image (all services integrated)

**Multi-stage Build**:
- Builder stage: Download external components (Gitea, Media, Library) + install Python dependencies
- Portainer stage: Copy Portainer binaries
- Final stage: Assemble all services

### Service Integration
**In-container Services** (managed by Supervisor):
- dbus, sshd
- cockpit-ws (port 9090)
- portainer (port 9000)
- gitea (port 3000)
- nginx (port 80)
- apphub (port 8080)
- apphub-cron

**Unified Gateway** (Nginx):
- Only port 80 exposed externally
- Path routing: `/` → Cockpit, `/w9deployment/` → Portainer, `/w9git/` → Gitea, `/w9api/` → Apphub
- `/w9media/` → Static files (served directly by Nginx, no longer using Python service)

### Key Optimizations
- **Build Cache**: Layered by change frequency (external downloads → Python deps → source code)
- **Image Naming**: Renamed from `websoft9-base` to `cockpit-base` for better semantics
- **Cockpit Plugins**: Auto-download and install from version.json (portainer, nginx, gitea, myapps, appstore, settings, navigator)
- **Menu Override**: Configuration files placed in `/etc/cockpit/` (not `/usr/share/cockpit/shell/`)
- **Default User**: Created websoft9/websoft9 account in container for authentication

## Build Commands
```bash
# Base image
docker build -f docker/cockpit/Dockerfile.base -t websoft9/cockpit-base:latest docker/cockpit/

# Business image
docker build -f docker/cockpit/Dockerfile -t websoft9/cockpit:latest .

# Run
make start-cockpit 9091
```

## Key Files
- `docker/cockpit/Dockerfile.base` - Base image
- `docker/cockpit/Dockerfile` - Business image
- `docker/cockpit/supervisord.conf` - Service configuration (unified management for all services)
- `docker/cockpit/nginx.conf` - Gateway configuration
- `docker/cockpit/entrypoint.sh` - Startup script
- `Makefile` - Build commands (updated image names)

## Issues Fixed
- supervisord.conf must overwrite system default config (`/etc/supervisor/supervisord.conf`)
- uvicorn runs via `python3 -m uvicorn` approach
- swagger-ui directory needs creation (avoid StaticFiles error)
- media static assets served directly by Nginx (better performance)

## Acceptance Results
✅ All services running normally  
✅ Cockpit interface accessible, menu displays correctly  
✅ Portainer, Gitea, Apphub accessible via path forwarding  
✅ Static asset paths working properly
