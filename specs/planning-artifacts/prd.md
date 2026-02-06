---
stepsCompleted: ['complete']
inputDocuments:
  - /data/dev/websoft9/specs/planning-artifacts/product-brief.md
workflowType: 'prd'
classification:
  projectType: 'Infrastructure Tool'
  domain: 'DevOps Tool'
  complexity: 'Medium'
---

# Product Requirements Document - websoft9

**Author:** Websoft9  
**Date:** 2026-02-04  
**Version:** 1.0

## Overview

websoft9 is a GitOps-driven application deployment platform for single-server scenarios. Target users: SMBs and developers without dedicated DevOps teams.

**Core Value:** 300+ app store + GitOps + complete integration (reverse proxy, Git server, SSL, monitoring)

---

## Functional Requirements

### FR-1: Application Lifecycle Management

- **FR-1.1** Browse and search application catalog
- **FR-1.2** One-click deployment from docker-compose templates
- **FR-1.3** Start/stop/restart applications
- **FR-1.4** Soft delete (preserve data volumes)
- **FR-1.5** Physical delete (complete cleanup of containers/networks/volumes)
- **FR-1.6** Rebuild/redeploy applications
- **FR-1.7** View real-time application logs
- **FR-1.8** Manage application environment variables

### FR-2: GitOps Integration

- **FR-2.1** Built-in Git repository service (Gitea integration)
- **FR-2.2** Web-based Git repository management UI
- **FR-2.3** Edit docker-compose.yml files via web interface
- **FR-2.4** Manual deployment trigger (after Git changes)
- **FR-2.5** View Git commit history
- **FR-2.6** Rollback to previous configurations

### FR-3: Network & SSL Management

- **FR-3.1** Reverse proxy management (Nginx Proxy Manager)
- **FR-3.2** Domain binding to container ports
- **FR-3.3** Automatic Let's Encrypt SSL certificates
- **FR-3.4** Force HTTPS redirect
- **FR-3.5** Custom SSL certificate upload support

### FR-4: Monitoring & Observability

- **FR-4.1** System resource monitoring (CPU, memory, disk, network)
- **FR-4.2** Container resource usage monitoring
- **FR-4.3** Application health status checks
- **FR-4.4** Historical metrics data (minimum 7 days retention)
- **FR-4.5** Real-time metric refresh (< 5 seconds)

### FR-5: Server Management

- **FR-5.1** Web terminal access (SSH-like)
- **FR-5.2** File browser (upload/download/edit)
- **FR-5.3** systemd service management (start/stop/enable/disable)
- **FR-5.4** Firewall configuration (basic rules)
- **FR-5.5** System log viewing and search

### FR-6: User Management

- **FR-6.1** Container-internal user management (default websoft9/websoft9 account)
- **FR-6.2** User creation/deletion via Cockpit web interface
- **FR-6.3** User password management and sudo privileges
- **FR-6.4** Equal access for all users (no permission hierarchy in MVP)

### FR-7: Backup & Recovery

- **FR-7.1** Manual backup trigger
- **FR-7.2** Backup destination configuration (local, S3, FTP, etc.)
- **FR-7.3** File/folder selection for backup
- **FR-7.4** Backup encryption (AES-256)
- **FR-7.5** Backup restoration interface
- **FR-7.6** Backup history viewing

### FR-8: API & CLI

- **FR-8.1** RESTful API for application management
- **FR-8.2** JWT-based authentication
- **FR-8.3** CLI tool with API feature parity
- **FR-8.4** OpenAPI/Swagger documentation
- **FR-8.5** API response time < 200ms (P95)

---

## Non-Functional Requirements

### NFR-1: Performance

- **NFR-1.1** System runs stably on 1C2G minimum configuration
- **NFR-1.2** Support 50+ concurrent application instances
- **NFR-1.3** Application deployment time < 2 minutes (average)
- **NFR-1.4** Application start/stop operations < 5 seconds
- **NFR-1.5** Domain + SSL setup < 30 seconds
- **NFR-1.6** API response time < 200ms (P95)
- **NFR-1.7** Web UI dashboard load time < 3 seconds

### NFR-2: Reliability

- **NFR-2.1** System availability > 99% (excluding planned maintenance)
- **NFR-2.2** Application deployment success rate > 95%
- **NFR-2.3** Critical services auto-restart on failure
- **NFR-2.4** Application data persists through host reboots
- **NFR-2.5** SSL certificates auto-renew 30 days before expiry
- **NFR-2.6** No orphaned Docker resources after operations

### NFR-3: Security

- **NFR-3.1** All web interfaces enforce HTTPS/TLS 1.3
- **NFR-3.2** Strong password requirements (8+ chars, mixed case, numbers)
- **NFR-3.3** Session timeout after 30 minutes of inactivity
- **NFR-3.4** Container network isolation
- **NFR-3.5** Firewall pre-configured (only necessary ports open)
- **NFR-3.6** Backup data encryption (AES-256)
- **NFR-3.7** Secrets stored securely (not plain text)

### NFR-4: Usability

- **NFR-4.1** System installation completes in < 15 minutes
- **NFR-4.2** First application deployment in < 2 minutes (new user)
- **NFR-4.3** In-app help links and documentation
- **NFR-4.4** Actionable error messages with suggested fixes
- **NFR-4.5** Mobile responsive (tablet 1024px+ width)

### NFR-5: Compatibility

- **NFR-5.1** OS Support: Ubuntu 20.04+, Debian 11+, CentOS 8+/Rocky Linux 8+
- **NFR-5.2** Docker 20.10+ (tested with 24.x)
- **NFR-5.3** Browser Support: Chrome 90+, Firefox 88+, Edge 90+, Safari 14+

### NFR-6: Maintainability

- **NFR-6.1** Structured JSON logs for all services
- **NFR-6.2** Health check endpoints for critical services
- **NFR-6.3** One-command upgrade mechanism
- **NFR-6.4** Backup/restore for disaster recovery
- **NFR-6.5** Inline code documentation

### NFR-7: Scalability (Single-Server Focus)

- **NFR-7.1** Support 50+ installed applications per instance
- **NFR-7.2** Support 20+ user accounts
- **NFR-7.3** Handle 1TB+ of application data
- **NFR-7.4** Support 100+ reverse proxy host configurations
- **NFR-7.5** No horizontal scaling required (single-server optimization)

---

## MVP Scope

### Included in MVP

All functional requirements (FR-1 through FR-8) and non-functional requirements (NFR-1 through NFR-7) listed above.

### Explicitly Excluded from MVP

- ❌ Application template management (separate project)
- ❌ Permission hierarchy/RBAC (all users equal access)
- ❌ Automated scheduled backups (manual only)
- ❌ Multi-server/cluster support
- ❌ Kubernetes integration
- ❌ Advanced CI/CD pipelines
- ❌ Advanced monitoring (distributed tracing, APM)
- ❌ Web Application Firewall (WAF)

### Post-MVP (Growth Features)

**Priority 1 (3-6 months):**
- Automated scheduled backups
- Permission hierarchy (Admin/Developer/Viewer)
- Webhook integration (auto-deploy on Git push)
- Alert notifications (Email/Slack)

**Priority 2 (6-12 months):**
- Advanced monitoring (Grafana)
- Log aggregation and search
- Multi-language support
- Plugin system

---

## Success Metrics

### User Success
- Application deployment success rate > 95%
- First deployment time < 2 minutes
- User retention > 60% after 30 days

### Business Success
- 1,000+ active installations (6 months)
- 5,000+ GitHub stars (12 months)

### Technical Success
- System availability > 99%
- API response time < 200ms (P95)
- Zero-downtime application deployments
