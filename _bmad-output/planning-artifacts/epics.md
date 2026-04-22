---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
inputDocuments:
  - /workspace/websoft9/_bmad-output/planning-artifacts/prd.md
  - /workspace/websoft9/_bmad-output/planning-artifacts/architecture.md
  - /workspace/websoft9/_bmad-output/planning-artifacts/ux-design-specification.md
notes:
  - This is the English primary planning artifact.
  - The active Chinese working copy is epics_cn.md.
---

# websoft9 - Epic Breakdown

## Overview

This document is the primary English epic-and-story planning artifact for the current Websoft9 refactor track. The active Chinese working copy is maintained as `epics_cn.md` in the same folder.

The current phase target remains unchanged: Websoft9 converges AppHub, Portainer, Gitea, and Nginx Proxy Manager into one product container that runs multiple internal services. Service responsibilities do not change in this phase. The main adjustment in this revision is implementation order.

The approved order is now:

1. Establish the new frontend workspace and prepare single-container convergence.
2. Deliver embedded third-party workspaces and automatic-login continuity.
3. Deliver App Store, My Apps, application access, and product settings.
4. Deliver additional product-native capabilities such as home overview data, users, backup, files, terminal, services, and logs.
5. Deliver direct upgrade and migration work last.

## Requirements Inventory

### Functional Requirements

FR1: Provide a home or overview page centered on Websoft9 product status, task events, alerts, and shortcut entry points rather than host resource monitoring.

FR2: Provide an App Store experience with category filtering, search, app detail, and bilingual app information.

FR3: Provide an app installation flow with parameter configuration, unified task feedback, and a post-install handoff into My Apps.

FR4: Provide a My Apps list and detail experience that preserves old high-frequency information architecture and access continuity.

FR5: Support application lifecycle operations including start, stop, restart, redeploy, and uninstall through unified APIs and task handling.

FR6: If a migrated flow requires product-side login, support administrator or operator initialization independent from host users or Cockpit sessions.

FR7: If Phase 1 requires it, support minimal product-side user management: create, disable, reset password, and delete.

FR8: Provide Websoft9 product settings for domain entry, certificates, mirror sources, internal access, upgrade and version information, plus change recording.

FR9: Provide controlled file management limited to Websoft9-managed volumes, mount directories, and controlled file spaces.

FR10: Provide a controlled host terminal bridge with session protection, boundary clarity, and session metadata recording.

FR11: Provide a Websoft9 core services view with state, health, key indicators, and log drilldown.

FR12: Provide a Websoft9 runtime logs page with time range, severity, and keyword filtering.

FR13: Preserve API integration, automatic login, and full UI access for Gitea, Portainer, and Nginx Proxy Manager.

FR14: Preserve application access and proxy-management workflows built around Nginx Proxy Manager APIs, including basic domain and certificate handling.

FR15: Clearly separate Websoft9 platform entry and internal service proxying from user application domain proxying, even if both still land in one product container during MVP.

FR16: Preserve backup and restore as a primary capability, including backup trigger, list, delete, and restore.

FR17: Support direct upgrade from the current Websoft9 version to the refactored version while preserving core continuity.

FR18: Keep the upgrade path single-path, observable, and recoverable, without introducing a long-lived compatibility runtime.

### Non-Functional Requirements

NFR1: If product accounts and sessions exist in Phase 1, they must stay independent from host accounts.

NFR2: File and terminal capabilities must be scoped to an authenticated user context, and sensitive configuration must not remain exposed to the frontend in persistent plaintext form.

NFR3: Primary navigation and first meaningful interaction for core pages should be available within 2 seconds.

NFR4: Default app list, service list, and log list queries should return within 3 seconds.

NFR5: Phase 1 must support both Chinese and English without `cockpit.locale` or `po.js`.

NFR6: Core long-running tasks require a unified status model with at least running, success, failure, and canceled states plus diagnostic failure details.

NFR7: The frontend must be one unified project or workspace rather than multiple isolated plugin projects.

NFR8: The new control plane must narrow its dependency boundary on third-party management UIs while still preserving third-party API integration and full embedded access where required.

### Additional Requirements

- AppHub remains the unified API surface and main business orchestration layer.
- The frontend stack remains Vite + React 19.2 + TypeScript + React Router v7 + Material UI 9.0.0.
- TanStack Query 5.99.2 owns server-state workflows. Zustand 5.0.12 is limited to cross-route UI state and short-lived workspace coordination.
- REST + OpenAPI remains the default API model. SSE carries long-running task progress. WebSocket remains reserved for terminal transport.
- Third-party UI continuity must land inside Websoft9-owned integration workspaces rather than raw deep links.
- High-risk actions such as terminal, file changes, backup restore, upgrade, and credential management require explicit safety checks and auditability.
- The direct-upgrade migration playbook must exist before migration-sensitive work is considered complete.

## Sequencing Principles

This revision uses the following implementation principles:

1. Start by building the frontend workspace and the runtime convergence foundation.
2. Put embedded third-party continuity before native business migration, so Gitea, Portainer, and NPM remain accessible inside the new shell early.
3. Deliver the native product core next: App Store, My Apps, application access, and settings.
4. Move additional product-native capability after the core flow is stable: overview data, users, backup, files, terminal, services, and logs.
5. Move direct upgrade and migration to the final stage so upgrade design follows the stabilized runtime and user-facing flows.

## FR Coverage Map

FR1: Epic 4 - Product-Native Operations and Observability Expansion
FR2: Epic 3 - Core Application Workflows and Product Settings
FR3: Epic 3 - Core Application Workflows and Product Settings
FR4: Epic 3 - Core Application Workflows and Product Settings
FR5: Epic 3 - Core Application Workflows and Product Settings
FR6: Epic 4 - Product-Native Operations and Observability Expansion
FR7: Epic 4 - Product-Native Operations and Observability Expansion
FR8: Epic 3 - Core Application Workflows and Product Settings
FR9: Epic 4 - Product-Native Operations and Observability Expansion
FR10: Epic 4 - Product-Native Operations and Observability Expansion
FR11: Epic 4 - Product-Native Operations and Observability Expansion
FR12: Epic 4 - Product-Native Operations and Observability Expansion
FR13: Epic 2 - Third-Party Embedded Workspaces and Auto-Login Continuity
FR14: Epic 3 - Core Application Workflows and Product Settings
FR15: Epic 1 - Frontend Workspace and Single-Container Convergence Foundations
FR16: Epic 4 - Product-Native Operations and Observability Expansion
FR17: Epic 5 - Upgrade and Migration Closure
FR18: Epic 5 - Upgrade and Migration Closure

## Epic List

### Epic 1: Frontend Workspace and Single-Container Convergence Foundations

Deliver the new frontend workspace and the single-container convergence foundation first, so every later module lands on the correct product shell and runtime model.

**Why first:** This establishes the technical boundary that everything else depends on. Without the workspace and runtime convergence baseline, embedded integrations, App Store, My Apps, and later migration work would be built on the wrong foundation.

**Scope:**

- Initialize the `console/` workspace and base frontend conventions.
- Establish bilingual app entry, base shell routing, and provider composition.
- Define the single-container multi-process model.
- Start core services inside one product container under a managed process model.
- Separate platform gateway responsibilities from user app proxy responsibilities.
- Freeze the data, config, log, and recoverability boundaries required by the single-container delivery model.

**FRs covered:** FR15

**Key dependencies:** None. This epic is the baseline for all later work.

### Story 1.1: Bootstrap the unified console workspace

As a platform operator,
I want a standalone Websoft9 console workspace,
so that the new control plane can evolve outside the legacy Cockpit plugin structure.

**Acceptance Criteria:**

**Given** the repository still contains only legacy plugin projects
**When** console bootstrapping is completed
**Then** a standalone `console/` workspace exists in the repository
**And** it is based on Vite + React + TypeScript rather than a reused plugin directory.

**Given** the workspace has been created
**When** developers install dependencies and start the dev environment
**Then** the base development server runs successfully
**And** React Router, Material UI, TanStack Query, and base project conventions are already connected.

### Story 1.2: Establish bilingual app entry and base shell routing

As a platform operator,
I want the new console to have a stable bilingual entry, provider stack, and shell-level routing baseline,
so that later features can land under one consistent application boundary.

**Acceptance Criteria:**

**Given** the new `console/` workspace exists
**When** the app entry is initialized
**Then** the project includes base providers, route composition, and shell-level structure
**And** the implementation no longer depends on `cockpit.locale` or `po.js`.

**Given** the console needs Chinese and English support
**When** the i18n baseline is initialized
**Then** locale resources and i18n structure exist for both languages
**And** future navigation and shared shell strings can reuse the same mechanism.

### Story 1.3: Define the single-container multi-process runtime skeleton

As a platform engineer,
I want Websoft9 to define a clear single-container multi-process runtime skeleton,
so that the refactored platform can be delivered as one managed product unit.

**Acceptance Criteria:**

**Given** the current system still runs through multiple containers
**When** the new runtime skeleton is defined
**Then** Websoft9 clearly documents how AppHub, Portainer, Gitea, and NPM coexist inside one product container
**And** the skeleton identifies process management, service order, and health-entry expectations.

**Given** the runtime skeleton has been defined
**When** engineers inspect the delivery model
**Then** they can distinguish platform processes, configuration locations, data locations, and log locations
**And** the model does not require converting all services into one binary.

### Story 1.4: Start core services inside one product container

As a platform operator,
I want AppHub, Portainer, Gitea, and NPM to start inside one product container,
so that Websoft9 runs on the converged deployment topology without rewriting service responsibilities.

**Acceptance Criteria:**

**Given** the single-container runtime skeleton exists
**When** the product container starts
**Then** AppHub, Portainer, Gitea, and NPM start inside that same product container through their native runtimes
**And** the managed runtime can start, stop, and restart them.

**Given** one of the services fails during startup
**When** the product container enters a degraded state
**Then** the runtime exposes a clear failure signal
**And** the system does not collapse into silent startup failure.

### Story 1.5: Separate platform gateway and application proxy responsibilities

As a platform administrator,
I want the platform gateway and application proxy responsibilities to stay separate even in one-container delivery,
so that platform entry, internal services, and user application access do not collapse into one proxy model.

**Acceptance Criteria:**

**Given** the product container hosts both platform entry and application-access capabilities
**When** the gateway boundary is implemented
**Then** Websoft9’s own entry and internal service routing are clearly separated from user application domain routing
**And** the model remains compatible with later physical split deployment.

**Given** NPM still owns application-domain access logic in MVP
**When** the gateway model is reviewed
**Then** platform traffic and application traffic remain logically distinct
**And** the design does not break future isolation decisions.

### Story 1.6: Solidify single-container data, config, and recoverability boundaries

As an engineer responsible for delivery and recovery,
I want the data, configuration, logging, and recoverability boundaries of the one-container model to be explicit,
so that later backup, diagnostics, and migration work remain controlled.

**Acceptance Criteria:**

**Given** the one-container runtime baseline exists
**When** the delivery boundary is finalized
**Then** the key data, config, and log boundaries for AppHub, Portainer, Gitea, and NPM are explicitly identified
**And** the delivery model preserves stable mount or migration expectations.

**Given** later work needs backup, restore, or migration
**When** teams inspect the container delivery model
**Then** they can tell which assets must be retained, moved, or restored
**And** the one-container convergence does not block later recovery work.

### Epic 2: Third-Party Embedded Workspaces and Auto-Login Continuity

Deliver third-party embedded workspaces and auto-login continuity before native App Store migration, so Gitea, Portainer, and NPM stay usable inside the new Websoft9 shell early.

**Why second:** These services are already part of the current operator workflow. Preserving embedded access early reduces migration risk and prevents the new shell from becoming incomplete while native pages are still being built.

**Scope:**

- Introduce integration entry cards and workspace routing.
- Deliver embedded Gitea, Portainer, and NPM access inside product-controlled workspaces.
- Preserve automatic-login continuity or controlled session brokerage.
- Provide failure, degraded-state, and unavailable-state handling for integrations.

**FRs covered:** FR13

**Key dependencies:** Depends on Epic 1 for the new workspace, shell entry, and runtime foundation.

### Story 2.1: Establish integration workspace entry cards

As an operator who uses integrated services,
I want Websoft9 to expose stable integration entry cards and routes,
so that third-party service access is carried by the new product shell rather than scattered legacy links.

**Acceptance Criteria:**

**Given** the new console shell exists
**When** the integrations area renders
**Then** it shows stable entry cards for Gitea, Portainer, and NPM
**And** each card can express available, loading, unavailable, and configuration-error states.

**Given** a service is not yet fully connected
**When** the user opens the integrations area
**Then** the route and container structure still exists for that workspace
**And** later work can extend it without replacing the shell model.

### Story 2.2: Deliver Gitea embedded workspace and session continuity

As an operator who needs repository access,
I want to enter Gitea from within Websoft9 without breaking context,
so that repository operations remain continuous inside the new shell.

**Acceptance Criteria:**

**Given** Gitea is reachable
**When** the user opens the Gitea integration workspace
**Then** Websoft9 provides embedded full-UI access under the product-owned workspace
**And** the user is not forced through a raw external login screen by default.

**Given** Gitea session continuity fails
**When** the workspace cannot establish access
**Then** the UI presents a clear failure state and reason summary
**And** it does not end in a blank or silent failure surface.

### Story 2.3: Deliver Portainer embedded workspace and session continuity

As an operator who needs container-management access,
I want to enter Portainer from within Websoft9 without repeated login interruption,
so that container operations stay continuous inside the new shell.

**Acceptance Criteria:**

**Given** Portainer is reachable
**When** the user opens the Portainer integration workspace
**Then** Websoft9 provides embedded full-UI access under the product-owned workspace
**And** the user is not forced to restart the session from an external login page.

**Given** Portainer access continuity fails
**When** the workspace load fails
**Then** the UI presents an explicit degraded or failed state
**And** it exposes the reason rather than hiding the problem.

### Story 2.4: Deliver NPM embedded workspace and session continuity

As an operator who needs proxy-management access,
I want to enter Nginx Proxy Manager from within Websoft9 with session continuity,
so that proxy operations remain available inside the new shell while native flows are still being migrated.

**Acceptance Criteria:**

**Given** NPM is reachable
**When** the user opens the NPM integration workspace
**Then** Websoft9 provides embedded full-UI access inside the product-owned workspace
**And** default access preserves controlled session continuity.

**Given** NPM integration fails or becomes unavailable
**When** the workspace cannot be established
**Then** the UI presents a clear state, reason summary, and recovery direction
**And** it does not degrade into a hidden iframe failure.

### Story 2.5: Handle integration failures and degraded states consistently

As an operator relying on embedded integrations,
I want failure and degraded integration states to be explicit,
so that I understand whether the problem is availability, configuration, or session continuity.

**Acceptance Criteria:**

**Given** any integration enters a failed, degraded, or misconfigured state
**When** the user views the integration card or workspace
**Then** the UI clearly labels the state and cause summary
**And** it provides a stable recovery or diagnostics entry point.

**Given** one integration fails while others remain healthy
**When** the integrations area renders
**Then** unaffected workspaces stay usable
**And** one broken integration does not collapse the entire integration surface.

### Epic 3: Core Application Workflows and Product Settings

Deliver the native core product flow after the shell and embedded integrations are stable: App Store, install, My Apps, application access, and Websoft9 settings.

**Why third:** This is the first large native user-value epic, but it should land after the workspace and integration continuity are already stable. That sequence reduces migration risk and keeps settings aligned with the new shell rather than legacy flows.

**Scope:**

- App Store list, search, filters, detail, and installation handoff.
- Installation task loop and My Apps handoff.
- My Apps list, detail shell, lifecycle actions, and application access management.
- Product settings and sensitive configuration baseline.

**FRs covered:** FR2, FR3, FR4, FR5, FR8, FR14

**Key dependencies:** Depends on Epic 1 for the shell/runtime base and Epic 2 for embedded integration continuity.

### Story 3.1: Build the App Store list and filters page

As a user looking for applications,
I want to browse and filter the App Store in the new Websoft9 console,
so that I can quickly find installable apps while retaining continuity with the old high-frequency flow.

**Acceptance Criteria:**

**Given** the user opens the App Store page
**When** the page finishes loading
**Then** the UI shows application cards, category filters, keyword search, and base metadata
**And** the information architecture remains recognizable to existing users.

**Given** the user changes category or search criteria
**When** the list refreshes
**Then** the system returns matching application results
**And** default list behavior stays within core performance expectations.

### Story 3.2: Build the app detail and install-parameters page

As a user preparing to install an application,
I want to inspect app details and install parameters first,
so that installation decisions are informed rather than blind.

**Acceptance Criteria:**

**Given** the user opens an app detail page from the App Store
**When** the page loads
**Then** the UI shows description, template or image information, required parameters, and related links
**And** the detail page stays clearly separated from submission actions.

**Given** some parameters come from media or catalog metadata
**When** the detail page renders the install form model
**Then** the backend contract provides those definitions
**And** the frontend does not hardcode installation parameter shapes.

### Story 3.3: Build the installation task loop

As a user installing an application,
I want installation to produce explicit task feedback,
so that I can understand progress, failure causes, and what to do next.

**Acceptance Criteria:**

**Given** the user submits a valid installation request
**When** the backend accepts it
**Then** Websoft9 creates an installation task through the unified API model
**And** the frontend does not execute host commands directly.

**Given** the installation task changes state
**When** the backend updates task status
**Then** the UI shows queued, running, success, failure, or canceled states through one task-feedback model
**And** failure states include a summary and diagnostics entry.

### Story 3.4: Build the My Apps list and detail shell

As a user managing installed applications,
I want My Apps to provide a stable list and detail shell,
so that the old high-frequency management path remains continuous inside the new console.

**Acceptance Criteria:**

**Given** the user opens My Apps
**When** the page loads
**Then** the UI shows installed app name, state, access entry, and base actions
**And** the structure remains recognizable to old users.

**Given** the user opens an application detail page
**When** the page renders
**Then** it exposes at least overview, access, runtime, volumes or files, backup, and uninstall structure slots
**And** the detail layout can carry later lifecycle and operations features.

### Story 3.5: Build lifecycle actions and the application detail header

As a daily operator,
I want high-frequency lifecycle actions at the top of the application detail page,
so that Websoft9 can take over the real application-management path instead of only displaying application information.

**Acceptance Criteria:**

**Given** the user opens an application detail page
**When** the page renders
**Then** the page header exposes access, start, stop, restart, redeploy, and uninstall actions
**And** those actions use one consistent action-header model.

**Given** the user triggers any lifecycle action
**When** the backend accepts the request
**Then** the platform executes it through the unified API and task model
**And** state changes return to the UI within the defined feedback loop.

### Story 3.6: Build application access proxy and certificate management

As an administrator managing application access,
I want My Apps to keep application-domain, proxy, and basic certificate management,
so that the old NPM-based access workflow remains continuous.

**Acceptance Criteria:**

**Given** the user opens an application access configuration area
**When** current access data is loaded
**Then** the UI shows domains, entry address, and base certificate state
**And** the data comes from backend integration with Nginx Proxy Manager APIs.

**Given** the user creates or updates application-domain access settings
**When** the change is submitted
**Then** the system executes a proxy task through the unified task model
**And** the result returns updated access and certificate state.

### Story 3.7: Build product settings and the sensitive-configuration baseline

As a platform administrator,
I want Websoft9 product settings to exist inside the new console,
so that core runtime configuration no longer depends on legacy plugins or direct host-file editing.

**Acceptance Criteria:**

**Given** the user opens the settings area
**When** the page loads
**Then** the UI exposes domain entry, certificates, mirror sources, internal access, upgrade, and version settings groups
**And** the page structure follows the shared shell conventions.

**Given** some fields are sensitive
**When** the current values are displayed
**Then** sensitive values default to masked presentation
**And** the frontend does not become a long-term plaintext secret surface.

### Epic 4: Product-Native Operations and Observability Expansion

After the core flow is stable, deliver the additional product-native capabilities: home overview data, minimal product-side identity where needed, backup, controlled file and terminal tools, services, and logs.

**Why fourth:** These capabilities are important, but they are not the fastest way to prove the new product spine. They should follow the shell, integration continuity, App Store, My Apps, and settings instead of leading the migration.

**Scope:**

- Home overview data and global task feedback.
- Minimal product-side login and user management if required.
- Backup and restore.
- Controlled file and terminal tools.
- Core services view and runtime logs.

**FRs covered:** FR1, FR6, FR7, FR9, FR10, FR11, FR12, FR16

**Key dependencies:** Depends on the stabilized shell, runtime model, and core native product workflow from Epics 1 through 3.

### Story 4.1: Build the home overview and global task-feedback baseline

As a daily operator,
I want the home page to show platform status, recent tasks, and shortcut entries,
so that I can quickly understand system health and the next action after entering Websoft9.

**Acceptance Criteria:**

**Given** the user opens the home page
**When** the page loads
**Then** the page prioritizes platform overview data, recent tasks, and frequent entry points
**And** it does not fall back to host-resource monitoring as the main view.

**Given** long-running actions exist across the platform
**When** the global task area is initialized
**Then** the home page and shared shell provide a reusable task-timeline surface
**And** later install, backup, and other tasks can share the same feedback model.

### Story 4.2: Build minimal product-side login and administrator initialization

As a first-time administrator,
I want Websoft9 to provide minimal product-side login and initialization when a migrated flow truly requires it,
so that high-risk actions no longer rely on host users or Cockpit sessions.

**Acceptance Criteria:**

**Given** the current flow requires product-side authentication
**When** the system detects that no operator account exists
**Then** it enters an initialization path for the first administrator or operator
**And** protected areas are not accessible without the resulting product-side session.

**Given** a user tries to open a protected module without a valid session
**When** the request is evaluated
**Then** the system blocks access to that module
**And** the old Cockpit session model no longer acts as a bypass.

### Story 4.3: Build the basic user-management entry

As a system administrator,
I want a minimal user-management module,
so that future protected flows can rely on product-side user continuity without demanding full RBAC in Phase 1.

**Acceptance Criteria:**

**Given** product-side user management is enabled for the current flow
**When** the administrator opens the user-management area
**Then** the platform supports create, disable, password reset, and delete actions
**And** it does not require a full role matrix to ship.

**Given** a user has been disabled or removed
**When** that user tries to continue using a protected feature
**Then** access is denied
**And** product-side user handling remains decoupled from host accounts.

### Story 4.4: Build the backup list and restore loop

As an administrator responsible for recoverability,
I want backup and restore inside the new console,
so that core protection and recovery flows remain available before upgrade work is finalized.

**Acceptance Criteria:**

**Given** the user opens the backup area
**When** the page loads
**Then** it shows backup list, status, timestamps, and available actions
**And** it supports trigger, list, delete, and restore flows.

**Given** the user triggers backup or restore
**When** the backend accepts the request
**Then** the platform exposes progress and results through the unified task model
**And** failure states provide reason summaries and diagnostics entry points.

### Story 4.5: Build the controlled file-management workspace

As an operator maintaining application mounts and managed files,
I want a controlled file-management workspace,
so that configuration maintenance remains possible without exposing the full host filesystem.

**Acceptance Criteria:**

**Given** the user opens file management
**When** a target application, volume, or mount is selected
**Then** the UI only exposes Websoft9-managed volumes, mount paths, or controlled file areas
**And** the workspace clearly labels the application or mount ownership boundary.

**Given** the user uploads, downloads, creates, renames, edits, or deletes files
**When** the action completes
**Then** the operation stays inside the controlled boundary
**And** the system does not expose the full host file tree.

### Story 4.6: Build the controlled terminal bridge and session audit

As an operator performing advanced diagnostics,
I want a controlled terminal bridge with session records,
so that necessary terminal access is preserved without collapsing security boundaries.

**Acceptance Criteria:**

**Given** the user is authorized to open terminal access
**When** the terminal workspace starts
**Then** Websoft9 establishes the session through a controlled bridge
**And** the capability remains protected by the login context.

**Given** a terminal session starts, exits, or fails
**When** the session metadata is recorded
**Then** the system records at least user, source, start time, and result
**And** host shell permissions are not reimplemented as a second internal permission model.

### Story 4.7: Build the core services view and log drilldown

As a platform operator,
I want to inspect Websoft9 core service state and jump into related logs,
so that platform diagnosis follows a stable path from alert to detail.

**Acceptance Criteria:**

**Given** the user opens the services page
**When** the page loads
**Then** it shows core service name, runtime state, health state, and update time
**And** the scope stays limited to Websoft9 core services or main process components.

**Given** the user inspects one service
**When** that service has a notable metric or issue
**Then** the UI can present key indicator trend context and a jump to the related log view
**And** home, services, and logs stay connected by one diagnostic path.

### Story 4.8: Build the Websoft9 runtime logs page

As an operator investigating failures,
I want a Websoft9 runtime logs page with filters,
so that AppHub, background task, and platform runtime problems can be located quickly.

**Acceptance Criteria:**

**Given** the user opens the logs page
**When** the page loads
**Then** the UI supports time-range, severity, and keyword filters
**And** it covers AppHub, background tasks, and other core runtime log sources.

**Given** the user enters the logs page from services, tasks, or alert cards
**When** the navigation completes
**Then** the page carries relevant context into the initial filter state
**And** the user does not need to rediscover the same failure manually.

### Epic 5: Upgrade and Migration Closure

Deliver direct upgrade and migration last, after the runtime, shell, integrations, native core flows, and operational surfaces have stabilized enough to define a real migration target.

**Why last:** Upgrade is not only a page or task. It is a convergence test of everything else. It should follow the stabilized target system rather than drive premature decisions while the new product model is still moving.

**Scope:**

- Upgrade precheck and migration summary.
- Single-path upgrade execution with clear failure handling.
- Post-upgrade continuity confirmation and repair or recovery entry.

**FRs covered:** FR17, FR18

**Key dependencies:** Depends on the stabilized runtime, shell, integrations, settings, and operational surfaces from Epics 1 through 4.

### Story 5.1: Build the upgrade precheck and migration summary

As a current-version user preparing to migrate,
I want a precheck and migration summary before running upgrade,
so that I understand preserved assets, blockers, and expected carry-forward behavior.

**Acceptance Criteria:**

**Given** the user opens the upgrade entry
**When** the system evaluates the current environment
**Then** it identifies relevant configuration, data, certificates, and third-party entry continuity
**And** it produces a user-readable migration summary.

**Given** blocking issues exist
**When** the user reviews the precheck result
**Then** the UI clearly shows blocker summaries and repair guidance
**And** the system avoids turning the user flow into a complex manual branch tree.

### Story 5.2: Build single-path upgrade execution and failure handling

As a user upgrading from the old version,
I want upgrade execution to remain single-path and observable,
so that migration does not become a guess-heavy multi-step manual procedure.

**Acceptance Criteria:**

**Given** the user confirms the upgrade
**When** execution begins
**Then** the platform presents progress, stage, and state through the unified task model
**And** the user-facing path remains one controlled flow.

**Given** the upgrade fails during execution
**When** the user inspects the result
**Then** the platform shows failure stage, current state, and repair, rollback, or abort guidance
**And** the system stays in a recoverable or repairable state rather than an ambiguous half-finished state.

### Story 5.3: Build post-upgrade continuity confirmation and repair entry

As an upgraded user,
I want a post-upgrade continuity confirmation surface,
so that I can quickly verify that preserved entries, data, and workflows still function and know where to repair them if they do not.

**Acceptance Criteria:**

**Given** an upgrade completes successfully
**When** the user views the completion result
**Then** the UI confirms preserved certificates, entry points, application data, and core workflow continuity
**And** it provides direct next entries into the main product surfaces.

**Given** some migrated capability still requires repair or manual attention
**When** the user views the completion summary
**Then** the system exposes clear repair or diagnostics entry points
**And** post-upgrade verification does not end as an undocumented assumption.

## Sequencing Summary

The confirmed implementation order is now:

1. Epic 1: Build the new frontend workspace and prepare single-container convergence.
2. Epic 2: Deliver third-party embedded workspaces and automatic-login continuity.
3. Epic 3: Deliver App Store, My Apps, application access, and product settings.
4. Epic 4: Deliver additional product-native capabilities such as home overview, users, backup, files, terminal, services, and logs.
5. Epic 5: Deliver direct upgrade and migration last.

## Story Planning Status

This document now reflects the updated implementation order at both epic and story level. Because the sequence has changed materially, any prior implementation-readiness assessment should be considered stale until rerun against this revision.
