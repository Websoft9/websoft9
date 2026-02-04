---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-03-success', 'step-04-journeys']
inputDocuments:
  - specs/planning-artifacts/product-brief.md
workflowType: 'prd'
briefCount: 1
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
classification:
  projectType: 'Infrastructure Tool'
  domain: 'DevOps Tool'
  complexity: 'Medium'
  projectContext: 'Greenfield'
  scope: 'Complete lightweight platform functionality'
---

# Product Requirements Document - websoft9

**Author:** Websoft9
**Date:** 2026-02-04

## Success Criteria

### User Success

**Core "Aha!" Moments:**
- User deploys their first application and accesses it via domain within **< 2 minutes** of login
- User modifies config via GitOps, manually triggers deployment, and sees changes live in **< 2 minutes**
- User manages complete application lifecycle without leaving the web interface

**Measurable User Success Metrics:**
- ✅ Application deployment success rate > **95%** (using app store templates)
- ✅ App start/stop/restart operations respond in < **5 seconds**
- ✅ Domain binding + automatic SSL certificate issuance < **30 seconds**
- ✅ Application rebuild/redeploy completion time < **3 minutes**
- ✅ Delete operations fully clean up resources (no orphaned containers/networks/volumes)
- ✅ Monitoring data refresh latency < **5 seconds**

**User Emotional Success:**
- Users feel "This is more powerful than Docker Compose, but simpler than Kubernetes"
- Team members can independently deploy and manage applications without DevOps expertise
- Users have complete infrastructure control (GitOps + open source transparency)

### Business Success

**6-Month Goals:**
- Active installations > **1,000** instances
- Steady growth in cloud marketplace deployments (Azure, AWS, Alibaba Cloud, etc.)
- Top 50 app store applications actively used

**12-Month Goals:**
- GitHub stars > **5,000**
- Community contributors > **50** people
- Enterprise use cases > **10** (small businesses, educational institutions, non-profits)

**Product-Market Fit Signals:**
- Users spontaneously recommend to peers (NPS > 50)
- Users transition from "testing" to "production deployment"
- Community begins contributing custom application templates

### Technical Success

**Performance Metrics:**
- ✅ Runs stably on **1C2G** configuration for core services
- ✅ Supports **50+** concurrent application instances
- ✅ System installation success rate > **95%** (official install script)
- ✅ API response time < **200ms** (P95)

**Reliability Metrics:**
- ✅ System availability > **99%** (excluding planned maintenance)
- ✅ Critical services auto-restart and recover
- ✅ Application data persists through host reboots
- ✅ SSL certificates auto-renew 30 days in advance

**Security Metrics:**
- ✅ All web interfaces enforce HTTPS/TLS 1.3
- ✅ Container network isolation
- ✅ Firewall pre-configured (only necessary ports open)
- ✅ Session timeout mechanism (30 minutes of inactivity)

### Measurable Outcomes

**User Level:**
- Average deployment time reduced from "hours" (manual configuration) to **< 2 minutes**
- Infrastructure configuration time reduced by **90%**
- Application configuration error rate reduced by **80%** (through GitOps version control)

**Operations Level:**
- Zero-downtime deployments (application level)
- Configuration drift eliminated (Git as single source of truth)
- Disaster recovery time < **30 minutes** (via backup restore)

## Product Scope

### MVP - Minimum Viable Product

**Core Features (Required):**

**1. Application Lifecycle Management**
- Browse and search application catalog
- One-click deployment (from docker-compose templates)
- Start/stop/restart applications
- Soft delete (preserve data volumes)
- Physical delete (complete cleanup)
- Rebuild/redeploy applications
- View application logs (real-time)
- Environment variable management

**2. GitOps Integration**
- Built-in Git repository service (Gitea)
- Web-based Git repository management
- Configuration file editing (docker-compose.yml)
- Manual deployment triggering
- Git history and version rollback

**3. Network and SSL Management**
- Reverse proxy management (Nginx Proxy Manager)
- Domain binding (to container ports)
- Let's Encrypt automatic SSL certificates
- Force HTTPS redirect
- Custom SSL certificate upload

**4. Monitoring and Observability**
- System resource monitoring (CPU, memory, disk, network)
- Container resource usage monitoring
- Application health checks
- Historical data queries (minimum 7 days)

**5. Server Management**
- Web terminal (SSH-like)
- File browser (upload/download/edit)
- systemd service management
- Firewall configuration (basic rules)
- System log viewing

**6. User Management**
- Multi-user account support (Linux PAM authentication)
- User creation/deletion (via web interface)
- SSH access control
- **No permission hierarchy** (all users have equal access)

**7. Backup and Recovery**
- Manual backup triggering
- Backup destination configuration (local, S3, etc.)
- File/folder selection
- Backup encryption (AES-256)
- Backup restoration interface
- Backup history

**8. API and CLI**
- RESTful API (application management, lifecycle operations)
- JWT authentication
- CLI tool (aligned with API functionality)
- OpenAPI/Swagger documentation

**MVP Exclusions (Explicitly Not Included):**
- ❌ Application template management (handled in separate project)
- ❌ Permission hierarchy and RBAC (all users equal)
- ❌ Automated scheduled backups (manual backup only)
- ❌ Multi-server/cluster support
- ❌ Kubernetes integration
- ❌ Advanced CI/CD pipelines
- ❌ Advanced monitoring (distributed tracing, APM)
- ❌ Web Application Firewall (WAF)

### Growth Features (Post-MVP)

**Priority 1 (3-6 months):**
- Automated scheduled backups and retention policies
- Backup versioning and incremental backups
- Permission hierarchy system (Admin/Developer/Viewer)
- Application usage statistics and analytics
- Webhook integration (Git push auto-triggers deployment)
- Alert notifications (Email/Slack/Webhook)

**Priority 2 (6-12 months):**
- Advanced monitoring dashboard (Grafana integration)
- Log aggregation and advanced search
- Application template custom editor
- Multi-language support expansion (Japanese, Spanish, etc.)
- Plugin system (community extensions)

### Vision (Future)

**Long-term Vision (12+ months):**
- Application marketplace community contribution platform
- AI-assisted application configuration optimization
- Multi-region deployment coordination (non-cluster, but multiple independent instances)
- Enterprise SSO integration (LDAP/OAuth)
- Disaster recovery automation

## User Journeys

### 1. Solo Developer / Indie Hacker

**User Profile:** Independent developer deploying side projects on a single VPS

**Key Journey:**
1. Install websoft9 on fresh VPS
2. Deploy first app (e.g., WordPress) from app store in < 2 minutes
3. Bind custom domain + get automatic SSL
4. Clone app's Git repo, modify docker-compose.yml
5. Trigger manual deployment, see changes live
6. Monitor resource usage, restart app when needed
7. Backup before major changes

**Required Capabilities:**
- One-click app deployment
- Domain + SSL management
- GitOps workflow (Git repo + manual trigger)
- Basic monitoring
- Manual backup

### 2. Small Development Team

**User Profile:** Startup team (3-5 developers) managing multiple client projects

**Key Journey:**
1. Team lead installs websoft9
2. Creates user accounts for team members (no permission hierarchy needed)
3. Each member deploys different client applications
4. Team uses Git to track configuration changes
5. Members collaborate via shared access to apps
6. Monitor all running applications
7. Perform backups before client demos

**Required Capabilities:**
- Multi-user account management (equal access)
- Multiple concurrent applications
- GitOps for configuration tracking
- Application list/status overview
- Manual backup per application

### 3. Technical SMB Owner / CTO

**User Profile:** Small business owner self-hosting business tools (CRM, collaboration)

**Key Journey:**
1. Deploy business applications from app store (Nextcloud, GitLab, etc.)
2. Configure domains for each business tool
3. Ensure all apps have SSL (data security)
4. Monitor system resources to prevent downtime
5. Backup critical business data regularly
6. Restart applications after updates

**Required Capabilities:**
- App store with business-focused apps
- Domain + SSL management
- System resource monitoring
- Manual backup with encryption
- Application lifecycle control (start/stop/restart)

### 4. System Administrator (Linux-Savvy)

**User Profile:** Sysadmin in school/non-profit transitioning to containers

**Key Journey:**
1. Install websoft9 on existing server infrastructure
2. Use web terminal for familiar Linux operations
3. Manage systemd services alongside containerized apps
4. Browse/edit files via web interface
5. Deploy educational/internal tools from app store
6. Monitor system health and container resources
7. Configure firewall rules

**Required Capabilities:**
- Web terminal (SSH-like)
- File browser with edit capabilities
- systemd service management
- Container + system monitoring
- Firewall configuration
- App deployment

### 5. Platform Administrator (Maintains websoft9 itself)

**User Profile:** Person responsible for keeping websoft9 platform running

**Key Journey:**
1. Monitor websoft9 core services (Portainer, Gitea, Nginx Proxy Manager, etc.)
2. Check system logs when issues occur
3. Restart core services via systemd
4. Update websoft9 components
5. Backup websoft9 configuration
6. View resource usage of platform services

**Required Capabilities:**
- systemd service management (for core services)
- System log viewing
- Container monitoring (including websoft9 containers)
- File access (for config files)
- Manual backup

### 6. Support Personnel

**User Profile:** Person helping users troubleshoot issues

**Key Journey:**
1. Access user's websoft9 instance
2. Check application logs for errors
3. View system resource usage to identify bottlenecks
4. Inspect container status (running/stopped/error)
5. Check reverse proxy configuration
6. Review Git commit history for config changes
7. Test application restart/rebuild

**Required Capabilities:**
- Real-time log viewing
- System + container resource monitoring
- Application status visibility
- Proxy host configuration viewing
- Git history access
- Application lifecycle operations (restart/rebuild)

### Journey Requirements Summary

**From these 6 journeys, we identify these capability areas:**

1. **Application Management**: Deploy, start/stop/restart, rebuild, delete, view logs
2. **App Store**: Browse, search, one-click install
3. **GitOps**: Git repo management, config editing, manual deploy trigger, history
4. **Network**: Domain binding, SSL automation, reverse proxy config
5. **Monitoring**: System metrics, container metrics, real-time refresh
6. **Server Management**: Web terminal, file browser, systemd services
7. **User Management**: Create/delete users, multi-user access (equal permissions)
8. **Backup**: Manual trigger, destination config, encryption, restore
9. **Logging**: Application logs, system logs, search/filter
10. **API/CLI**: Programmatic access for automation
