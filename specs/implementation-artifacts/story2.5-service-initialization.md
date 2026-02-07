# Story 2.5: Service Initialization & Connection Testing

Status: ready-for-dev

## Story

As a **system administrator**,
I want **all microservices to be initialized with default configurations and have connectivity validated**,
so that **the platform is ready for use immediately after deployment**.

## Acceptance Criteria

1. Initialize all services in cockpit container with default configurations:
   - ✓ Cockpit (admin user, system settings)
   - ✓ Apphub (database schema, default config.ini)
   - ✓ Gitea (repository setup, webhook config)
   - ✓ Portainer (endpoint registration)

2. Connection testing suite passes:
   - ✓ Test apphub → cockpit connectivity
   - ✓ Test apphub → gitea connectivity
   - ✓ Test apphub → portainer connectivity
   - ✓ Validate all API endpoints are accessible

3. Health check endpoints return HTTP 200 with valid JSON response containing `status: "healthy"` field

4. Retry mechanism with exponential backoff (3 retries, 1s/2s/4s delays)

5. Initialization status reporting API available at `/api/v1/init/status`

6. Apphub starts successfully (HTTP 200 on health endpoint) even if one or more service initialization fails (non-blocking behavior)

## Tasks / Subtasks

- [ ] Task 1: Container-Level Service Initialization (AC: 1)
  - [ ] Create `/data/dev/websoft9/docker/cockpit/init-services.sh` script
  - [ ] Ensure config.ini exists (copy from template or generate defaults)
  - [ ] Ensure system.ini exists (copy from template)
  - [ ] Generate secure random passwords (20+ chars) for services if config.ini is empty
  - [ ] Encrypt and store passwords in config.ini (AES-256) using helper script
  - [ ] Init Cockpit: Ensure websoft9 user exists (already done in entrypoint.sh)
  - [ ] Init Apphub: Create SQLite DB schema if not exists, ensure config directory
  - [ ] Init Gitea: Background job to create admin user after gitea starts (keep existing logic)
  - [ ] Init Portainer: Background job to register Docker endpoint after portainer starts
  - [ ] Create master encryption key if not exists (/websoft9/.secrets/master.key, chmod 600)
  - [ ] Update entrypoint.sh to call init-services.sh before supervisord

- [ ] Task 2: Connection Testing Suite (AC: 2)
  - [ ] Create `/data/dev/websoft9/docker/cockpit/test-connections.sh` script
  - [ ] Implement curl-based connectivity tests (cockpit:9090, git:3000, portainer:9000)
  - [ ] Implement retry logic with exponential backoff (sleep 1, 2, 4)
  - [ ] Log results to /websoft9/apphub/logs/init.log
  - [ ] Call from entrypoint.sh after supervisord starts (background job)

- [ ] Task 3: Health Check Endpoints (AC: 3)
  - [ ] Define health check interface for each service
  - [ ] Implement health check aggregator

- [ ] Task 4: Initialization Status API (AC: 5, 6)
  - [ ] Create `/api/v1/init/status` endpoint in apphub (reads from status file)
  - [ ] init-services.sh writes status to /websoft9/apphub/logs/init-status.json
  - [ ] Return JSON with per-service initialization status
  - [ ] Include error details if initialization fails
  - [ ] Ensure apphub health endpoint returns 200 regardless of init failures

## Dev Notes

### Architecture Context
- **Primary Location**: `/data/dev/websoft9/docker/cockpit/entrypoint.sh` (Container init script)
- **Helper Scripts**: `/data/dev/websoft9/docker/cockpit/init-services.sh` (New - service initialization logic)
- **Trigger**: Container startup via Docker entrypoint
- **Pattern**: Sequential initialization in entrypoint.sh
- **Execution**: Services initialized before supervisord starts
- **Non-modification Constraint**: DO NOT modify files under `/websoft9/apphub/src/` - initialization happens at container layer

### Initialization Strategy
**Container-Level Initialization** (docker/cockpit/):
```bash
entrypoint.sh (main entry)
├─ 1. Create directories & set permissions
├─ 2. Call init-services.sh (NEW)
│     ├─ Init Cockpit (admin user via useradd)
│     ├─ Init Apphub (config.ini/system.ini defaults, DB schema)
│     ├─ Init Gitea (admin user via gitea CLI, delayed)
│     └─ Init Portainer (Docker endpoint setup, delayed)
├─ 3. Start dbus, nginx, SSH
└─ 4. exec supervisord (all services start)
```

**Key Points**:
- Initialization logic in `docker/cockpit/init-services.sh` (NEW file)
- Existing `entrypoint.sh` calls the init script before starting supervisord
- Config files managed at container level, not in apphub source code
- Gitea/Portainer init delayed (background, after services start)

### Configuration File Strategy
**Preserve Existing Business Stability**:
- **config.ini**: User-facing configuration, modifiable via API (credentials, preferences)
- **system.ini**: System-level configuration, NOT modifiable via API (paths, core settings)
- **Read Priority**: config.ini first, fallback to system.ini
- **API Exposure**: Only config.ini exposed to `/api/v1/settings` endpoints

### Configuration Management
**Dual Configuration Architecture**: `/websoft9/apphub/src/config/`

**config.ini** - User-modifiable configuration (API accessible):
- Service credentials (encrypted)
- Service URLs and ports
- User preferences
- Modifiable via `/api/v1/settings` endpoints

**system.ini** - System-level configuration (API read-only):
- System paths and directories
- Core service settings
- Bootstrap configuration
- NOT modifiable via API (file-only access)

All services read from both configuration files with dedicated sections:

**config.ini** (User-modifiable via API):
```ini
[cockpit]
admin_user = admin
admin_password_encrypted = AES256:xxxxx

[git]
admin_user = gitea_admin
admin_password_encrypted = AES256:xxxxx
webhook_secret_encrypted = AES256:xxxxx

[portainer]
admin_user = admin
admin_password_encrypted = AES256:xxxxx
endpoint_name = local

[apphub]
api_key_encrypted = AES256:xxxxx
log_level = INFO
```

**system.ini** (System-level, API read-only):
```ini
[paths]
database_path = /var/lib/apphub/db.sqlite
log_directory = /websoft9/apphub/logs
config_directory = /websoft9/apphub/src/config

[services]
git_api_url = http://git:3000
portainer_api_url = http://portainer:9000
cockpit_api_url = http://cockpit:9090

[security]
encryption_key_file = /websoft9/.secrets/master.key
```

**Security Pattern**:
- **NO plaintext passwords**: All sensitive values stored encrypted
- **Auto-generation**: Random passwords generated on first initialization (20+ chars)
- **Encryption**: AES-256-CBC with master key stored in secure file
- **Master Key**: `/websoft9/.secrets/master.key` (permissions: 600, owner: root)
- **ConfigManager Enhancement**: Automatically decrypt `*_encrypted` fields when reading

**Config Access**: Use enhanced `ConfigManager` class from `src/core/config.py`:
```python
from src.core.config import ConfigManager

# For user-modifiable config (API accessible)
config = ConfigManager("config.ini")
gitea_pwd = config.get_value("git", "admin_password_encrypted")  # Auto-decrypts

# For system config (read-only via API)
system = ConfigManager("system.ini")
db_path = system.get_value("paths", "database_path")
git_url = system.get_value("services", "git_api_url")

# Read strategy: Check config.ini first, fallback to system.ini for missing keys
```

### Service Endpoints
```yaml
Cockpit Container Services (websoft9-cockpit):

Cockpit:
  Port: 9090
  Health: http://cockpit:9090/ping
  Init: Already done in entrypoint.sh (websoft9 user creation)

Apphub:
  Port: 8080
  API: http://localhost:8080/api/v1
  Health: http://localhost:8080/health
  Init: 
    - SQLite DB schema creation (via init-services.sh)
    - config.ini/system.ini defaults
    - Encryption key generation

Gitea:
  Port: 3000
  API: http://git:3000/api/v1
  Health: http://git:3000/api/healthz
  Init: Background job in entrypoint.sh (keep existing: sleep 15 + gitea admin user create)

Portainer:
  Port: 9000
  API: http://portainer:9000/api
  Health: http://portainer:9000/api/status
  Init: Background job in init-services.sh (Docker endpoint registration after portainer ready)
```

### File Structure
```
/data/dev/websoft9/docker/cockpit/
├── entrypoint.sh              # Main entry (modified to call init scripts)
├── init-services.sh           # NEW: Service initialization logic
├── test-connections.sh        # NEW: Connection testing script
├── encrypt-password.py        # NEW: Helper for password encryption
└── config-templates/          # NEW: Default config templates
    ├── config.ini.default
    └── system.ini.default
```

### Container Architecture Notes

**Cockpit Container (websoft9-cockpit)** - All services in THIS story:
- Multi-process container running: Cockpit, Apphub, Gitea, Portainer
- All services initialized within same container
- Initialization happens during cockpit container startup
- Services communicate via internal networking (localhost/container hostname)

**Separate Service Containers** (e.g., Nginx Proxy Manager):
- Independent Docker containers (NOT in cockpit container)
- **Out of scope for this story**
- Future consideration: Story for external container initialization
- Pattern: Cockpit container init (this story) → External containers init (future story)

### Error Handling
- Log all initialization failures to `/websoft9/apphub/logs/init.log`
- Non-blocking: Allow apphub to start even if some services fail initialization
- Expose failures via `/api/v1/init/status` for troubleshooting
- **Security**: Never log decrypted passwords - log "password: ***" instead

### Security Considerations
- **Password Storage**: All passwords encrypted with AES-256, never plaintext
- **Master Key**: Stored in `/websoft9/.secrets/master.key` with 600 permissions
- **Auto-Generation**: Random passwords (20+ chars: alphanumeric + symbols) on first init
- **Key Rotation**: Future story - for now, master key generated once and persists
- **Audit**: Log password generation events (not the passwords themselves)

### Testing Standards
- Unit tests: Mock HTTP calls, test retry logic
- Integration tests: Use docker-compose test environment
- Coverage target: >80% for init_service.py

### References
- [Source: specs/implementation-artifacts/epic-02-config.md#Story 2.5]
- [Architecture: docs/architecture.md#Microservices]

## Dev Agent Record

### Agent Model Used

_To be filled by dev agent_

### Completion Notes List

_To be filled by dev agent_

### File List

_To be filled by dev agent_
