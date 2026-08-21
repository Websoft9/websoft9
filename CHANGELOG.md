# Changelog

All notable changes to Websoft9 are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0-dev] - 2026-08-21

### Added
- **Scheduled Tasks** — Add managed scheduled tasks for recurring platform operations.
- **External Database Profiles** — Add install profiles for applications that use externally managed databases, including WordPress with external MySQL.
- **Platform Readiness** — Add a readiness endpoint and wait for the platform to become ready before the setup wizard proceeds.

### Changed
- **Installation** — Use the major-minor image tag for fresh installations, while upgrades continue to use the full release version.
- **Image Pulling** — Use registry mirror fallback when pulling utility images.

### Fixed
- **Terminal File Uploads** — Remove the gateway's default 1 MB API request limit for file uploads.

## [2.3.4] - 2026-08-05

### Fixed
- **Setup Wizard** — Improve initialization loading, account form validation layout, and recovery after an application startup failure.
- **Gitea Integration** — Keep automatic sign-in working when the Gitea login page does not expose a CSRF token.

## [2.3.3] - 2026-08-03

### Added
- **App Store Recommendations** — Show related application recommendations based on installed applications.
- **Volume Browser** — Add read-only access to application volumes from My Apps.

### Changed
- **Media Storage** — Persist user-uploaded media files across product container upgrades.
- **Marketplace Configuration** — Migrate marketplace configuration from `bootstrap.json` to `config.ini`.

### Fixed
- **App Store Sync** — Refresh app store data when component versions change instead of incorrectly skipping synchronization.
- **Setup Wizard** — Simplify the post-install flow and automatically open the relevant My Apps dialog with installation progress.
- **My Apps** — Localize volume browser errors and prevent browser loading layout shifts.

## [2.3.2] - 2026-07-29

### Changed
- **Setup Wizard** — Optimized cloud marketplace initialization flow: reduced install wait timeout to 30 seconds with automatic redirect to My Apps, removed retry button to prevent duplicate installs, and permanently disables the wizard page once the bootstrap install is triggered. Validation errors now persist across page refreshes.
- **Host Access** — Improved connection save logic and credential entry dialog.

## [2.3.1] - 2026-07-28

### Added
- **Custom Fields** — My Apps overview now supports customizable fields with inline editing for application metadata management.
- **Docker Mirror Config** — Docker registry mirror configuration now serves as the single source of truth across the platform.

### Changed
- **Mirror Configuration** — Refactored mirror config to single source-of-truth model with data-safe schema migration and backup volume inventory tracking.

### Fixed
- **Product Auth** — Reset form state on mode change to prevent credential leakage across routes.
- **Legacy Migration** — Preserve legacy compose host paths during migration; only restart active Gitea-deployed stacks; skip Portainer stack wait when no stacks exist.
- **Domain Binding** — Fix error parsing to read `details` field instead of `detail` for accurate domain binding error messages.
- **Health Probe** — Keep port 9000 health probe available when HTTPS is enabled.
- **Cloud Marketplace** — Avoid `/auth/setup` flash by deferring redirect to frontend.
- **Channel & Edition** — Remove rc channel; clean up edition_key from version.json and CI pipelines.
- **Mirror URLs** — Handle legacy mirror URL format after upgrade.
- **Welcome Page** — Remove broken brand logo from port 80 welcome page (dynamic asset loading fails on non-console base URL).
- **Custom Fields UI** — Fix standalone card structure, schema migration framework, icon overlap, and empty-row persistence.

### Documentation
- Refine screenshot gallery layout and sizing for marketplace docs.
- Fix marketplace logo sizes, remove broken links, and use full-width screenshots.
- Add install/uninstall parameters, move Cloud Marketplace section upfront, and drop S3 mention.

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

