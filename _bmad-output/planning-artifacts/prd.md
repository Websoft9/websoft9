---
---
stepsCompleted:
  - step-01-init
  - step-02-discovery
inputDocuments:
  - /workspace/websoft9/docs/product/product-brief.md
  - /workspace/websoft9/docs/prd.md
  - /workspace/websoft9/docs/current-architecture-baseline.md
  - /workspace/websoft9/docs/ui-plugin-baseline.md
  - /workspace/websoft9/docs/api-contracts-apphub.md
  - /workspace/websoft9/docs/architecture/tech-architecture.md
  - /workspace/websoft9/docs/sprint-artifacts/stories-overview.md
documentCounts:
  briefCount: 1
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 7
workflowType: prd
classification:
  projectType: web-based self-hosting application management platform
  domain: developer tools and SMB infrastructure management
  complexity: high
  projectContext: brownfield
---

# Product Requirements Document - Websoft9 Refactor

**Author:** Websoft9
**Date:** 2026-04-21
**Status:** Draft
**Version:** 3.0-draft
**Related Documents:** [Current Architecture Baseline](../../docs/current-architecture-baseline.md), [UI Plugin Baseline](../../docs/ui-plugin-baseline.md), [AppHub API Baseline](../../docs/api-contracts-apphub.md)

## 1. Document Purpose

### 1.1 PRD Objective

This PRD defines the target requirements for the Websoft9 product refactor. This is not an incremental feature release. It is a systemic adjustment of the product operating model. The key changes are:

- Replace the Cockpit plugin-based frontend with a Websoft9-owned frontend.
- Preserve the current AppHub-centered backend responsibility model while removing Cockpit from the product path, and converge AppHub, Portainer, Gitea, and Nginx Proxy Manager into a single product container that runs multiple internal services.
- Introduce only the minimum product-side authentication and session capability required by migrated flows, while deferring broader user, API key, and permission-model redesign.
- Converge file management, terminal, services, and logs into capabilities that match the Websoft9 product boundary.
- Preserve the existing automated login and embedded access experience for Gitea, Portainer, and Nginx Proxy Manager.
- Provide a complete direct upgrade path from the current version to the refactored version.

### 1.2 Product Context

Websoft9 has already been running in production for many years. The current implementation has the following characteristics:

- AppHub provides the core business APIs.
- Multiple Cockpit plugins in the `pluings` directory carry the main UI capabilities.
- Third-party services such as Portainer, Gitea, and Nginx Proxy Manager provide part of the control plane capabilities.
- Installation, upgrade, and runtime behavior depend on host root privileges, systemd, Docker, and Cockpit.

This PRD is written for a brownfield refactor. Existing documents may be referenced, but existing assumptions are not treated as design constraints.

### 1.3 Target Audience

- Product and architecture owners
- Frontend and backend engineering teams
- Upgrade and operations teams
- QA and integration validation teams

## 2. Product Vision

Websoft9 Refactor is a self-hosted application management platform for developers and SMB teams. Its goal is to preserve the core value of “app store + my apps + proxy/settings/backup” while removing structural dependency on Cockpit and consolidating a true first-party Websoft9 control plane.

The core product principles are:

1. The Websoft9 frontend and control plane are first-party product capabilities and no longer depend on the Cockpit plugin mechanism.
2. System functions are limited to the scope directly related to Websoft9 product operation instead of trying to be a full host management panel.
3. Users, configuration, logs, and service status are owned by Websoft9, while the permission model may evolve in phases.
4. API integration, automatic login, and full UI access for Gitea, Portainer, and Nginx Proxy Manager must remain continuous.
5. Direct upgrade from the current version to the refactored version must be part of the architecture, not a later patch script.
6. The current refactor track removes Cockpit from the product path and converges AppHub + Portainer + Gitea + Nginx Proxy Manager into one product container with multiple internal services, while preserving their current responsibilities and integration model.

## 3. Problem Statement

### 3.1 Current Problems

The current system has the following root problems:

1. **Frontend capability depends on the Cockpit runtime**  
   Existing plugins heavily depend on `cockpit.js` for locale handling, navigation, file access, and host command execution, which prevents Websoft9 UI from evolving independently.

2. **Control-plane responsibilities are fragmented**  
   AppHub, Portainer, Gitea, Nginx Proxy Manager, and Cockpit together form the control plane. The product boundary is unclear and maintenance cost is high.

3. **The user model does not belong to the product itself**  
   Current access control depends on host Linux users and Cockpit/PAM. This is not suitable for a product-controlled console and makes scoped product-side authorization difficult.

4. **System management boundaries are too wide**  
   In the old model, files, terminal, services, and logs lean toward full host management instead of Websoft9 product management.

5. **The current upgrade model conflicts with the target architecture**  
   The old upgrade process assumes host root, systemd, and Cockpit are already present, which does not align with the future custom frontend and the target single-product-container runtime.

### 3.2 Impact

- Limits long-term frontend product experience and information architecture evolution.
- Increases compatibility and security risk caused by third-party dependencies.
- Enlarges installation, upgrade, permissions, and troubleshooting cost.
- Prevents Websoft9 from forming a truly unified product capability model and development model.

## 4. Goals and Non-Goals

### 4.1 Goals

1. Deliver a custom Websoft9 frontend that does not depend on Cockpit.
2. Preserve the current AppHub-centered backend responsibility model while converging AppHub, Portainer, Gitea, and Nginx Proxy Manager into a single product container that runs multiple internal services.
3. Add the minimum product-side session, operator, and initialization capability required by migrated flows, while deferring broader user and permission redesign.
4. Preserve the main information architecture from the current menus to reduce the learning cost after upgrade.
5. Refactor file management around current-host files accessed through a controlled SSH/SFTP bridge.
6. Provide a controlled host terminal access solution through the same current-host bridge.
7. Display only Websoft9 core service status and Websoft9 runtime logs.
8. Preserve API integration, automatic login, and full UI access for Gitea, Portainer, and Nginx Proxy Manager.
9. Provide a complete direct upgrade path from the current version to the refactored version.
10. Expand application installation from marketplace-template-only flows to a unified installation model that also supports user-authored Docker Compose deployment and runtime-based source deployment.

### 4.2 Non-Goals

1. Websoft9 is no longer positioned as a full host management panel.
2. Phase 1 does not require full recreation of all Cockpit system management capabilities.
3. Phase 1 does not require fully rewriting Portainer, Gitea, and Nginx Proxy Manager as native Websoft9 modules, but it does require preserving their API integration, automatic login, and full UI access.
4. Multi-node orchestration, Kubernetes, or HA cluster support are not goals of this effort.
5. Phase 1 does not attempt to become a general-purpose PaaS, CI/CD platform, or arbitrary buildpack system.
6. Phase 1 does not allow unrestricted privileged Docker Compose options such as host network, privileged containers, or arbitrary host-path mounts without explicit product policy support.

## 5. Target Users

### 5.1 Primary Users

1. **SMB IT teams**  
   Need to deploy and manage multiple self-hosted applications on a single host or lightweight infrastructure.

2. **Developers and technical service providers**  
   Need to deploy, manage, and operate open-source applications quickly while reducing host-level complexity.

3. **Current Websoft9 users**  
   Need a direct upgrade path from the current version to the refactored version without losing core workflows.

### 5.2 Admin Persona

The system administrator is the core persona in the refactored version and is responsible for:

- Initializing the system administrator account
- Managing users and base settings
- Maintaining application deployment, proxy, backup, and upgrade flows

## 6. Core Functional Requirements

### 6.0 Home and Overview

#### FR-HOME-001: Product Home and Overview Page

The system must provide a new home or overview page. This page is no longer centered on host resources and host configuration. It must instead be centered on Websoft9 product status, key operation entry points, and risk notifications.

**Overview page characteristics:**

- Current Websoft9 version, upgrade state, and key system prompts
- Number of installed apps, running apps, and abnormal apps
- Important recent tasks and events such as install, upgrade, backup, restore, and failure alerts
- Summary of Websoft9 core service runtime status
- Summary-level resource information for the home page, such as overall stability or abnormal fluctuations, without expanding into service-level diagnostics
- Common shortcuts such as app store, my apps, settings, backup, logs, and services

**The overview page must not primarily carry:**

- Global host resource panels
- Host network, firewall, users, partitions, and other host-management information
- Generic server monitoring items unrelated to Websoft9 product operation

**Acceptance Criteria:**

- After login, the first thing the home page reflects is Websoft9 platform status rather than host status.
- The home page quickly answers three questions: whether the platform is healthy, whether apps are normal, and whether anything needs attention.
- Summary cards on the home page cover at least app status, task events, and core service status, and can navigate to the corresponding modules such as services, logs, my apps, upgrade, or backup.
- The home page focuses on overview, reminders, and navigation rather than service-level troubleshooting.
- If host summary information is added later, it must remain secondary rather than becoming the primary home view.

### 6.1 Application Store and Catalog

#### FR-APP-001: App Store Browsing

The system must provide an app store page that preserves the current primary information architecture: category filtering, search, card list, app details, and installation entry.

**Acceptance Criteria:**

- Users can browse apps by category and keyword.
- Basic application information is displayed correctly in both Chinese and English UI.
- The app detail page displays description, image or template information, installation parameters, and related links.

#### FR-APP-002: App Installation Flow

The system must provide a unified application installation model and clear task feedback. Phase 1 installation sources include marketplace templates, user-authored Docker Compose deployments, and curated runtime-based source deployment.

**Installation source types:**

- Marketplace template installation from the App Store
- User-authored Docker Compose installation through upload or inline editing
- Runtime-based source deployment, starting with PHP project bundles in Phase 1

**Acceptance Criteria:**

- Users can choose an installation source type before submission when multiple flows are available.
- The installation process is shown through task-state feedback rather than frontend-executed host commands.
- After installation succeeds, the app appears in My Apps with installation-source metadata.

#### FR-APP-002A: Custom Docker Compose Installation

The system must support user-authored Docker Compose installation so operators can install applications that do not come from the curated App Store catalog.

**Acceptance Criteria:**

- Users can create a custom installation by uploading a compose file or editing compose content online.
- Phase 1 may start with single-file compose, but the product model must leave room for companion environment files and future multi-file expansion.
- Before install, the backend validates syntax, normalizes the deployment model, and applies product security policy checks.
- Validation failures must return actionable feedback that identifies the affected field, service, or unsupported directive.
- After installation succeeds, My Apps records the deployment as a custom compose application rather than a marketplace template application.

#### FR-APP-002B: Runtime-Based Source Deployment

The system must support runtime-based source deployment so operators can upload project source code and let Websoft9 provision a curated runtime container and deployment topology for that project type.

**Acceptance Criteria:**

- Users can upload a source bundle for a supported runtime profile.
- Phase 1 must support PHP project deployment as the first curated runtime profile.
- The install flow captures runtime parameters such as runtime version, entry path, public directory, exposed port, and required environment variables.
- The backend converts the source bundle plus runtime profile into a deployable runtime specification and executes it through the same task model used by other installation flows.
- After deployment succeeds, My Apps records the application as a runtime-based deployment and exposes the selected runtime profile in detail views.

### 6.2 My Apps and Lifecycle

#### FR-APP-003: My Apps List and Detail

The system must provide a My Apps page for viewing currently installed applications and their details.

**Acceptance Criteria:**

- The list page shows application name, status, access entry, and basic actions.
- The list page also exposes enough metadata to distinguish marketplace, custom compose, and runtime-based deployments.
- The detail page covers at least overview, access, container or runtime information, volumes or files, backup, and uninstall tabs.
- The detail view exposes installation source, deployment summary, and runtime profile metadata when applicable.
- The information architecture should stay as recognizable as possible compared with the current system.
- High-frequency business paths from the old plugins must stay continuous in the new frontend, especially app browsing, installation, management, settings, backup, and access.

#### FR-APP-004: Lifecycle Management

The system must support start, stop, restart, redeploy, and uninstall operations for applications.

**Acceptance Criteria:**

- Operations are executed through unified APIs and a task system.
- State changes are reflected in the UI within 3 seconds.
- Uninstall supports keeping or cleaning volumes.
- Redeploy and update flows must work for marketplace, custom compose, and runtime-based applications, while clearly surfacing any flow-specific limitations.

### 6.3 Product-Native Authentication and Users

#### FR-AUTH-001: Administrator Initialization

If a migrated flow requires product-side login, the system must support initialization of a Websoft9 administrator or operator account.

**Acceptance Criteria:**

- If the selected Phase 1 authentication model requires a product-side operator account, the system enters an initialization flow when no operator exists.
- Any product-side login introduced in Phase 1 must not depend on host users or Cockpit sessions.

#### FR-AUTH-002: Multi-User Management

The system may provide basic product-side user management capability, but it is not a universal Phase 1 blocker.

**Acceptance Criteria:**

- If product-side users are introduced in Phase 1, support create, disable, password reset, and delete operations for those users.
- Phase 1 does not require complete RBAC or fine-grained permission control.
- Broader multi-user governance can be deferred until after the core migration path is stable.

### 6.4 Settings and Configuration

#### FR-SET-001: Websoft9 Product Settings

The system must provide settings pages related to Websoft9’s own operation.

**Scope includes:**

- Domain and entry configuration
- Certificate configuration
- Registry mirror and download configuration
- System-level API and internal access configuration
- Upgrade and version information

**Acceptance Criteria:**

- Settings updates do not depend on the frontend directly editing host files.
- Sensitive configuration is masked by default in the UI.
- Settings changes record at least operator, operation time, changed item, and result.

### 6.5 File Management

#### FR-FILE-001: Current-Host File Management

The system must provide a file management page for the current host, but file access must be established through a controlled SSH/SFTP bridge owned by Websoft9 rather than by exposing raw host paths, direct browser SSH/SFTP access, or unrestricted host filesystem browsing.

**Acceptance Criteria:**

- If the current Cockpit file manager module or reusable parts of it can be used behind a product-owned SSH/SFTP bridge, reuse should be preferred to reduce development cost.
- Users can browse, upload, download, create, rename, and delete files on the current host through Websoft9-owned APIs.
- The file view must clearly show the current host path context and any product-imposed boundary such as a locked root or recommended working directory.
- Text files support basic online editing.
- File operations must be executed by AppHub over the bound SFTP session and must not expose raw SSH/SFTP connectivity to the browser.
- If terminal and file management share one current-host SSH authorization, host permissions must derive from the bound SSH user rather than from a second internal Websoft9 permission model.
- This host-file workspace does not replace the existing application-detail volume browser. Websoft9 must continue to let operators browse and edit the current application's volumes from My Apps or application detail views through product-owned volume-scoped APIs.

### 6.6 Host Terminal Access

#### FR-TERM-001: Host Terminal Bridge

The system must provide host terminal capability, but it must be implemented through a controlled bridge rather than direct host command invocation from the frontend.

**Acceptance Criteria:**

- Terminal capability requires at least authenticated session protection.
- Terminal and file management may reuse one current-host SSH authorization flow so the operator authorizes once and reuses it across host-access features.
- If the terminal solution uses SSH login, the session inherits the host permissions of the logged-in user, and Websoft9 does not introduce an additional permission system at this layer.
- The system can record session metadata such as start time, user, and source.
- The connection solution must support basic records for session establishment, disconnection, and failure cases.

**Design Constraint:**

The concrete terminal and file implementation can be determined in the architecture and story phases, but the PRD explicitly requires a controlled bridge capability rather than a simple Cockpit replacement. If SSH is used for the current host, the browser still talks only to Websoft9-owned APIs while AppHub owns the SSH PTY and SFTP transport details. Finer-grained permission details are deferred to the execution phase.

### 6.7 Core Services and Logs

#### FR-OPS-001: Core Service View

The system must provide a services page, but it only displays Websoft9 core services.

**Service page characteristics:**

- Item-by-item visibility and diagnosis for Websoft9 core services
- Emphasis on service-level status, resource usage, log linkage, and abnormality troubleshooting
- Acts as the drill-down destination for the summary cards on the home page

**Acceptance Criteria:**

- Display service name, runtime status, health status, and last update time.
- Support key runtime indicators such as CPU and memory for each core service.
- Support graphical trend display for key metrics per core service.
- Support navigation from a service view into the corresponding service logs.
- Phase 1 scope only includes core services or main process components inside the Websoft9 product container.

#### FR-OPS-002: Websoft9 Runtime Logs

The system must provide a logs page, but only for Websoft9’s own runtime logs.

**Acceptance Criteria:**

- Support filtering by time range, level, and keyword.
- Support viewing key log sources such as AppHub, background tasks, and upgrade flows.

### 6.8 Proxy and Access

#### FR-ACCESS-001: Third-Party Service Integration and Access

The system must continue to preserve API integration, automatic login, and full UI access for Gitea, Portainer, and Nginx Proxy Manager.

**Acceptance Criteria:**

- AppHub or an equivalent backend layer continues to integrate and call third-party service APIs to preserve the current in-product automation capability.
- When users enter Gitea, Portainer, or Nginx Proxy Manager from Websoft9, they do not need to log in manually again by default.
- Third-party service pages can continue to be shown inside Websoft9 via embedded pages or equivalent integration so users retain full access to their functions.
- After upgrade, the main workflow of entering third-party services from Websoft9 remains continuous.
- Third-party API integration and UI access are parallel capabilities and both must be preserved.
- If third-party service access fails because the service itself is unavailable, the UI must return an explicit error state rather than failing silently.

#### FR-PROXY-001: App Access and Proxy Management

The system must preserve the current application access and proxy-management workflow in My Apps, which is based on Nginx Proxy Manager APIs.

**Acceptance Criteria:**

- Support creating and updating app access domains.
- Support certificate viewing and basic certificate management.
- Stay continuous with the old My Apps capabilities that were implemented through NPM APIs, instead of introducing abstract models disconnected from the current workflow.

#### FR-PROXY-002: Separation of Internal Proxy and App Proxy Responsibilities

The system must clearly distinguish between two proxy responsibilities:

- Proxying for Websoft9’s own internal services and product entry.
- Domain proxying, access entry, and SSL management for user applications.

**Acceptance Criteria:**

- The two proxy types must be logically separated in both configuration model and runtime responsibility.
- Websoft9’s own entry and internal service proxy responsibilities must be separated from user app-domain proxy responsibilities.
- Websoft9’s own entry and internal service proxy can be handled by the product gateway layer in the retained backbone and do not have to require a new standalone gateway component in Phase 1.
- App-domain proxying, access entry, and SSL management remain centered on Nginx Proxy Manager or an equivalent app-access layer.
- If future deployment requires physical separation, the configuration model and deployment path must not block it.

### 6.9 Backup and Restore

#### FR-BACKUP-001: Application Backup and Restore

The system must preserve the current primary backup and restore capability.

**Acceptance Criteria:**

- Support triggering backup, viewing backup lists, deleting backups, and restoring.
- Phase 1 focuses on recoverability of volumes and application data.

### 6.10 Direct Upgrade

#### FR-UPGRADE-001: Direct Upgrade from the Current Version

The system must support direct upgrade from the current version of Websoft9 to the refactored version.

**Acceptance Criteria:**

- The system can identify key configuration and data locations from the old version.
- It can preserve and convert core configuration, volume data, certificates, and required metadata so the upgraded system can continue to be used directly.
- MVP must already provide a complete user-facing direct-upgrade capability.
- From the user perspective, the upgrade flow should be as simple, converged, and predictable as possible, with success as the default target.
- The upgrade must not break ongoing system operation. Core business entries and main workflows should continue directly after upgrade.
- After upgrade, at minimum the existing certificates, domain entries, application data, and third-party service entries remain available.

#### FR-UPGRADE-002: Upgrade Process Handling Strategy

The system must handle the transition of old plugins, old entries, and old dependencies during the upgrade process, but must not introduce a long-lived compatibility runtime layer.

**Acceptance Criteria:**

- The upgrade process has observable status and rollback or abort strategies for failures.
- The upgrade process must not become a complex user-side branching flow or require users to decide which data to keep and which steps to run manually.
- The user-facing upgrade entry and process must stay on a single path while the product handles internal conversion details.
- If upgrade fails, the system must remain in a clear recoverable or repairable state rather than an ambiguous half-finished state.

## 7. Non-Functional Requirements

### 7.1 Security

- If Phase 1 introduces product accounts and sessions, they must be independent from host accounts.
- Terminal and file management must at least be established within a logged-in user context. If the terminal uses SSH login, host permissions are determined by the SSH user rather than by an internal Websoft9 permission mapping.
- Sensitive configuration must not remain exposed in plaintext to the frontend.
- Custom compose and runtime-source installation must pass backend policy validation before any container or proxy resources are created.
- Phase 1 must explicitly reject unsupported or unsafe directives such as unrestricted host-path mounts, privileged mode, and unsupported network modes unless the product later introduces approved policy exceptions.

### 7.2 Performance

- Primary navigation and first meaningful interaction for core pages should be available within 2 seconds.
- Default queries for app lists, log lists, and service lists should return within 3 seconds.

### 7.3 Internationalization

- Phase 1 must support at least Chinese and English.
- Existing bilingual resources from the old plugins should be reusable, but the implementation must not depend on `cockpit.locale` or `po.js`.

### 7.4 Operability

- Core tasks need a unified status model.
- Key tasks such as upgrade, install, backup, and restore need diagnostic failure information and must distinguish at least running, success, failure, and canceled states.

### 7.5 Maintainability

- The new frontend should be a unified project or unified workspace instead of multiple isolated plugin projects.
- The new control plane must reduce the UI dependency boundary on external management products while continuing to support third-party API integration, automatic login, and full UI access.

## 8. MVP Scope

### 8.1 In Scope for Phase 1

- Custom frontend shell and base navigation
- The minimum login or operator initialization capability required by migrated flows
- App store and My Apps core workflows
- Custom Docker Compose installation with upload or inline editing
- PHP runtime-based source deployment as the first curated runtime profile
- App lifecycle management
- Gitea, Portainer, and Nginx Proxy Manager API integration, automatic login, and full UI access
- Current-host file management through a controlled SSH/SFTP bridge
- Minimal controlled host terminal bridge with shared current-host authorization
- Websoft9 core service status
- Websoft9 runtime logs
- Basic proxy and certificate capability
- Basic backup and restore capability
- Complete direct-upgrade main path from the current version

### 8.2 Out of Scope for Phase 1

- Full host-management functionality
- Fully rewriting Portainer, Gitea, or NPM as native Websoft9 modules in Phase 1
- Multi-node orchestration or cluster capability
- Broad user-model redesign, advanced audit, fine-grained RBAC, and enterprise SSO integration
- Multi-runtime source-deployment expansion beyond the first curated profile set
- Git-driven continuous deployment pipelines, build farm orchestration, and generic application buildpack automation

## 9. Product Risks

1. If the terminal bridge is designed poorly, it can become a security weak point.
2. If the single-container convergence is implemented without clear process supervision, data isolation, and upgrade boundaries, it may introduce unnecessary maintenance cost and operational fragility.
3. If direct upgrade lacks clear processing boundaries, it may reduce upgrade success rate and stability for current users.
4. If the frontend engineering model is not unified early, the old plugin fragmentation problem may continue.
5. If custom compose and runtime-source deployment are added without a clear installation domain model, Websoft9 may fragment into multiple incompatible install paths.
6. If compose policy validation is too permissive, the new installation flows can become an operator-facing security and operability risk.

## 10. Open Decisions for Architecture Phase

The following questions must be clarified during the Create Architecture phase:

1. The exact extension boundary between current AppHub services and newly added migration-critical capabilities inside the single product container.
2. The storage, rotation, and recovery policy for the shared current-host SSH authorization profile.
3. The root-path policy, safe editing boundary, and audit depth for current-host file management.
4. How old Gitea, Portainer, and Nginx Proxy Manager data, API integration, and entry points are converted and carried forward during upgrade.
5. The minimum Phase 1 authentication, initialization, and permission scope required by migrated flows, and which broader user-model concerns remain deferred.
6. The normalized installation domain model for marketplace templates, custom compose deployments, and runtime-based source deployments.
7. The Phase 1 Docker Compose policy boundary, including validation of volumes, networks, environment files, and unsupported directives.
8. The Phase 1 runtime-profile model, starting with PHP source deployment and leaving room for later runtime families.

## 11. Success Metrics

- Current-version users can complete a direct upgrade through a controlled set of steps, preserving legacy data such as certificates without breaking existing core workflows.
- The new frontend covers the existing high-frequency paths: app browsing, installation, management, settings, logs, and services.
- Operators can complete marketplace-template installation, custom compose installation, and PHP runtime-based source deployment through one consistent task-and-management model.
- Authorized operators can complete major product operations through Websoft9 without depending on Cockpit-era host-user workflows.
- After release, the new version no longer depends on Cockpit as the frontend runtime base.
- After upgrading from the old version, third-party service entries, certificates, and application access paths remain available.