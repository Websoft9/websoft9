# Technical Architecture Document
# Websoft9 Containerized Application Platform

**Created:** 2026-01-04  
**Architect:** Websoft9 Team  
**Version:** 2.0  
**Status:** Active

---

## 1. Architecture Overview

### 1.1 Architecture Philosophy

**Integrated Modular Architecture**

Websoft9 follows a **composition-over-complexity** approach, integrating proven open-source components rather than building proprietary solutions.

**Core Principles:**
1. **Leverage Proven Technologies**: Use battle-tested open-source tools
2. **Avoid Reinvention**: Integrate existing solutions instead of building from scratch
3. **Cloud-Neutral**: Run anywhere Docker runs (cloud or bare metal)
4. **Single-Server Optimized**: Efficient resource usage for typical workloads
5. **Extensible**: Plugin architecture for future capabilities

```
┌─────────────────────────────────────────────────────────────┐
│                     Websoft9 Platform                        │
├─────────────────────────────────────────────────────────────┤
│                  Cockpit Web Framework                       │
│              (System Management Interface)                   │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Websoft9    │   Nginx      │  Portainer   │    Gitea       │
│  Plugins     │   Proxy      │  Container   │    Git Repo    │
│  (Custom)    │   Manager    │   Management │    Service     │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                      AppHub API                              │
│              (Python FastAPI - Orchestration)                │
├──────────────────────────────────────────────────────────────┤
│                    Docker Engine                             │
│              (Container Runtime + Networking)                │
├───────────┬───────────┬───────────┬───────────┬──────────────┤
│   Redis   │   App     │   App     │   App     │   ...        │
│   Cache   │   1       │   2       │   N       │  (200+ apps) │
└───────────┴───────────┴───────────┴───────────┴──────────────┘
           │                                      │
           ▼                                      ▼
    Host File System                      Docker Volumes
    /data/websoft9/                       (Persistent Data)
```

---

## 2. Technology Stack

### 2.1 Core Components

| Layer | Technology | Version | Purpose | Source |
|-------|-----------|---------|---------|--------|
| **Web Framework** | RedHat Cockpit | 276+ | System management UI | Upstream |
| **Container Runtime** | Docker | 20.10+ | Application isolation | Official |
| **Orchestration** | Docker Compose | 2.x | Multi-container apps | Official |
| **Proxy/SSL** | Nginx Proxy Manager | 2.x | Reverse proxy + Let's Encrypt | jc21/npm |
| **Container UI** | Portainer | 2.x | Docker GUI management | portainer/portainer-ce |
| **Git Service** | Gitea | 1.x | Self-hosted Git | gitea/gitea |
| **Cache/Queue** | Redis | 7.x | Session storage + events | Official redis |
| **AppHub API** | Python + FastAPI | 3.11+/0.100+ | Custom business logic | Custom-built |
| **Plugin System** | Cockpit Packages | N/A | Modular extensions | Custom |

### 2.2 Supporting Technologies

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Database** | SQLite (default) | AppHub metadata storage |
| **Backup** | Duplicati | Encrypted backup automation |
| **Monitoring** | Prometheus (optional) | Metrics collection |
| **Visualization** | Grafana (optional) | Monitoring dashboards |
| **OS** | Ubuntu/Debian/CentOS/Rocky | Linux host OS |
| **Firewall** | ufw / firewalld | Network security |

### 2.3 Development Tools

- **Language**: Python 3.11+ (AppHub), JavaScript (Cockpit plugins)
- **Package Manager**: pip (Python), npm/yarn (JavaScript)
- **Testing**: pytest (Python), jest (JavaScript)
- **Linting**: flake8, eslint
- **CI/CD**: GitHub Actions
- **Documentation**: Markdown, OpenAPI/Swagger

---

## 3. Component Architecture

### 3.1 Cockpit Web Framework

**Role**: Primary user interface and system management

**Integration Approach:**
```
User Browser
     ↓
Cockpit (Port 9000)
     ↓
├─ System Management (built-in)
│  ├─ Terminal
│  ├─ File Browser
│  ├─ Network Config
│  ├─ Service Management
│  └─ User Management
│
└─ Websoft9 Plugins (custom packages)
   ├─ App Catalog Plugin
   ├─ App Management Plugin
   ├─ Proxy Management Plugin (iframe to Nginx PM)
   └─ Git Management Plugin (iframe to Gitea)
```

**Key Features:**
- Multi-user authentication via PAM (Linux accounts)
- Session management with cookie-based auth
- WebSocket support for real-time updates
- Modular plugin architecture

**Plugin Development:**
```javascript
// Cockpit package structure
/usr/share/cockpit/websoft9-apps/
├── manifest.json       // Plugin metadata
├── index.html          // Entry point
├── app.js              // Application logic
└── app.css             // Styling
```

**Communication:**
- Cockpit ↔ AppHub: HTTP REST API
- Cockpit ↔ System: D-Bus (built-in)
- Cockpit ↔ Docker: Unix socket (`/var/run/docker.sock`)

---

### 3.2 AppHub API (Python FastAPI)

**Role**: Custom business logic and orchestration layer

**Architecture:**
```
AppHub (FastAPI)
├── src/
│   ├── api/
│   │   └── v1/
│   │       ├── routers/
│   │       │   ├── apps.py          # Application CRUD
│   │       │   ├── settings.py      # Configuration
│   │       │   ├── domains.py       # Domain management
│   │       │   └── logs.py          # Log retrieval
│   │       └── deps.py              # Dependencies (auth, db)
│   ├── core/
│   │   ├── docker.py                # Docker client wrapper
│   │   ├── compose.py               # Compose file parser
│   │   ├── templates.py             # App template loader
│   │   └── proxy.py                 # Nginx PM integration
│   ├── schemas/
│   │   ├── app.py                   # Pydantic models
│   │   └── response.py              # API response schemas
│   ├── models/                      # Database models (SQLAlchemy)
│   ├── db/                          # Database utilities
│   └── main.py                      # FastAPI app entry point
└── requirements.txt
```

**Key Responsibilities:**
1. **Template Management**: Load and validate docker-compose templates from [docker-library](https://github.com/Websoft9/docker-library)
2. **Container Orchestration**: Deploy, start, stop, restart applications via Docker API
3. **Configuration Management**: Manage environment variables and volumes
4. **Proxy Integration**: Create Nginx proxy hosts programmatically
5. **Metadata Storage**: Track installed apps, configurations, versions

**API Design Patterns:**
```python
# Standardized response format
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    code: int
    message: str
    data: Optional[T] = None

# Example endpoint
@router.post("/apps", response_model=ApiResponse[AppResponse])
async def install_app(
    app_data: AppInstall,
    current_user: dict = Depends(get_current_user)
) -> ApiResponse[AppResponse]:
    try:
        result = await app_service.install(app_data)
        return ApiResponse(
            success=True,
            code=201,
            message="Application installed successfully",
            data=result
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Database Schema:**
```sql
-- Installed applications
CREATE TABLE apps (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    template_id TEXT NOT NULL,  -- Reference to docker-library template
    compose_path TEXT NOT NULL,  -- Path to docker-compose.yml
    status TEXT NOT NULL,        -- running, stopped, error
    domain TEXT,                 -- Associated domain
    created_at DATETIME,
    updated_at DATETIME
);

-- Application environment variables
CREATE TABLE app_env_vars (
    id INTEGER PRIMARY KEY,
    app_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
);
```

---

### 3.3 Nginx Proxy Manager

**Role**: Reverse proxy and SSL certificate automation

**Integration:**
- **Access**: Embedded in Cockpit via iframe (seamless UX)
- **API**: AppHub communicates via Nginx PM REST API
- **Database**: SQLite (independent from AppHub)

**Proxy Host Creation Flow:**
```
User creates app in AppHub
     ↓
AppHub deploys container (Docker)
     ↓
AppHub calls Nginx PM API
     ↓
POST /api/nginx/proxy-hosts
{
  "domain_names": ["myapp.example.com"],
  "forward_scheme": "http",
  "forward_host": "container_name",
  "forward_port": 8080,
  "certificate_id": 0,  // 0 = request new Let's Encrypt
  "ssl_forced": true
}
     ↓
Nginx PM configures virtual host
     ↓
Let's Encrypt certificate issued
     ↓
HTTPS traffic routed to container
```

**Nginx Configuration Generated:**
```nginx
server {
    listen 80;
    server_name myapp.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name myapp.example.com;

    ssl_certificate /data/letsencrypt/live/npm-1/fullchain.pem;
    ssl_certificate_key /data/letsencrypt/live/npm-1/privkey.pem;

    location / {
        proxy_pass http://container_name:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### 3.4 Portainer

**Role**: Visual Docker management interface

**Integration:**
- **Access**: Embedded in Cockpit (alternative: standalone port 9000)
- **Authentication**: Shared with Cockpit (via reverse proxy)
- **Scope**: Read/write access to Docker socket

**Key Features Used:**
- Container lifecycle management (start, stop, restart, logs)
- Docker Compose stack deployment
- Volume and network management
- Image management (pull, remove, build)
- Container resource usage metrics

**AppHub ↔ Portainer Relationship:**
- **AppHub**: High-level application abstraction (install WordPress)
- **Portainer**: Low-level container operations (inspect nginx container)
- **Use Case**: AppHub for app deployment, Portainer for debugging

---

### 3.5 Gitea

**Role**: Self-hosted Git repository service

**Integration:**
- **Access**: Embedded in Cockpit or standalone URL
- **Use Cases**:
  - Store application configurations
  - Version control for docker-compose files
  - Code repositories for custom applications
  - Infrastructure-as-Code storage

**Typical Workflow:**
```
Developer commits docker-compose.yml to Gitea
     ↓
AppHub watches repository (webhook)
     ↓
On push, AppHub pulls latest compose file
     ↓
AppHub redeploys application with new config
```

**MVP Note**: Webhook automation is **not** included in MVP. Manual pull/deploy only.

---

### 3.6 Redis

**Role**: Caching and lightweight message queue

**Use Cases:**
1. **Session Storage**: Cockpit session data (optional)
2. **Cache Layer**: Frequently accessed data (app list, metrics)
3. **Event Queue**: Asynchronous task processing (future)

**Example Redis Usage:**
```python
import redis

# Cache application list for 5 minutes
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_apps_cached():
    cache_key = "apps:list"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    apps = fetch_apps_from_docker()  # Expensive operation
    redis_client.setex(cache_key, 300, json.dumps(apps))
    return apps
```

---

### 3.7 Docker Engine & Networking

**Container Networking:**
```
┌─────────────────────────────────────────┐
│         websoft9 Bridge Network         │
├──────────┬──────────┬──────────┬────────┤
│  Nginx   │  App 1   │  App 2   │  Redis │
│  Proxy   │          │          │        │
└──────────┴──────────┴──────────┴────────┘
     │           │          │         │
     └───────────┴──────────┴─────────┘
             Published Ports
          (80, 443, 9000, etc.)
```

**Network Types:**
1. **websoft9 Network**: Default bridge for all Websoft9 services
2. **App-Specific Networks**: Created per docker-compose stack for isolation
3. **Host Network**: Used for services needing direct port access

**Volume Management:**
```bash
# Persistent data locations
/data/websoft9/
├── apphub/               # AppHub database and configs
├── nginx_pm/             # Nginx PM data
│   ├── data/
│   └── letsencrypt/      # SSL certificates
├── portainer/            # Portainer data
├── gitea/                # Git repositories
├── redis/                # Redis persistence
└── apps/                 # Application volumes
    ├── wordpress_1/
    ├── gitlab_1/
    └── ...
```

---

## 4. Data Architecture

### 4.1 Data Flow

**Application Installation:**
```
User selects app from catalog
     ↓
AppHub fetches template from GitHub
     ↓
Template parsed (docker-compose.yml + metadata.json)
     ↓
Environment variables generated (passwords, ports, etc.)
     ↓
Docker Compose deploys containers
     ↓
Nginx PM creates proxy host (if domain provided)
     ↓
AppHub stores metadata in SQLite
     ↓
User receives installation URL
```

**Log Aggregation:**
```
Container stdout/stderr
     ↓
Docker logging driver
     ↓
Cockpit journal reader (systemd-journald)
     ↓
Web-based log viewer
```

**Monitoring Data:**
```
Docker stats API (CPU, RAM, network)
     ↓
Cockpit metrics module
     ↓
In-memory storage (last 24 hours)
     ↓
Dashboard visualization
```

---

### 4.2 Database Design

**AppHub SQLite Schema:**
```sql
-- Core tables
CREATE TABLE apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    template_id TEXT NOT NULL,
    compose_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'stopped', 'error')),
    domain TEXT,
    port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_env_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,  -- Sensitive values encrypted
    is_secret BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
);

CREATE TABLE app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    level TEXT CHECK(level IN ('INFO', 'WARN', 'ERROR')),
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_apps_status ON apps(status);
CREATE INDEX idx_logs_timestamp ON app_logs(timestamp DESC);
CREATE INDEX idx_logs_app_id ON app_logs(app_id);
```

---

### 4.3 Caching Strategy

**Multi-Layer Cache:**

1. **L1 (In-Memory)**: Python dict for current request
2. **L2 (Redis)**: Shared cache across AppHub instances (future scaling)
3. **L3 (Database)**: Persistent storage

**Cache Invalidation:**
- **Time-Based**: Cache expires after 5 minutes
- **Event-Based**: Cache cleared on app install/uninstall
- **Manual**: Admin can force cache clear via API

---

## 5. API Architecture

### 5.1 API Design Principles

1. **RESTful Conventions**: Resources as nouns, HTTP verbs for actions
2. **Versioned**: `/api/v1/` prefix for stability
3. **Consistent Responses**: Standard success/error format
4. **Authentication**: JWT tokens for stateless auth
5. **Rate Limiting**: 100 requests/minute per user (future)

### 5.2 API Endpoints

**Application Management:**
```
GET    /api/v1/apps                 # List all apps
POST   /api/v1/apps                 # Install new app
GET    /api/v1/apps/{id}            # Get app details
PATCH  /api/v1/apps/{id}            # Update app config
DELETE /api/v1/apps/{id}            # Uninstall app
POST   /api/v1/apps/{id}/start      # Start app
POST   /api/v1/apps/{id}/stop       # Stop app
POST   /api/v1/apps/{id}/restart    # Restart app
GET    /api/v1/apps/{id}/logs       # Get app logs
```

**Template Catalog:**
```
GET    /api/v1/templates            # List available templates
GET    /api/v1/templates/{id}       # Get template details
POST   /api/v1/templates/refresh    # Refresh from GitHub
```

**System Management:**
```
GET    /api/v1/system/info          # System information
GET    /api/v1/system/metrics       # Resource usage
POST   /api/v1/system/backup        # Trigger backup
```

**Domain/Proxy:**
```
GET    /api/v1/domains              # List proxy hosts
POST   /api/v1/domains              # Create proxy host
PATCH  /api/v1/domains/{id}         # Update proxy config
DELETE /api/v1/domains/{id}         # Remove proxy host
```

### 5.3 Response Format

**Success Response:**
```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": {
    "app": {
      "id": 1,
      "name": "wordpress_1",
      "status": "running",
      "url": "https://mysite.example.com"
    }
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "code": 400,
  "message": "Invalid application configuration",
  "error": {
    "code": "INVALID_COMPOSE",
    "details": "Missing required service definition: database"
  }
}
```

**Pagination:**
```json
{
  "success": true,
  "code": 200,
  "data": {
    "items": [...],
    "pagination": {
      "total": 150,
      "page": 1,
      "pageSize": 20,
      "totalPages": 8
    }
  }
}
```

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

**Multi-Layer Security:**
```
User Login
     ↓
Cockpit PAM Authentication (Linux users)
     ↓
Session Cookie Issued
     ↓
AppHub API: Cookie → JWT Token
     ↓
Token Validation on Each Request
     ↓
Docker Socket Access (requires Docker group membership)
```

**Permission Levels:**
- **Admin**: Full system access (sudo + docker group)
- **User**: App management only (docker group)
- **Guest**: Read-only access (no docker group)

### 6.2 Network Security

**Firewall Rules (ufw example):**
```bash
# Allow SSH (admin access)
ufw allow 22/tcp

# Allow HTTP/HTTPS (application traffic)
ufw allow 80/tcp
ufw allow 443/tcp

# Allow Websoft9 UI (Cockpit)
ufw allow 9000/tcp

# Deny all other inbound
ufw default deny incoming

# Allow all outbound
ufw default allow outgoing
```

**Container Isolation:**
- Applications run in isolated Docker networks
- No direct access between app containers (unless explicitly linked)
- Host network mode disabled by default

### 6.3 Data Security

**Encryption:**
- **In-Transit**: TLS 1.3 for all HTTPS traffic
- **At-Rest**: 
  - Sensitive env vars encrypted before storing in database
  - Backups encrypted via Duplicati (AES-256)
- **Secrets Management**: Docker secrets for passwords (future enhancement)

**Password Policy:**
- Minimum 8 characters
- Requires uppercase, lowercase, number
- No common passwords (dictionary check)
- Automatic password generation for app installations

### 6.4 Vulnerability Management

**Automated Scanning:**
```yaml
# GitHub Actions workflow
name: Security Scan
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
```

**Update Strategy:**
- **Critical**: Patch within 7 days
- **High**: Patch within 30 days
- **Medium/Low**: Patch in next minor release

---

## 7. Performance & Scalability

### 7.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Response Time** | < 200ms (P95) | Prometheus + Grafana |
| **Application Install** | < 2 min (P95) | User-reported metrics |
| **Dashboard Load Time** | < 3 sec (P95) | Browser DevTools |
| **Concurrent Users** | 10+ sessions | Load testing (Locust) |
| **Resource Usage** | 1C2G minimum | Production deployments |

### 7.2 Optimization Strategies

**Database:**
- Indexed queries for common operations
- Connection pooling (SQLAlchemy)
- Query result caching (Redis)

**API:**
- Async/await for I/O operations (FastAPI)
- Background tasks for long-running operations
- Response compression (gzip)

**Frontend:**
- Static asset caching (browser cache headers)
- Minified JavaScript and CSS
- Lazy loading for heavy components

**Docker:**
- Image layer caching (multi-stage builds)
- Volume mounts for persistent data (avoid image bloat)
- Resource limits per container (prevent noisy neighbor)

### 7.3 Scalability Limitations (MVP)

**Current Constraints:**
- **Single Server**: No multi-node clustering
- **Vertical Scaling Only**: Add more CPU/RAM to host
- **Shared Docker Socket**: All services access same Docker daemon

**Future Evolution Path:**
```
Current (MVP):
┌────────────────┐
│  Websoft9     │
│  (All-in-One) │
└────────────────┘

Phase 2 (Multi-Server):
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Websoft9 │  │ Websoft9 │  │ Websoft9 │
│  Node 1  │  │  Node 2  │  │  Node 3  │
└──────────┘  └──────────┘  └──────────┘
      │             │             │
      └─────────────┴─────────────┘
               │
         ┌──────────────┐
         │  Shared DB   │
         │  (PostgreSQL)│
         └──────────────┘
```

---

## 8. Monitoring & Observability

### 8.1 Monitoring Stack (Optional)

**Components:**
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization dashboards
- **Node Exporter**: System-level metrics
- **cAdvisor**: Container-level metrics

**Metrics Collected:**
```yaml
# System metrics
- node_cpu_seconds_total
- node_memory_MemAvailable_bytes
- node_disk_io_time_seconds_total
- node_network_receive_bytes_total

# Container metrics
- container_cpu_usage_seconds_total
- container_memory_usage_bytes
- container_network_receive_bytes_total
- container_network_transmit_bytes_total

# Application metrics (custom)
- websoft9_apps_total
- websoft9_app_install_duration_seconds
- websoft9_api_requests_total
- websoft9_api_request_duration_seconds
```

**Grafana Dashboards:**
1. System Overview (CPU, RAM, Disk, Network)
2. Application Health (status, uptime, resource usage)
3. API Performance (response times, error rates)
4. Docker Statistics (container count, image sizes)

### 8.2 Logging Architecture

**Log Aggregation:**
```
Application Containers
     ↓
Docker JSON-file logging driver
     ↓
/var/lib/docker/containers/{id}/{id}-json.log
     ↓
Cockpit journal reader
     ↓
Web-based log viewer (real-time)
```

**Log Levels:**
- **DEBUG**: Detailed diagnostic info (disabled in production)
- **INFO**: General informational messages
- **WARN**: Warning messages (recoverable errors)
- **ERROR**: Error messages (requires attention)
- **CRITICAL**: System failures (immediate action needed)

**Structured Logging (AppHub):**
```python
import logging
import json

logger = logging.getLogger(__name__)

# Structured JSON logs
logger.info(json.dumps({
    "event": "app_install",
    "app_name": "wordpress",
    "user": "admin",
    "duration_ms": 120000,
    "status": "success"
}))
```

### 8.3 Alerting (Future)

**Alert Rules (Prometheus example):**
```yaml
groups:
  - name: websoft9_alerts
    rules:
      - alert: HighCPUUsage
        expr: node_cpu_usage > 80
        for: 5m
        annotations:
          summary: "CPU usage above 80% for 5 minutes"

      - alert: ApplicationDown
        expr: up{job="app"} == 0
        for: 2m
        annotations:
          summary: "Application {{ $labels.app }} is down"
```

**Notification Channels:**
- Email (SMTP)
- Slack webhook
- Discord webhook
- Custom webhooks

---

## 9. Deployment Architecture

### 9.1 Installation Process

**One-Line Installer:**
```bash
wget -O install.sh https://websoft9.github.io/websoft9/install/install.sh
bash install.sh
```

**Installation Steps:**
1. **Dependency Check**: Verify OS version, root privileges
2. **Docker Installation**: Install Docker Engine if not present
3. **Cockpit Installation**: Install and configure Cockpit
4. **Service Deployment**: Deploy Websoft9 services via docker-compose
5. **Firewall Configuration**: Open necessary ports (ufw/firewalld)
6. **Initial Setup**: Create admin user, generate SSL certificates
7. **Post-Install**: Display access URL and credentials

**Installation File Structure:**
```
/opt/websoft9/
├── install.sh               # Installer script
├── docker-compose.yml       # Core services definition
├── .env                     # Environment variables
├── apphub/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
├── cockpit/
│   └── websoft9-plugins/
└── systemd/
    └── websoft9.service     # Systemd service for auto-start
```

### 9.2 Docker Compose Configuration

**Core Services:**
```yaml
version: '3.8'

services:
  apphub:
    build: ./apphub
    container_name: websoft9-apphub
    restart: unless-stopped
    volumes:
      - apphub_data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - websoft9
    environment:
      - DATABASE_URL=sqlite:///data/websoft9.db
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8080:8080"

  proxy:
    image: jc21/nginx-proxy-manager:latest
    container_name: websoft9-proxy
    restart: unless-stopped
    volumes:
      - nginx_data:/data
      - nginx_letsencrypt:/etc/letsencrypt
    networks:
      - websoft9
    ports:
      - "80:80"
      - "443:443"
      - "81:81"  # Admin UI

  portainer:
    image: portainer/portainer-ce:latest
    container_name: websoft9-portainer
    restart: unless-stopped
    volumes:
      - portainer_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - websoft9

  gitea:
    image: gitea/gitea:latest
    container_name: websoft9-gitea
    restart: unless-stopped
    volumes:
      - gitea_data:/data
    networks:
      - websoft9
    environment:
      - USER_UID=1000
      - USER_GID=1000

  redis:
    image: redis:7-alpine
    container_name: websoft9-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - websoft9
    command: redis-server --appendonly yes

volumes:
  apphub_data:
  nginx_data:
  nginx_letsencrypt:
  portainer_data:
  gitea_data:
  redis_data:

networks:
  websoft9:
    name: websoft9
    driver: bridge
```

### 9.3 Cloud Marketplace Deployment

**Pre-Built Images:**
- **Azure Marketplace**: Ubuntu 22.04 + Websoft9 pre-installed
- **AWS Marketplace**: Ubuntu 22.04 AMI + Websoft9
- **Alibaba Cloud**: CentOS 8 + Websoft9
- **Huawei Cloud**: Ubuntu 20.04 + Websoft9

**Image Build Process:**
```bash
# Packer template (simplified)
packer build \
  -var 'cloud_provider=azure' \
  -var 'websoft9_version=2.0.0' \
  marketplace-image.pkr.hcl
```

**First-Boot Script:**
```bash
#!/bin/bash
# Executed on first VM boot

# Generate unique passwords
export ADMIN_PASSWORD=$(openssl rand -base64 16)
export DB_PASSWORD=$(openssl rand -base64 16)

# Update .env file
sed -i "s/ADMIN_PASSWORD=.*/ADMIN_PASSWORD=${ADMIN_PASSWORD}/" /opt/websoft9/.env

# Start services
systemctl start websoft9

# Display credentials
cat > /root/websoft9_credentials.txt <<EOF
Websoft9 Access:
URL: http://$(curl -s ifconfig.me):9000
Username: admin
Password: ${ADMIN_PASSWORD}
EOF
```

---

## 10. Disaster Recovery & Backup

### 10.1 Backup Strategy

**Backup Components:**
1. **Application Data**: Docker volumes (`/var/lib/docker/volumes/`)
2. **Configuration**: `/opt/websoft9/` and `.env` files
3. **Database**: AppHub SQLite database
4. **SSL Certificates**: Let's Encrypt certificates

**Backup Schedule:**
- **Critical Data**: Daily at 2 AM (application volumes)
- **Configuration**: Weekly on Sundays
- **Full System**: Monthly snapshot (cloud providers)

**Duplicati Configuration:**
```json
{
  "backup-name": "websoft9-daily",
  "source-paths": [
    "/var/lib/docker/volumes/",
    "/opt/websoft9/"
  ],
  "destination": "s3://my-bucket/websoft9-backups/",
  "encryption": "AES-256",
  "schedule": "0 2 * * *",
  "retention": "30D"
}
```

### 10.2 Disaster Recovery

**Recovery Time Objective (RTO):** < 4 hours  
**Recovery Point Objective (RPO):** < 24 hours

**Disaster Recovery Steps:**
1. **Provision New Server**: Deploy fresh OS instance
2. **Install Websoft9**: Run installer script
3. **Restore Configuration**: Copy `/opt/websoft9/` from backup
4. **Restore Data**: Extract Docker volumes from backup
5. **Restart Services**: `systemctl restart websoft9`
6. **Verify Functionality**: Check application accessibility

**Automated DR Script:**
```bash
#!/bin/bash
# disaster_recovery.sh

# Download latest backup
aws s3 sync s3://my-bucket/websoft9-backups/latest/ /restore/

# Stop services
systemctl stop websoft9

# Restore data
rsync -av /restore/docker/volumes/ /var/lib/docker/volumes/
rsync -av /restore/websoft9/ /opt/websoft9/

# Start services
systemctl start websoft9

# Health check
curl -f http://localhost:9000 || echo "Recovery failed"
```

---

## 11. Evolution & Future Architecture

### 11.1 Current Limitations

1. **Single Point of Failure**: All services on one server
2. **No Load Balancing**: Cannot distribute traffic across multiple instances
3. **Limited Horizontal Scaling**: Vertical scaling only (add more CPU/RAM)
4. **Shared Docker Socket**: Security concern for multi-tenant scenarios

### 11.2 Proposed Evolution

**Phase 1 (MVP - Current):**
- Single-server deployment
- Integrated components
- Simplified management

**Phase 2 (Multi-Server - Q3 2026):**
- Separate AppHub and application servers
- Shared database (PostgreSQL cluster)
- Load balancer for high availability

**Phase 3 (Microservices - 2027):**
- AppHub decomposed into services (auth, catalog, orchestration)
- Message queue for async operations (RabbitMQ/NATS)
- Service mesh for communication (Istio/Linkerd)

**Architecture Evolution Diagram:**
```
MVP (Now):
┌──────────────────┐
│   Websoft9      │
│   All-in-One    │
└──────────────────┘

Multi-Server (Q3 2026):
        ┌──────────────┐
        │ Load Balancer│
        └──────────────┘
         │           │
    ┌────┴───┐  ┌────┴───┐
    │ Node 1 │  │ Node 2 │
    └────────┘  └────────┘
         │           │
         └──────┬────┘
                │
        ┌───────┴──────┐
        │  PostgreSQL  │
        │   Cluster    │
        └──────────────┘

Microservices (2027):
┌─────────┐  ┌─────────┐  ┌─────────┐
│  Auth   │  │ Catalog │  │Orchestr.│
│ Service │  │ Service │  │ Service │
└─────────┘  └─────────┘  └─────────┘
     │            │            │
     └────────────┴────────────┘
                  │
          ┌───────┴───────┐
          │  Message Bus  │
          │  (RabbitMQ)   │
          └───────────────┘
```

---

## 12. Key Architecture Decisions (ADRs)

### ADR-001: Use Cockpit as Web Framework

**Decision**: Integrate with RedHat Cockpit instead of building custom UI

**Rationale:**
- Production-tested by RedHat for 10+ years
- Built-in system management features (terminal, logs, network)
- Active upstream maintenance
- Plugin architecture for extensibility

**Tradeoffs:**
- Dependency on upstream Cockpit development
- Limited UI customization options
- Must adapt to Cockpit's authentication model

**Status**: Accepted (2 years in production)

---

### ADR-002: Integrate vs. Build for Proxy/Git/Containers

**Decision**: Integrate Nginx PM, Gitea, Portainer instead of building custom solutions

**Rationale:**
- Faster time-to-market (no R&D for these complex features)
- Proven reliability (millions of users)
- Active community support and updates
- Focus development on unique value (application catalog)

**Tradeoffs:**
- Multiple UIs to learn (Nginx PM, Portainer, Gitea)
- Potential version incompatibilities
- Limited control over upstream feature roadmap

**Status**: Accepted (core philosophy)

---

### ADR-003: SQLite vs. PostgreSQL for AppHub

**Decision**: Use SQLite for MVP, design for PostgreSQL migration

**Rationale:**
- Zero-configuration for users (no DB setup required)
- Sufficient for single-server workloads (< 1M records)
- Easy backup (single file)
- Faster development (no connection pooling complexity)

**Tradeoffs:**
- Limited to single-writer (no concurrent writes)
- No native replication for HA
- Must migrate for multi-server deployments

**Future Migration Path**: Use SQLAlchemy ORM for database abstraction

**Status**: Accepted for MVP

---

### ADR-004: Docker Compose vs. Kubernetes

**Decision**: Use Docker Compose for application deployment, avoid Kubernetes

**Rationale:**
- Target audience: SMBs and developers (not enterprise DevOps)
- Single-server focus (K8S adds unnecessary complexity)
- Faster installation and lower resource overhead
- Familiar to Docker users (gentle learning curve)

**Tradeoffs:**
- No built-in service discovery or auto-scaling
- Limited orchestration features (no rolling updates)
- Manual high availability setup

**Future Consideration**: Offer optional K8S support for enterprise users (Phase 3)

**Status**: Accepted (core value proposition)

---

### ADR-005: Python FastAPI vs. Go for AppHub

**Decision**: Use Python + FastAPI for AppHub API

**Rationale:**
- Rapid development (Pydantic models, auto-generated docs)
- Rich ecosystem (Docker SDK, templating libraries)
- Async support for non-blocking I/O
- Easier to attract contributors (Python popularity)

**Tradeoffs:**
- Higher memory usage vs. Go (acceptable on 2GB+ servers)
- Slower cold start vs. compiled languages
- Requires Python runtime in container

**Alternative Considered**: Go (better performance, but slower development)

**Status**: Accepted

---

## Appendix

### A. System Requirements

**Minimum:**
- CPU: 1 core
- RAM: 2 GB
- Disk: 20 GB
- OS: Ubuntu 20.04+, Debian 11+, CentOS 8+, Rocky Linux 8+

**Recommended:**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 50 GB+ (depending on applications)
- OS: Ubuntu 22.04 LTS

### B. Port Reference

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 22 | SSH | TCP | Server administration |
| 80 | Nginx PM | TCP | HTTP traffic |
| 443 | Nginx PM | TCP | HTTPS traffic |
| 81 | Nginx PM Admin | TCP | Proxy manager UI |
| 9000 | Cockpit | TCP | Websoft9 dashboard |
| 8080 | AppHub API | TCP | Internal API (not exposed) |
| 6379 | Redis | TCP | Internal cache (not exposed) |
| 3000 | Gitea | TCP | Git service (proxied via Nginx) |

### C. Related Documentation

- [Product Brief](product/product-brief.md) - Business strategy
- [PRD](prd.md) - Product requirements
- [Developer Guide](developer.md) - Contribution guidelines
- [User Guide](user.md) - End-user documentation
- [API Documentation](apidocs/index.html) - Swagger/OpenAPI specs

### D. External References

- [Cockpit Project](https://cockpit-project.org/)
- [Docker Documentation](https://docs.docker.com/)
- [Nginx Proxy Manager](https://nginxproxymanager.com/)
- [Portainer Docs](https://docs.portainer.io/)
- [Gitea Documentation](https://docs.gitea.io/)
- [FastAPI Framework](https://fastapi.tiangolo.com/)

---

**Document Maintainer:** Websoft9 Architecture Team  
**Review Status:** Active  
**Last Updated:** 2026-01-04  
**Next Review:** 2026-04-01  
**Change Log:**  
- 2026-01-04: Initial architecture document for BMAD workflow
