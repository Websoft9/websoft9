# Changelog

All notable changes to Websoft9 are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2026-07-23

### Added
- **App Store v2** — Browse and install 200+ open source applications with category filtering, search, and one-click deployment.
- **My Apps** — Unified application lifecycle management: start, stop, restart, redeploy, view logs, and manage files per app.
- **File Manager** — Web-based file browser with upload, download, edit, delete, and permission management for container volumes.
- **Terminal** — Browser-based SSH terminal for remote server management with persistent session support.
- **Proxy & SSL** — Domain binding and free Let's Encrypt SSL certificate management via Nginx Proxy Manager integration.
- **Backups** — Scheduled backup jobs for applications and databases with local and S3 remote storage support.
- **User Management** — Multi-user accounts with role-based access control.
- **Docker Compose GUI** — Upload and deploy custom docker-compose stacks from the web console.
- **Services & Logs** — Real-time core service status monitoring and structured log viewer.
- **Setup Wizard** — Guided first-run initialization for administrator account and basic platform configuration.
- **Platform Settings** — Centralized configuration for ports, mirrors, certificates, branding, and runtime parameters.
- **Multi-language** — English and Chinese (中文) interface support.

### Changed
- **Architecture** — Migrated from Cockpit-based multi-container system to a single-container control plane. All core services (AppHub, Console, Gitea, Portainer, Nginx Proxy Manager) now run inside one Docker container managed by supervisord.
- **Frontend** — Complete rewrite from Cockpit React plugins to a standalone React 19 + TypeScript + Vite + MUI application.
- **Backend** — AppHub API refactored with modular router architecture, improved authentication, and internal gateway trust key mechanism.
- **Installation** — Simplified single-command installer with unified install/upgrade path.
- **Documentation** — Complete rewrite of all user-facing and developer documentation.

### Removed
- **Cockpit dependency** — The platform no longer depends on Red Hat Cockpit as the web framework or host management layer.
- **Legacy plugins** — Removed all Cockpit-based plugins (appstore, myapps, settings, nginx, portainer, gitea).

### Fixed
- **Install & Upgrade** — Comprehensive hardening of install, upgrade, and environment detection flows; resolve image tag from version.json when `--version` is not explicitly provided; decouple container detection from target channel in upgrade path; add version resolution to mixed environment; fix runtime detection and restore flow; fix channel image tag resolution.
- **Uninstall** — Clean up leftover files, fix purge exit semantics, and fill documentation gaps.
- **Docker** — Add cache buster for appstore sync layer to prevent stale image layers; fix file helper lifecycle and volumes smart mount; preserve file ownership on write/create operations.
- **Overview** — API now returns real-time data instead of cached values; fix locale display issues.
- **Terminal** — Fix text selection by removing interfering xterm CSS overrides; add explicit selection colors; use `getSelection()` for reliable text copy.
- **Welcome Page** — Increase health check timeout with retry; add server-level CORS header to prevent redirect errors; update statusError text for both English and Chinese.
- **App Store** — Fix sync persistence across container restarts; fix setup wizard polling timeout.
- **Cloud Marketplace** — Fix onboarding flow: logo display, setup routing, and loading state flicker.
- **Notifications** — Repair WeChat notification shell escaping and timing; replace Cloudflare PURGE_URLS with PURGE_EVERYTHING for cache invalidation.
- **Documentation** — Update demo password in README; correct install URL path (remove `/platform/` segment).
- Docker registry mirror fallback list updated to improve image pull success rate in restricted network environments.

