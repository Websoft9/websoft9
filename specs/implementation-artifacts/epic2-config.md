# Epic 2: Configuration Management

## Overview
**Objective**: Centralized configuration management for microservices in containerized environment

**Business Value**: Single source of truth for all service configs, zero manual sync, instant rollback capability

**Priority**: P1

**Status**: Not Started

**Core Requirements**:
1. **Watch** - Monitor config.ini changes in real-time
2. **Sync** - Propagate configuration to target services (containers and internal processes)
3. **Reload** - Restart/reload services when configuration requires it (supports both container restart via Docker API and internal process restart via supervisord)
4. **Environment Variables Management**:
   - Independent env vars (standalone environment variables)
   - Mapped env vars (derived from config.ini sections)
5. **Service Initialization**:
   - Initialize all services with default configurations
   - Connection testing between main program and services
   - Health check validation

## Architecture Decision

**Pattern**: Integrated Config-Sync within Apphub Container

**Deployment**: Config-sync runs as **background thread inside FastAPI process**, not as separate process or container

**Rationale**: 
- Zero additional processes (keeps 8 existing processes)
- Minimal resource overhead (shares FastAPI process memory)
- Simplified deployment (no supervisord config needed)
- Fast development and debugging
- Perfect for all-in-one philosophy

**Components**:
1. **config.ini** - User-modifiable config (API accessible, credentials, preferences)
2. **system.ini** - System-level config (API read-only, paths, core settings)
3. **config-sync thread** - Background thread within FastAPI process
4. **Service init scripts** - Bootstrap configuration on container start

**Flow**:
```
Container Start → FastAPI startup event → spawns config-sync background thread
Runtime Change → config-sync thread watches config.ini → pushes to service volumes → triggers reload
Manual Update → FastAPI endpoint → writes config.ini → thread auto-detects change
```

**Thread Management**:
- Python threading.Thread with daemon=True
- Launched via FastAPI @app.on_event("startup")
- Shares same process as uvicorn (no new PID)
- Automatic cleanup on process exit

**Configuration Architecture**:
```
Cockpit Container
│
├─ Apphub (Configuration Center)
│  ├─ config.ini ← User-modifiable (API accessible)
│  ├─ system.ini ← System-level (API read-only)
│  ├─ ConfigManager (Read/Write API)
│  └─ config-sync thread (Watch & Push)
│        │
│        ├─ Watch: inotify monitors config.ini changes
│        ├─ Transform: INI → service-specific format
│        ├─ Push: Write to service config files
│        └─ Reload: Trigger service reload (< 5s)
│
├─ Services (Config Consumers)
│  ├─ Gitea: /etc/gitea/app.ini
│  ├─ Portainer: /portainer_data/config.json
│  └─ Cockpit: /etc/cockpit/config.json
│
└─ Flow: User → API → config.ini → sync thread → service files → reload
```

**Configuration File Strategy**:
- **config.ini**: User-facing settings (credentials, URLs, preferences) - Modifiable via API
- **system.ini**: System settings (paths, core config) - NOT modifiable via API
- **Stability**: Preserve existing business logic, dual-config approach for backward compatibility

**Init vs Runtime**:
- **Init** (Story 2.5): First-time setup, generate defaults, write initial config files
- **Runtime** (Story 2.2): Watch changes, sync to services, trigger reloads

## Stories

- [ ] Story 2.1: Configuration API Enhancement
  - Enhance existing `/settings` API (already supports GET all, GET by section, PUT update)
  - Add batch update endpoint (PUT multiple keys at once)
  - Add config validation before write (schema validation)
  - Add audit logging for all write operations

- [ ] Story 2.2: Config-Sync Thread Implementation
  - Background thread launched from FastAPI startup event
  - inotify-based config.ini watcher (watchdog library)
  - Config transformation engine (INI → service-specific format)
  - Service reload capability:
    - External containers: Docker API restart (via docker.sock)
    - Internal processes: supervisord XML-RPC API restart
    - Graceful reload via service HTTP APIs (zero downtime)
  - Thread-safe implementation with proper locking
  - Graceful shutdown via daemon thread pattern

- [ ] Story 2.3: Service Entrypoint Integration
  - Create init-config.sh template
  - Integrate into proxy/git/deployment entrypoints
  - Dependency ordering (wait for apphub ready)

- [ ] Story 2.4: Environment Variables Management
  - Support two types of environment variables:
    - Type 1: Independent env vars (managed separately, no config.ini mapping)
    - Type 2: Mapped env vars (auto-generated from config.ini sections)
  - Environment variable injection to containers on start/restart
  - API endpoints for env var CRUD operations
  - Sync env vars to .env files for docker-compose services

- [ ] Story 2.5: Service Initialization & Connection Testing
  - Initialize all microservices with default configurations:
    - Nginx Proxy Manager (admin user, SSL certificates)
    - Gitea (repository setup, webhook config)
    - Portainer (endpoint registration)
  - Connection testing suite:
    - Test apphub → proxy connectivity
    - Test apphub → gitea connectivity
    - Test apphub → portainer connectivity
    - Validate API endpoints are accessible
  - Health check endpoints for each service
  - Retry mechanism with exponential backoff
  - Initialization status reporting API

- [ ] Story 2.6: Git-Based Version Control
  - Auto-commit config.ini changes to Gitea
  - Config diff visualization
  - One-click rollback to previous version

- [ ] Story 2.7: Configuration Validation Engine
  - Schema validation for each section
  - Port conflict detection
  - Credential strength checking

- [ ] Story 2.8: Configuration Templates
  - Default config templates for common scenarios
  - Environment-based config (dev/staging/prod)
  - Variable substitution support

- [ ] Story 2.9: Change Audit & Notification
  - Webhook notifications on config change
  - Audit log with who/when/what
  - Slack/Discord integration

## Success Metrics
- Config propagation time < 5s
- Service startup with config < 15s
- Zero config drift incidents
- Rollback success rate > 99%

## Dependencies
- Prerequisites: Epic 1 (Docker infrastructure)
- Downstream: All service deployments

## Technical Details

**Config-Sync Thread Spec**:
```yaml
Deployment: Background thread in apphub FastAPI process
Location: /websoft9/apphub/src/daemon/config_sync.py
Language: Python 3.11 (shares apphub dependencies)
Dependencies: watchdog, requests (already in requirements.txt)
Resource: ~5-10MB memory (shared with FastAPI process)
```

**Thread Architecture in Apphub Container**:
```
apphub container (still 8 processes)
├── Process 1-7: existing services
└── uvicorn process (PID 8)
    ├── Main thread: FastAPI request handling
    └── Background thread: config_sync watcher (daemon thread)
```

**FastAPI Integration**:
```python
# src/main.py
from fastapi import FastAPI
import threading
from src.daemon.config_sync import start_config_watcher

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Launch config sync thread on startup"""
    watcher_thread = threading.Thread(
        target=start_config_watcher,
        daemon=True,  # Auto-terminate with main process
        name="config-sync-watcher"
    )
    watcher_thread.start()
    logger.info("Config sync thread started")
```

**API Endpoints**:
- GET `/api/v1/settings/{section}` - Get specific section
- PUT `/api/v1/settings/{section}` - Update with validation
- POST `/api/v1/settings/reload` - Trigger manual sync
- GET `/api/v1/settings/history` - Git commit history

**Security**:
- Config API requires `x-api-key` header
- Sensitive values encrypted at rest
- Audit log for all write operations
