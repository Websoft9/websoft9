# Product Requirements Document - Websoft9

**Author:** Websoft9 Team  
**Date:** 2026-01-04  
**Status:** Active  
**Version:** 2.0  
**Related Documents:** [Product Brief](product/product-brief.md)

---

## 1. Document Purpose

### 1.1 PRD Objectives

This PRD defines the **Functional Requirements (FR)** and **Non-Functional Requirements (NFR)** for Websoft9, a containerized application management platform.

**Relationship with Product Brief:**
- **Product Brief**: Defines business vision, market positioning, and strategic direction
- **PRD (this document)**: Defines verifiable functional requirements and acceptance criteria
- **Technical Architecture**: Defines implementation approach and technology decisions

### 1.2 Target Audience

- **Architects**: System design and integration decisions
- **Development Team**: Feature implementation
- **QA Team**: Test planning and acceptance validation
- **Product Managers**: Scope and priority management
- **DevOps**: Deployment and operational requirements

---

## 2. Core Functional Requirements

### 2.1 Application Management

#### FR-APP-001: Application Catalog & One-Click Deployment

**Requirement**: Provide a curated catalog of 200+ open-source applications with one-click installation

**Core Capabilities:**
- Browse application catalog by category (CMS, E-commerce, DevOps, etc.)
- View application details (description, requirements, documentation links)
- One-click installation from docker-compose templates
- Pre-configured environment variables with sensible defaults
- Automatic dependency resolution (networks, volumes, linked services)

**Acceptance Criteria:**
- ✅ User can browse and search the application catalog
- ✅ Application installation completes in < 2 minutes (average)
- ✅ Pre-configured apps are immediately accessible after install
- ✅ Installation success rate > 95% for official templates
- ✅ Failed installations provide clear error messages

**MVP Exclusions:**
- ❌ Custom application template builder (manual docker-compose only)
- ❌ Application version rollback (can reinstall only)
- ❌ Multi-stage deployment pipelines

---

#### FR-APP-002: Application Lifecycle Management

**Requirement**: Manage installed applications through their entire lifecycle

**Core Capabilities:**
- List all installed applications with status (running, stopped, error)
- Start, stop, restart individual applications
- View application logs in real-time
- Access application environment variables
- Update application configurations
- Uninstall applications with data cleanup options

**Acceptance Criteria:**
- ✅ Application status updates within 3 seconds of state change
- ✅ Logs displayed with timestamp and color coding (errors in red)
- ✅ Environment variable changes applied on container restart
- ✅ Uninstall removes containers, networks, and optionally volumes
- ✅ No orphaned Docker resources after uninstall

---

#### FR-APP-003: Docker Compose GUI

**Requirement**: Provide visual interface for docker-compose management via Portainer

**Core Capabilities:**
- View docker-compose.yml files in syntax-highlighted editor
- Edit compose files directly in web interface
- Validate compose syntax before applying
- Deploy custom docker-compose projects
- Manage container networks and volumes

**Acceptance Criteria:**
- ✅ Syntax validation catches common errors before deployment
- ✅ Changes to compose files trigger rebuild prompt
- ✅ Custom projects deploy successfully with valid compose files
- ✅ Network and volume visualization shows relationships

---

### 2.2 Reverse Proxy & SSL Management

#### FR-PROXY-001: Nginx Proxy Manager Integration

**Requirement**: Built-in reverse proxy with automatic SSL certificate management

**Core Capabilities:**
- Create proxy hosts for applications (domain → container:port)
- Automatic SSL certificates via Let's Encrypt
- Force HTTPS redirection
- Custom SSL certificate upload
- Access control lists (IP whitelist/blacklist)
- HTTP authentication (basic auth)

**Acceptance Criteria:**
- ✅ Proxy host creation takes < 30 seconds
- ✅ Let's Encrypt certificates auto-renew 30 days before expiry
- ✅ SSL rating of A or better on Qualys SSL Labs
- ✅ Proxy configuration changes apply immediately (< 5s)
- ✅ Failed certificate issuance provides actionable error message

**MVP Exclusions:**
- ❌ Web Application Firewall (WAF) rules
- ❌ Advanced load balancing (round-robin only)
- ❌ Custom Nginx configuration snippets (predefined only)

---

### 2.3 System Management

#### FR-SYS-001: Web-Based System Administration

**Requirement**: Cockpit-based system management interface

**Core Capabilities:**
- View system metrics (CPU, RAM, disk, network)
- Manage system services (start, stop, enable, disable)
- Web-based terminal access
- File browser with upload/download
- Network configuration (IP, DNS, firewall)
- User account management
- System log viewer

**Acceptance Criteria:**
- ✅ System metrics update every 5 seconds
- ✅ Terminal session persists for 30 minutes of inactivity
- ✅ File upload supports files up to 2GB
- ✅ Firewall rules apply immediately without reboot
- ✅ System logs searchable by date range and keyword

---

#### FR-SYS-002: Multi-User Access Control

**Requirement**: Support multiple users with role-based permissions

**Core Capabilities:**
- Create Linux user accounts via web interface
- Add users to Docker group for container access
- Sudo privilege management
- SSH access control
- Session management (view active sessions, force logout)

**Acceptance Criteria:**
- ✅ New users can log in within 30 seconds of creation
- ✅ Docker group membership grants container management rights
- ✅ Sudo privileges require password confirmation
- ✅ SSH access can be disabled per user
- ✅ Admin can view and terminate user sessions

---

### 2.4 Version Control Integration

#### FR-GIT-001: Gitea Repository Service

**Requirement**: Self-hosted Git repository for application code and configurations

**Core Capabilities:**
- Create and manage Git repositories
- Web-based code viewer and editor
- Clone/push/pull via HTTPS and SSH
- Branch management
- Basic issue tracking
- User and organization management

**Acceptance Criteria:**
- ✅ Repository creation takes < 10 seconds
- ✅ Code editor supports syntax highlighting for common languages
- ✅ Git operations (clone, push, pull) complete successfully
- ✅ SSH key authentication works without password prompts
- ✅ Web hooks trigger on push events

**MVP Exclusions:**
- ❌ Advanced CI/CD pipelines (use external tools)
- ❌ Code review workflows (PR approvals)
- ❌ Integrated wikis and project boards

---

### 2.5 Storage & Backup

#### FR-STORAGE-001: File Management

**Requirement**: Web-based file browser for server files

**Core Capabilities:**
- Navigate directory structure
- Upload and download files
- Create, rename, delete files and folders
- File permissions management (chmod)
- File content editing (text files)
- Archive creation (zip, tar.gz)

**Acceptance Criteria:**
- ✅ File operations complete within 2 seconds for small files (< 10MB)
- ✅ Upload progress indicator for large files
- ✅ File editor supports common formats (txt, yml, json, md)
- ✅ Permission changes visible immediately in file list
- ✅ Archive creation supports multiple file selection

---

#### FR-STORAGE-002: Backup Automation

**Requirement**: Scheduled backups via Duplicati integration

**Core Capabilities:**
- Configure backup destinations (local, S3, FTP, etc.)
- Schedule backup jobs (daily, weekly, custom cron)
- Select files/folders for backup
- Encrypted backups
- Backup restoration interface
- Email notifications on backup success/failure

**Acceptance Criteria:**
- ✅ Backup jobs run on schedule with < 1 minute variance
- ✅ Backups are encrypted with AES-256
- ✅ Restoration completes successfully for backed-up data
- ✅ Email notifications sent within 5 minutes of job completion
- ✅ Backup history shows last 30 days of jobs

**MVP Exclusions:**
- ❌ Incremental backup deduplication (full backups only)
- ❌ Backup retention policies (manual deletion)
- ❌ Disaster recovery automation

---

### 2.6 Monitoring & Logging

#### FR-MONITOR-001: System Health Monitoring

**Requirement**: Real-time system and application monitoring

**Core Capabilities:**
- System resource usage (CPU, RAM, disk, network)
- Docker container status and resource usage
- Application availability checks (HTTP endpoint monitoring)
- Historical data (last 24 hours minimum)
- Threshold-based alerts (email/webhook)

**Acceptance Criteria:**
- ✅ Metrics update every 10 seconds
- ✅ Container resource usage accurate within 5% margin
- ✅ HTTP availability checks run every 60 seconds
- ✅ Historical data queryable for 7 days
- ✅ Alerts sent within 2 minutes of threshold breach

---

#### FR-MONITOR-002: Centralized Logging

**Requirement**: Aggregate logs from all applications and system services

**Core Capabilities:**
- Collect logs from Docker containers (stdout/stderr)
- Collect system service logs (systemd journals)
- Web-based log viewer with filtering
- Search logs by keyword, time range, container
- Export logs (JSON, plain text)

**Acceptance Criteria:**
- ✅ Logs appear in viewer within 10 seconds of generation
- ✅ Search returns results in < 3 seconds for 10k log lines
- ✅ Filters work for container name, log level, time range
- ✅ Export includes all filtered logs
- ✅ Logs retained for 7 days (configurable)

**MVP Exclusions:**
- ❌ Log aggregation from external sources (syslog)
- ❌ Advanced log analytics (ML-based anomaly detection)
- ❌ Log correlation (distributed tracing)

---

### 2.7 API & CLI

#### FR-API-001: RESTful API (AppHub)

**Requirement**: Programmatic access to application management

**Core Capabilities:**
- List available applications
- Install/uninstall applications
- Get application status
- Start/stop/restart applications
- Retrieve application logs
- Manage environment variables
- API authentication (JWT tokens)

**Acceptance Criteria:**
- ✅ API response time < 200ms (P95)
- ✅ API returns standardized JSON responses
- ✅ Authentication required for all endpoints
- ✅ Comprehensive error messages (HTTP status + error codes)
- ✅ OpenAPI/Swagger documentation available

---

#### FR-API-002: Command Line Interface

**Requirement**: CLI for advanced users and automation

**Core Capabilities:**
- Install applications from CLI
- Manage application lifecycle (start, stop, restart)
- View logs
- Modify configuration
- Import/export application settings

**Acceptance Criteria:**
- ✅ CLI commands match API functionality
- ✅ Command help text available (`websoft9 --help`)
- ✅ Exit codes indicate success (0) or failure (non-zero)
- ✅ Supports JSON output for scripting (`--json` flag)
- ✅ Tab completion for commands and options

---

### 2.8 Internationalization

#### FR-I18N-001: Multi-Language Support

**Requirement**: Interface available in multiple languages

**Core Capabilities:**
- English (default)
- Simplified Chinese (中文)
- Language selection from settings
- Persistent language preference
- Localized date/time formats

**Acceptance Criteria:**
- ✅ All UI text translated in supported languages
- ✅ Language change applies immediately without reload
- ✅ User preference saved and restored on login
- ✅ Date/time formats match locale conventions
- ✅ No broken translations (missing keys show English)

**MVP Exclusions:**
- ❌ Right-to-left language support (Arabic, Hebrew)
- ❌ Automatic language detection from browser
- ❌ Community translation portal

---

## 3. Non-Functional Requirements (NFR)

### NFR-001: Performance

- **Single Server Optimization**: Core functionality runs on 1C2G instances
- **Application Install Time**: < 2 minutes average (P95)
- **API Response Time**: < 200ms for standard operations (P95)
- **Web UI Load Time**: < 3 seconds for dashboard (P95)
- **Concurrent Users**: Support 10+ simultaneous web sessions

---

### NFR-002: Reliability

- **System Availability**: > 99% uptime (excluding planned maintenance)
- **Installation Success Rate**: > 95% for official app templates
- **Automatic Restart**: Critical services auto-restart on failure
- **Data Persistence**: Application data survives host reboots
- **Graceful Degradation**: UI functional even if monitoring services fail

---

### NFR-003: Security

- **Transport Security**: HTTPS/TLS 1.3 for all web interfaces
- **Authentication**: Strong password requirements (8+ chars, mixed case, numbers)
- **Session Management**: Sessions expire after 30 minutes of inactivity
- **Container Isolation**: Applications run in isolated Docker networks
- **Firewall**: ufw/firewalld pre-configured for necessary ports only
- **Updates**: Automated security patch notifications
- **Secrets Management**: Sensitive config stored as Docker secrets (not plain text)

---

### NFR-004: Usability

- **First-Time Setup**: Complete initial setup in < 10 minutes
- **Documentation**: In-app help links to comprehensive docs
- **Error Messages**: Actionable errors with suggested fixes
- **Mobile Responsive**: Dashboard accessible on tablets (1024px+ width)
- **Keyboard Navigation**: Support tab navigation for accessibility

---

### NFR-005: Maintainability

- **Logs**: Structured JSON logs for all services
- **Monitoring**: Health check endpoints for all critical services
- **Updates**: One-command upgrade (`bash install.sh --upgrade`)
- **Rollback**: Ability to restore from backup in < 30 minutes
- **Documentation**: Inline code comments for complex logic

---

### NFR-006: Scalability

- **Application Limit**: Support 50+ installed applications per instance
- **User Limit**: 20+ user accounts
- **Storage**: Handle 1TB+ of application data
- **Network**: Support 100+ proxy hosts
- **Horizontal Scaling**: NOT required for MVP (single-server focus)

---

### NFR-007: Compatibility

- **Operating Systems**: 
  - Ubuntu 20.04+ LTS
  - Debian 11+
  - CentOS 8+ / Rocky Linux 8+
- **Docker**: 20.10+ (tested against 24.x)
- **Browsers**:
  - Chrome 90+
  - Firefox 88+
  - Edge 90+
  - Safari 14+

---

### NFR-008: Deployability

- **Installation Method**: Single-script installer
- **Installation Time**: < 15 minutes on clean system
- **Configuration**: Environment variable-based configuration
- **Containerization**: All services run in Docker containers
- **Port Requirements**: HTTP (80), HTTPS (443), Websoft9 UI (9000)
- **Cloud Marketplace**: Pre-built images for Azure, AWS, Alibaba Cloud

---

## 4. MVP Scope

### 4.1 MVP Features (Current v2.0 - Shipped)

All functional requirements listed in Section 2 are **currently implemented and in production** (v2.0).

**Core Platform (Production):**
- ✅ Cockpit web interface (RedHat Cockpit 276+)
- ✅ Docker container management (Portainer 2.x)
- ✅ Nginx Proxy Manager (automated SSL via Let's Encrypt)
- ✅ Gitea integration (self-hosted Git)
- ✅ 200+ application templates (docker-library)
- ✅ AppHub API (Python 3.11 + FastAPI)
- ✅ File management (Cockpit built-in)
- ✅ Basic monitoring (Cockpit metrics)
- ✅ Multi-user support (Linux PAM authentication)
- ✅ CLI tool (`apphub` command)
- ✅ API key authentication

**Current Development (v2.1 - In Progress):**
- 🔨 Enhanced API documentation (Swagger/OpenAPI UI)
- 🔨 Backup automation improvements (Duplicati)
- 🔨 Multi-language support expansion (Japanese, Spanish)
- 🔨 BMAD workflow integration (this documentation)

**Proven Production Metrics:**
- Installation success rate: **>95%** (official templates)
- Average install time: **<2 minutes**
- Cloud marketplace deployments: **6+ platforms**
- Uptime: **>99%** (community-reported)

---

### 4.2 MVP Exclusions

**Not Included in Current Scope:**
- ❌ Multi-server clustering or high availability
- ❌ Kubernetes integration
- ❌ Advanced CI/CD pipelines (use external tools like GitHub Actions)
- ❌ Database-as-a-Service (DBaaS) management
- ❌ Auto-scaling policies
- ❌ Advanced monitoring (distributed tracing, APM)
- ❌ SaaS multi-tenancy
- ❌ White-label capabilities
- ❌ Mobile native apps (Android/iOS)
- ❌ Plugin marketplace (manual plugin installation only)

---

### 4.3 Priority Levels (v2.x Roadmap)

Based on [Product Brief - Roadmap](product/product-brief.md#roadmap-highlights) and current production feedback.

**P0 (Critical - Must Have for v2.x):**
- ✅ Application catalog and one-click installation
- ✅ Docker container management (Portainer)
- ✅ Reverse proxy + SSL automation (Nginx PM)
- ✅ System administration (Cockpit)
- ✅ Multi-user support

**P1 (High - Current Development v2.1):**
- 🔨 Enhanced API documentation (Swagger/OpenAPI UI)
- 🔨 Backup automation improvements (Duplicati)
- 🔨 Multi-language expansion (Japanese, Spanish)
- 🔨 BMAD workflow integration (documentation standardization)
- 🔨 CLI enhancements (additional commands)

**P2 (Medium - Q2 2026):**
- 🔮 Advanced monitoring (Prometheus/Grafana integration)
- 🔮 Plugin SDK and marketplace
- 🔮 Template contribution portal
- 🔮 Enhanced RBAC (project-level permissions)
- 🔮 Webhook automation

**P3 (Low - Q3-Q4 2026):**
- 🔮 White-label branding options
- 🔮 Enterprise compliance features (audit logs, SOC2)
- 🔮 Multi-server clustering (breaking single-server limitation)
- 🔮 Advanced CI/CD pipeline integration

**Out of Scope (Not Planned):**
- ❌ Kubernetes integration (contradicts core value proposition)
- ❌ Multi-tenant SaaS mode (focused on self-hosted)
- ❌ Mobile native apps (web-responsive sufficient)
- ❌ Database-as-a-Service (DBaaS) management (use applications instead)

---

## 5. User Stories & Acceptance Tests

### Epic: Application Deployment

**US-001: As a developer, I want to install WordPress in one click so I can start building my site immediately.**

**Acceptance Tests:**
1. User navigates to application catalog
2. User searches for "WordPress"
3. User clicks "Install"
4. User optionally customizes domain name
5. Installation completes within 2 minutes
6. User can access WordPress setup page via generated URL
7. WordPress installation has secure default settings (strong DB password)

---

**US-002: As a small business owner, I want to deploy GitLab for my team without learning Docker so we can start collaborating.**

**Acceptance Tests:**
1. User selects GitLab from catalog
2. User clicks "Install" without modifying defaults
3. GitLab deploys with pre-configured email notifications
4. User receives login credentials via dashboard notification
5. GitLab web interface accessible via HTTPS with valid certificate
6. First login forces password change
7. User can create repositories and invite team members

---

### Epic: System Management

**US-003: As a sysadmin, I want to view real-time system metrics so I can identify performance issues.**

**Acceptance Tests:**
1. User accesses dashboard
2. Dashboard displays CPU, RAM, disk, and network usage
3. Metrics update every 5 seconds
4. Historical graphs show last 24 hours
5. Color-coded warnings when resources exceed 80%
6. Click on metric opens detailed view in Cockpit

---

**US-004: As a freelancer, I want to create backup jobs for client sites so I don't lose data.**

**Acceptance Tests:**
1. User navigates to Backup section
2. User creates new backup job
3. User selects directories to backup (e.g., `/var/lib/docker/volumes`)
4. User configures S3 destination with credentials
5. User sets schedule (daily at 2 AM)
6. Backup job runs successfully on schedule
7. User receives email confirmation of successful backup
8. User can restore files from backup via web interface

---

### Epic: Security & SSL

**US-005: As a website owner, I want automatic SSL certificates so my site is secure without manual config.**

**Acceptance Tests:**
1. User creates proxy host in Nginx Proxy Manager
2. User enters domain name (e.g., `myapp.example.com`)
3. User selects "Request SSL certificate via Let's Encrypt"
4. User enters email for certificate notifications
5. Certificate issued within 60 seconds
6. HTTPS redirection enabled automatically
7. Certificate auto-renews before expiry
8. User receives email 7 days before manual action needed (if any)

---

## 6. API Reference (AppHub Implementation)

### 6.1 Current API Structure

**Based on actual AppHub codebase (src/api/v1/routers/):**

**Application Management Endpoints:**
```python
# GET /api/v1/apps/
# List all installed applications with status

# POST /api/v1/apps/install
# Install application from template
# Request: { "template_id": "wordpress", "domain": "mysite.com", "env": {...} }

# POST /api/v1/apps/{app_id}/start
# Start a stopped application

# POST /api/v1/apps/{app_id}/stop
# Stop a running application

# POST /api/v1/apps/{app_id}/restart
# Restart an application

# POST /api/v1/apps/{app_id}/redeploy
# Rebuild and redeploy application (applies config changes)

# DELETE /api/v1/apps/{app_id}/uninstall
# Uninstall application with cleanup option
# Query params: ?remove_volumes=true (optional)
```

**Proxy Management Endpoints:**
```python
# GET /api/v1/proxy/{app_id}
# Get proxy configuration for application

# POST /api/v1/proxy/{app_id}
# Create proxy host with optional SSL
# Request: { "domain": "app.example.com", "ssl": true, "force_ssl": true }

# PUT /api/v1/proxy/{app_id}
# Update existing proxy configuration

# DELETE /api/v1/proxy/{app_id}
# Remove proxy host for application
```

**Settings Endpoints:**
```python
# GET /api/v1/settings
# Get current system settings

# PUT /api/v1/settings
# Update system configuration
# Request: { "key": "value", ... }
```

### 6.2 CLI Commands

**AppHub CLI (apphub command):**
```bash
# Generate API key for authentication
apphub genkey

# Get configuration value
apphub getconfig <key>

# Set configuration value
apphub setconfig <key> <value>
```

---

## 7. Integration Requirements

### 7.1 External Services

| Service | Integration Type | Purpose |
|---------|------------------|---------|
| **Let's Encrypt** | ACME Protocol | SSL certificate issuance |
| **Docker Hub** | Registry API | Pull application images |
| **GitHub** | Raw Content API | Fetch docker-library templates |
| **Cloud Storage** | S3/Blob API | Backup destinations |

### 6.2 Internal Components

| Component | Communication | Protocol |
|-----------|--------------|----------|
| Cockpit ↔ AppHub | HTTP | REST API |
| AppHub ↔ Docker | Socket | Docker API |
| Nginx PM ↔ Containers | Network | HTTP Proxy |
| Gitea ↔ Users | HTTPS | Web Interface |
| Portainer ↔ Docker | Socket | Docker API |

---

## 7. Constraints & Dependencies

### 7.1 Technical Constraints

- **Single Server**: MVP does not support multi-node deployments
- **Docker Dependency**: All applications must be containerized
- **Root Access**: Installer requires root/sudo privileges
- **Internet Connection**: Initial install requires internet for pulling images
- **Port Availability**: Ports 80, 443, 9000 must be available
- **Linux Only**: No Windows or macOS host support

### 7.2 External Dependencies

- **Docker Engine**: Host must support Docker 20.10+
- **Cockpit Package**: RedHat Cockpit must be installable
- **Systemd**: Required for service management
- **Firewall**: ufw or firewalld must be available
- **DNS**: Proper DNS records for SSL certificate issuance

### 7.3 Assumptions

- Users have basic Linux command-line knowledge
- Users control DNS for their domains
- Server has stable internet connection
- Users understand containerization basics (helpful but not required)

---

## 8. Compliance & Regulations

### 8.1 Open Source Licensing

- **Websoft9 Core**: LGPL-3.0
- **Restriction**: No unauthorized cloud marketplace redistribution
- **Third-Party Components**: Respect upstream licenses (MIT, Apache, etc.)

### 8.2 Data Privacy

- **User Data**: Stored locally on user's server (not collected by Websoft9)
- **Telemetry**: NO anonymous usage analytics in MVP
- **Logs**: Application logs remain on user's server
- **Compliance**: Users responsible for GDPR/HIPAA compliance of deployed apps

### 8.3 Security Standards

- **CVE Monitoring**: Automated scanning of dependencies
- **Responsible Disclosure**: Security issues reported via GitHub Security Advisories
- **Patch SLA**: Critical vulnerabilities patched within 7 days
- **Security Audits**: Annual third-party security review

---

## 9. Success Criteria

### 9.1 Product Launch Criteria

**Before Public Release:**
- ✅ All P0 features complete and tested
- ✅ Installation success rate > 95% across supported OS
- ✅ Security audit passed (no critical vulnerabilities)
- ✅ Documentation complete (user guide + developer guide)
- ✅ Demo server available (http://demo.goweb.cc:9000/)

### 9.2 User Acceptance Criteria

**Within 30 Days of Launch:**
- 1,000+ installations from GitHub (organic)
- 100+ installations via cloud marketplaces
- < 5% critical bug reports (blockers)
- Average user rating > 4.0/5.0 on cloud marketplaces

### 9.3 Technical Success Metrics

- **Uptime**: 99%+ availability (community-reported)
- **Performance**: API response time < 200ms (P95)
- **Installation Time**: < 15 minutes (median)
- **Support Ticket Volume**: < 10 tickets per 100 installations

---

## 10. Appendix

### 10.1 Glossary

| Term | Definition |
|------|------------|
| **AppHub** | Custom FastAPI service for application management |
| **Cockpit** | RedHat's web-based Linux admin interface |
| **Docker Compose** | Multi-container application definition format |
| **Gitea** | Self-hosted Git service |
| **Let's Encrypt** | Free SSL certificate authority |
| **Nginx PM** | Nginx Proxy Manager - GUI for reverse proxy |
| **Portainer** | Docker container management UI |
| **P0/P1/P2** | Priority levels (0=Critical, 1=High, 2=Medium) |

### 10.2 References

- [Product Brief](product/product-brief.md) - Business strategy and vision
- [Technical Architecture](architecture/tech-architecture.md) - System design
- [Developer Guide](developer.md) - Contributor documentation
- [User Guide](user.md) - End-user documentation
- [Docker Library](https://github.com/Websoft9/docker-library) - Application templates

### 10.3 Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-01-04 | 2.0 | Initial PRD for BMAD workflow integration | Websoft9 Team |

---

**Document Owner:** Product Team  
**Review Cycle:** Quarterly  
**Last Updated:** 2026-01-04  
**Next Review:** 2026-04-01
