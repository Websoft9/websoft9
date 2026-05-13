---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
inputDocuments:
  - /workspace/websoft9/_bmad-output/planning-artifacts/prd.md
  - /workspace/websoft9/_bmad-output/planning-artifacts/ux-design-specification.md
  - /workspace/websoft9/docs/current-architecture-baseline.md
  - /workspace/websoft9/docs/ui-plugin-baseline.md
  - /workspace/websoft9/docs/api-contracts-apphub.md
  - /workspace/websoft9/docs/notes/research.md
workflowType: 'architecture'
project_name: 'websoft9'
user_name: 'Websoft9'
date: '2026-04-21'
lastStep: 8
status: 'complete'
completedAt: '2026-04-21'
---

# Architecture Decision Document

_This document records the final architecture decisions for the current refactor track._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

The PRD defines a control-plane refactor around three capability families: product-owned app workflows such as catalog, install, My Apps, backup, proxy, and settings; controlled operational capability such as product-scoped logs, services, mounted-file management, and a host terminal bridge; and continuity capability such as direct upgrade plus continuous entry into Gitea, Portainer, and Nginx Proxy Manager. The application-workflow family now also expands the install model into three source types: marketplace templates, user-authored Docker Compose deployment, and curated runtime-based source deployment starting with PHP projects. The product is therefore not a generic server panel. It is an application-focused control plane with explicit host-interaction boundaries and one normalized installation domain. App Store and My Apps remain the primary spine and take priority over secondary modules.

**Non-Functional Requirements:**

The main NFRs are security, operability, maintainability, bilingual support, accessibility, and responsive feedback. The system must remove Cockpit-era privilege amplification, make long-running operations diagnosable, converge the fragmented plugin landscape into one frontend workspace plus one coherent backend control plane, support Chinese and English, target WCAG 2.1 AA, and keep core pages responsive.

**Scale & Complexity:**

This project is high complexity. It is not broad enterprise software, but it has enterprise-level architectural sensitivity because upgrade continuity, authentication, task orchestration, external integrations, and host interaction boundaries all change at once.

- Primary domain: web-based self-hosted application control plane
- Complexity level: high
- Estimated architectural components: 10-14 core components and integration boundaries

### Technical Constraints & Dependencies

The key constraint is that AppHub already supports the current core business path and remains the primary backend control layer. This is an evolutionary brownfield refactor around the current AppHub + Portainer + Gitea + Nginx Proxy Manager service responsibilities, but the runtime target is now a single product container hosting those services as internal processes. Cockpit currently supplies i18n context, host command execution, file access, and navigation bridging, so removing it requires explicit replacement layers, not just a frontend rewrite. Direct upgrade is also a hard constraint: the target system must absorb legacy configuration, certificates, app metadata, and third-party entry continuity through migration tooling, transitional adapters, and one visible upgrade path. Material dependencies include host Docker, existing media and docker-library metadata, current AppHub domain and backup logic, and the continued availability of the Portainer, Gitea, and Nginx Proxy Manager integration surfaces.

### Cross-Cutting Concerns Identified

1. Authentication and authorization: introduce the minimum product-facing session and account layer needed after Cockpit removal without forcing an unnecessary backend-core redesign.
2. Task orchestration and auditability: introduce a standard task and audit model for install, redeploy, backup, restore, upgrade, and proxy actions while reusing AppHub as the orchestration center.
3. Upgrade continuity: preserve data, certificates, and key user workflows while moving to the new runtime model.
4. Integration abstraction: continue using third-party services without allowing them to define the product boundary.
5. Host capability isolation: implement controlled bridges for terminal and file access instead of direct frontend host execution.
6. Frontend convergence: replace fragmented plugin projects with a single product shell and shared component architecture.

## Starter Template Evaluation

### Primary Technology Domain

The primary technology domain is a web-based product console with rich client-side interaction, management-heavy list and detail views, and self-hosted deployment expectations. This is closer to a React SPA control plane than to a content-heavy SSR website.

### Starter Options Considered

Two realistic starter directions were evaluated against the current codebase and public documentation:

1. **Next.js 16.2.4 via create-next-app**
  - Strong framework defaults, App Router, server capabilities, and self-hosting support.
  - Better fit when SSR, server components, or mixed content-delivery patterns are core requirements.
  - Less aligned with this migration, which is primarily a self-hosted control-plane SPA with rich in-browser interaction and existing React + MUI continuity.

2. **Vite + React + TypeScript via create-vite 9.0.5**
  - Lightweight, fast local development, strong fit for SPA control consoles, and straightforward integration with React Router and MUI.
  - Better match for replacing the current Cockpit plugin frontend model with a single product-owned shell.
  - Easier migration path from the current CRA-era plugins because it preserves the React model while modernizing tooling.

### Selected Starter: Vite + React + TypeScript

**Rationale for Selection:**

Vite is the better foundation because the target is a self-hosted control console, not an SEO-sensitive or SSR-heavy product. The current baseline already uses React and MUI, React Router fits the required SPA navigation model, and Vite modernizes tooling without forcing server-side framework decisions into the backend control plane.

**Initialization Command:**

```bash
npm create vite@latest console -- --template react-ts
```

**Architectural Decisions Provided by Starter:**

- Language and runtime: TypeScript React scaffold on modern ESM and current Node.js requirements.
- Styling: no locked-in styling system, so Material UI plus Emotion can remain the design-system base.
- Build: Vite dev server, HMR, and production assets for static delivery.
- Testing: no implicit test stack, which keeps testing choices explicit in later stories.
- Organization: simple SPA structure that can expand into a product shell with routes, features, shared UI, and data adapters.
- Developer experience: fast startup, fast rebuilds, and low-friction migration from CRA-era React code.

**Note:** Project initialization using this starter should be the first implementation story for the new console frontend, likely under a dedicated `console/` workspace path rather than inside legacy Cockpit plugin folders.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**

1. The backend core keeps the current AppHub + Portainer + Gitea + Nginx Proxy Manager service responsibilities, with AppHub continuing as the primary business orchestration layer and unified API surface, but those services converge into a single product container as internal processes.
2. This architecture track removes Cockpit dependency, adds only the capabilities required to complete the migration, and avoids backend-core replacement beyond the required topology convergence into one product container.
3. Unless a migrated feature has a specific hard requirement, new backend capabilities should be added as AppHub-hosted routes and services, while legacy API key, account, and permission-model optimization is deferred until after core feature migration is stable.
4. The frontend will be a React 19.2 SPA on Vite, routed with React Router v7, using Material UI 9.0.0 as the shared UI foundation.
5. Long-running operational feedback will use an AppHub-centered task model plus streaming updates: REST for commands and reads, SSE for most task progress, and WebSocket reserved for the terminal bridge transport.

**Important Decisions (Shape Architecture):**

1. TanStack Query 5.99.2 will own server-state caching and invalidation, while Zustand 5.0.12 will be limited to cross-route UI state and ephemeral workspace coordination.
2. Sensitive secrets for third-party integrations will be encrypted at rest, while passwords will be hashed with Argon2id and never stored in reversible form.
3. External systems such as Gitea, Portainer, and Nginx Proxy Manager will be exposed through product-owned integration workspaces under the Websoft9 origin, with backend session brokerage or delegated auto-login rather than raw deep links.
4. Proxy responsibilities stay explicitly separated as concerns: Websoft9 product entry and internal-service routing must not be conflated with user app-domain routing, but MVP may enforce that boundary within the current gateway and Nginx Proxy Manager topology before deciding whether a physically separate gateway is necessary.
5. Gateway responsibilities must be split between platform routing and app-access routing, while legacy authorization, API key governance, and richer user management remain deferred optimization topics unless a specific migrated flow forces earlier work.
6. The direct-upgrade migration playbook is a mandatory implementation artifact before any migration-sensitive development story is considered done.
7. Flexible installation must be implemented as one normalized installation domain in AppHub rather than as separate ad hoc flows for templates, compose deployments, and runtime-source deployments.
8. Phase 1 runtime-based source deployment starts with curated PHP profiles and explicitly defers broader multi-runtime expansion.

**Deferred Decisions (Post-MVP):**

1. Redis is intentionally deferred. The architecture will stay Redis-ready, but MVP will avoid extra infrastructure and rely on the current AppHub persistence baseline plus in-process caches.
2. Multi-node horizontal scaling and HA database topology are deferred. MVP is optimized for single-host self-hosted deployment with clean future expansion.
3. External identity providers such as OIDC or LDAP are deferred until the product-native identity model is stable.

### Installation Domain Architecture

Websoft9 will treat all install entry points as variants of one installation domain rather than as unrelated product surfaces.

**Installation source types in Phase 1:**

1. Marketplace template install sourced from existing App Store metadata.
2. Custom Docker Compose install sourced from uploaded or inline-authored compose content.
3. Runtime-based source deployment sourced from uploaded application bundles plus a curated runtime profile, starting with PHP.

**Normalized installation objects:**

- `installation_source`: identifies whether the request comes from marketplace, compose, or runtime source.
- `installation_spec`: normalized product-owned deployment intent after validation and transformation.
- `runtime_profile`: curated runtime descriptor used only for runtime-source deployments.
- `deployment_revision`: persisted deployment snapshot used for redeploy, diagnosis, and lifecycle operations.

**Processing pipeline:**

1. Accept source payload and installation metadata through AppHub-owned APIs.
2. Validate source-specific inputs.
3. Normalize them into one installation specification.
4. Apply policy checks before any container, volume, network, or proxy resource is created.
5. Execute installation through the unified task model.
6. Persist deployment summary so My Apps and lifecycle flows can treat all application types consistently.

### Data Architecture

**Primary Persistence Choice:**

This track does not force a persistence redesign. AppHub's current configuration and storage model remains the baseline, and new durable state is added only where Cockpit removal or new capabilities make it unavoidable, such as sessions, audit, task history, upgrade checkpoints, and the normalized installation records required by custom compose and runtime-source deployment.

**Persistence & Modeling Approach:**

Existing AppHub configuration, service contracts, and integration metadata should be reused wherever practical. When new durable state is needed, add it in the least disruptive way that preserves compatibility with current AppHub service logic. New capability should default to AppHub extension and AppHub-owned APIs rather than a parallel public backend or a flag-day rewrite of settings and runtime state. For the flexible installation expansion, the new durable state should center on installation-source metadata, deployment revisions, runtime-profile references, and artifact locations for uploaded source bundles. A narrow exception is approved for privileged bridge execution that materially benefits from warm reuse and isolation inside the current product runtime, such as a long-lived internal file-operations sidecar. In that exception, AppHub still owns authentication, authorization, request validation, and the public API contract, while the sidecar remains an internal execution dependency only.

**Validation Strategy:**

Pydantic-style models remain the validation boundary for request, response, settings, and task payload contracts. Validation should occur at transport DTO and domain-service layers first, with persistence-level constraints introduced only where the added capability truly needs them.

**Migration Strategy:**

Data evolution in this track focuses on compatibility-first migration rather than mandatory schema-platform replacement. Any new persistence added for sessions, audit, tasks, or upgrade checkpoints must include import and rollback behavior compatible with the current AppHub runtime and current upgrade path.

**Caching Strategy:**

MVP caching remains conservative and AppHub-centered. Read-heavy catalog metadata and integration capability lookups may use short-lived in-process caches. Redis remains deferred because the current track is not redesigning the backend core for distributed operation.

**Decision Record:**

- Category: Data Architecture
- Decision: Preserve AppHub's current persistence baseline and add new durable state only where Cockpit removal or new features require it
- Version: Compatibility-first continuation of the current AppHub model; no mandatory PostgreSQL/Alembic migration in this architecture track
- Rationale: Minimizes backend-core disruption and keeps core business capability reusable
- Affects: sessions, audit, tasks, upgrade checkpoints, settings compatibility
- Provided by Starter: no

### Authentication & Security

**Authentication Method:**

This track does not treat user-model and API key redesign as day-one blockers. During core migration, AppHub continues to provide the unified backend API surface, and authentication changes are introduced only where a migrated flow strictly requires them. Product-facing accounts, richer session handling, and broader credential cleanup remain follow-on work unless migration exposes a hard dependency.

**Authorization Pattern:**

Authorization in MVP remains intentionally coarse-grained. The baseline is only what is needed to keep migrated platform flows safe and operable. Richer owner or multi-user management, viewer roles, and fine-grained policy matrices stay deferred unless a concrete feature requires them earlier. High-risk capabilities such as terminal access, host file manipulation, backup restore, upgrade execution, and third-party credential management still require explicit capability checks.

**Secret & Credential Protection:**

When these capabilities are introduced, passwords and product credentials should use modern password hashing and encrypted secret handling. Third-party tokens and integration secrets should move away from broad plaintext exposure over time, but that cleanup should be incremental AppHub hardening after the migration-critical path, not an up-front secret-platform rewrite.

Custom compose and runtime-source deployment must also pass product-owned policy validation before any deployment resources are created.

**Security Middleware & Transport Controls:**

The backend will enforce secure cookie settings, CSRF protection for mutating requests, same-origin defaults, explicit CORS allowlists only where needed, and structured audit logging for privileged actions. TLS termination is expected at the reverse-proxy edge, but backend trust of upstream headers must remain explicit and minimal.

**API Security Strategy:**

Authentication endpoints, terminal bridges, file bridges, backup restore endpoints, upgrade actions, and flexible-installation submission endpoints must receive stricter protection than general reads. Coarse rate limiting should be applied at the proxy layer, while app-level throttling and explicit guards protect sensitive command endpoints. If terminal access is implemented through SSH-backed session establishment, Websoft9 authorization gates the creation of the terminal session, while host-level permissions continue to derive from the bound SSH user rather than from a second internal shell permission model. Compose policy validation must reject unsupported directives such as unrestricted host-path mounts, privileged containers, and disallowed network modes unless a future product policy explicitly introduces controlled exceptions.

**Decision Record:**

- Category: Authentication & Security
- Decision: Keep authentication and credential changes minimal during core migration, and defer broader API key, user, and secret-governance optimization unless a migrated capability requires earlier work
- Version: Compatibility-first continuation of the current AppHub security baseline during migration; no external IdP in MVP
- Rationale: Keeps the migration focused on removing Cockpit and preserving core operations instead of reopening legacy auth design too early
- Affects: login, settings, terminal bridge, file bridge, integrations, audit, upgrade
- Provided by Starter: no

### API & Communication Patterns

**API Style:**

The public control-plane contract stays REST-first and JSON-first. This matches the existing FastAPI shape, the current AppHub baseline, and the management-heavy UX. GraphQL adds flexibility but does not materially reduce complexity for this domain.

**Backend Framework Direction:**

FastAPI remains the backend framework baseline, currently documented as FastAPI 0.136.0. The backend should be evolved rather than replaced wholesale, though its authentication, persistence, and integration layers still need refactoring around the new domain boundaries.

**Streaming & Realtime Communication:**

The architecture separates operational progress from interactive streams. SSE is the default realtime channel for task progress, log tails, and background status because it is simpler operationally and fits one-way updates. WebSocket is reserved for browser-to-terminal transport because only that path requires bidirectional low-latency interaction.

**API Documentation & Contracts:**

OpenAPI remains the authoritative machine-readable API contract. API groups should align to product capabilities rather than implementation history, but the current AppHub route shape is still the baseline implementation surface. Unless a special requirement proves otherwise, new capabilities should be added as evolutionary AppHub routes and services so AppHub remains the unified API layer rather than growing a parallel backend platform.

**Compatibility Strategy:**

The architecture cannot assume a flag-day contract rewrite. Existing API key, snake_case, and `code/message/data` response patterns should be treated as the practical AppHub baseline. The new console should adapt to them where possible, and only introduce additive translation or normalization where Cockpit removal or new workflows make it necessary. If a deeper contract redesign is desired later, it should be planned as a separate redesign effort.

**Installation API Strategy:**

Flexible installation remains AppHub-owned. The product should expose one installation surface with source-type-aware request models rather than inventing three disconnected public APIs. Compose parsing, runtime-profile rendering, and source-bundle handling may use internal helper services, but AppHub remains the only public policy and contract boundary.

**Third-Party Workspace Strategy:**

Third-party full UI access will be delivered through product-owned integration workspaces mounted under the Websoft9 origin. The backend must broker session continuity through a supported mechanism verified against each upstream product, such as server-side session establishment with proxied upstream cookies or delegated bootstrap tokens exchanged inside a controlled gateway. Deep-linking directly to third-party login screens is not considered sufficient for MVP because the PRD requires preserved automatic login and full in-product UI continuity.

**Proxy Responsibility Model:**

Product entry and internal-service routing are owned by the Websoft9 platform gateway layer. App-domain proxying, SSL issuance, and app-facing access configuration are owned by a separate app-access layer, currently centered on Nginx Proxy Manager. This separation is mandatory at the responsibility level so the product does not repeat the legacy conflation of internal entry routing and user-app proxy responsibilities, but MVP may realize it through the retained backbone before introducing another standalone gateway component.

**Service Communication Model:**

MVP will avoid premature service decomposition. Internal communication stays in-process between domain modules, while external calls to Docker, Portainer, Gitea, and Nginx Proxy Manager pass through explicit gateway/adaptor layers with typed request and error translation boundaries.

The approved exception is the privileged file bridge. File browsing and mutation continue to enter through AppHub-owned REST endpoints, but AppHub may delegate low-level file execution to a long-lived internal sidecar running in the current container topology rather than launching an ephemeral helper container per request. That sidecar must not become a second product API. It is reachable only from AppHub over an internal channel such as localhost or a Unix socket, and it receives already-authorized, already-canonicalized operations scoped to approved Docker-volume roots.

**Decision Record:**

- Category: API & Communication
- Decision: REST + OpenAPI + SSE for task streams + WebSocket only for terminal bridge
- Version: FastAPI 0.136.0 baseline
- Rationale: Fits current backend, keeps operational complexity low, and matches control-plane interaction patterns
- Affects: task execution, logs, terminal, integrations, frontend data access
- Provided by Starter: no

### Frontend Architecture

**Routing & Application Shell:**

The frontend uses React 19.2 with React Router v7 in an SPA data-router model. Routing follows product information architecture rather than legacy plugin packaging: app store, my apps, operations, integrations, and settings under one authenticated shell. Route modules split by feature domain, not by low-level component type.

**State Management:**

TanStack Query 5.99.2 owns server state and network lifecycle. Zustand 5.0.12 is limited to cross-route UI state such as workspace panes, persistent filters, and transient shell coordination. Global business stores remain the exception.

**Component Architecture:**

Material UI 9.0.0 is the base component system, but product-specific primitives must wrap it so the design system belongs to Websoft9 rather than raw vendor components. The component tree should stay layered into app shell, design-system primitives, shared domain widgets, and feature modules.

**Performance Strategy:**

The architecture optimizes perceived responsiveness rather than synthetic micro-benchmarks. Standard patterns include route-level code splitting, feature-level chunking, list virtualization, optimistic updates only for low-risk reversible actions, and background prefetch for likely next views. Heavy detail views should stream status progressively instead of blocking on all secondary data.

**Bundle Strategy:**

Vite build output should be manually chunked along stable feature boundaries where analysis shows real payoff. Icon imports and large utility packages must be tree-shaken. Shared shell code should remain lightweight so authenticated navigation stays fast.

**Decision Record:**

- Category: Frontend Architecture
- Decision: React 19.2 + React Router v7 + Material UI 9.0.0 + TanStack Query 5.99.2 + Zustand 5.0.12
- Version: React 19.2, React Router v7, Material UI 9.0.0, TanStack Query 5.99.2, Zustand 5.0.12
- Rationale: Preserves React continuity, modernizes data/state handling, and supports a single converged product shell
- Affects: console workspace, app store, my apps, settings, operational flows
- Provided by Starter: partially

### Infrastructure & Deployment

**Deployment Model:**

MVP deployment remains self-hosted and single-node. The runtime topology converges AppHub + Portainer + Gitea + Nginx Proxy Manager into a single product container with Cockpit removed from the product path. This is a topology convergence rather than a service-responsibility rewrite, so the services continue to run with their native runtimes under one product-managed process supervision layer.

For the file-management bridge, the target runtime should prefer a long-lived internal `files-agent` style sidecar or co-scheduled helper process over per-request helper-container startup. This keeps privileged file access inside the current container estate without requiring a host-resident daemon, while materially reducing cold-start cost, request fan-out, and script-fragment drift in the file-management path.

**Environment Configuration:**

Runtime configuration should split cleanly. Deployment-time immutable settings and sensitive secrets move toward typed environment variables plus secret mounts, while product-editable operational settings remain AppHub-managed configuration with validation, auditability, and migration support. Repository-tracked ini files may still appear in migration tooling, but they are not the long-term source of truth for mutable product settings.

**CI/CD Direction:**

The delivery pipeline should validate three layers: static checks, automated tests, and containerized integration smoke tests. Release artifacts should include the frontend bundle, AppHub build output, and the versioned upgrade and deployment assets required by the single-product-container multi-service runtime. Release automation must preserve the direct-upgrade path.

**Monitoring & Logging:**

Structured logs, health endpoints, task telemetry, audit trails, and upgrade diagnostics are mandatory. Because the PRD requires graphical trend views for core service indicators, MVP also needs a lightweight metrics sampling path with short-retention history. This should preferably be implemented as an additive AppHub-oriented capability rather than as a new observability platform.

**Scaling Strategy:**

The architecture is intentionally optimized for vertical scaling first. Stateless HTTP handling, AppHub-managed sessions, and adapter boundaries keep the path open for future multi-instance control-plane deployment, but that is not an MVP promise.

**Decision Record:**

- Category: Infrastructure & Deployment
- Decision: Single-node self-hosted deployment that converges AppHub + Portainer + Gitea + NPM into one product container while removing Cockpit and adding audit-safe frontend integration
- Version: Single-product-container multi-service runtime in this architecture track; no Redis or HA topology in MVP
- Rationale: Keeps the working backend service responsibilities intact while aligning delivery topology to the current product constraint
- Affects: install, upgrade, backup, supportability, release engineering
- Provided by Starter: no

### Decision Impact Analysis

**Implementation Sequence:**

1. Initialize the new `console/` frontend workspace on Vite + React + TypeScript.
2. Produce the direct-upgrade migration playbook and compatibility plan for contracts, data carry-forward, and rollback behavior.
3. Extend AppHub with the minimum migration-critical routes, task support, and capability additions required after Cockpit removal.
4. Make the product-entry routing boundary and app-access routing boundary explicit before proxy-sensitive feature migration, initially reusing the retained gateway and Nginx Proxy Manager topology where practical.
5. Introduce the task orchestration model plus SSE status streaming through AppHub as the unified API layer.
6. Migrate App Store and My Apps onto the new product shell and AppHub-backed typed API contracts.
7. Rebuild terminal, files, backup, restore, and upgrade bridges behind explicit safety boundaries, adding only the minimum guards required for each migrated flow. For file management specifically, replace per-request helper-container execution with a long-lived internal file-execution sidecar or equivalent warm bridge inside the product runtime.
8. Complete integration adapters, auto-login workspaces, direct-upgrade tooling, and other migration-critical compatibility work.
9. After core migration stabilizes, address deferred legacy optimization topics such as API key governance, user/account redesign, credential hardening, and richer authorization models.

**Cross-Component Dependencies:**

The AppHub-centered backend decision preserves current business behavior and constrains new capability placement: unless a special requirement appears, new capability lands as an AppHub extension exposed through AppHub APIs. The gateway split constrains proxy, third-party workspace, and product entry because platform routing and app-domain routing are separate concerns. REST plus SSE shapes frontend data access and task orchestration contracts. The state-management decision preserves modular migration by avoiding a monolithic client store. Because the backend core is preserved and legacy auth cleanup is deferred, the migration playbook and compatibility strategy matter more than backend-topology redesign or early user-model rework.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**

The chosen stack creates predictable consistency risks: Python versus TypeScript naming drift, database naming inconsistency, API payload drift, route and file naming divergence, duplicate shared components, inconsistent task streaming, and uneven error or loading handling. The rules below define the implementation baseline.

### Naming Patterns

**Database Naming Conventions:**

1. Tables use plural snake_case names: `users`, `app_installations`, `task_events`.
2. Primary keys use `id` unless a foreign aggregate identifier is semantically required; foreign keys use singular object name plus `_id`: `user_id`, `installation_id`.
3. Timestamp columns use explicit names: `created_at`, `updated_at`, `completed_at`, `deleted_at`.
4. Enum-like values are lower snake_case strings, never mixed-case literals.
5. Indexes and constraints use deterministic names: `ix_users_email`, `uq_users_username`, `fk_task_events_task_id`, `ck_sessions_expired_at`.

**API Naming Conventions:**

1. REST resources use plural kebab-case path segments when needed: `/api/v1/apps`, `/api/v1/my-apps`, `/api/v1/task-streams`.
2. New additive console-owned path parameters should use semantic names consistently at the HTTP boundary: `{appId}`, `{taskId}`, `{proxyId}`.
3. Normalized console-facing query parameters and JSON fields should prefer camelCase externally, while reused AppHub baseline endpoints may preserve legacy naming during migration.
4. HTTP headers use standard casing; product-specific request tracing uses `X-Request-Id`.
5. API versions live only at the prefix level; no version suffixes in field names or route names.

**Code Naming Conventions:**

1. Python packages, modules, functions, and variables use snake_case.
2. Python classes, Pydantic models, and other persistence models use PascalCase.
3. React components and files exporting a component use PascalCase: `AppCard.tsx`, `TaskTimeline.tsx`.
4. Frontend hooks use `useXxx.ts`; utility files use camelCase only for exported functions, while filenames remain kebab-case or lowercase by category: `use-app-filters.ts`, `formatDate.ts` is not allowed.
5. Frontend feature directories use kebab-case: `app-store`, `my-apps`, `system-settings`.

### Structure Patterns

**Project Organization:**

1. Backend organization preserves the current AppHub router, service, schema, and external-integration layering; new capabilities should extend those feature-aligned boundaries rather than inventing a second backend module tree.
2. Frontend organization is by feature domain first, with `shared/` reserved only for primitives or cross-feature contracts.
3. External service integrations never appear directly inside route handlers or React views; they live behind explicit adapters or client modules.
4. Task execution logic is centralized in the backend task subsystem, not reimplemented per feature.
5. Upgrade, terminal, and file access stay isolated in privileged modules and are never mixed into general settings or app-list handlers.

**File Structure Patterns:**

1. Backend tests live under `apphub/tests/unit` and `apphub/tests/integration`; frontend unit tests are co-located as `*.test.ts(x)` and end-to-end tests live under `console/tests/e2e`.
2. API schemas/contracts are defined once and reused; route handlers do not inline anonymous response shapes.
3. Environment examples live beside their workspace roots as `.env.example`; secrets never appear in committed env files.
4. Static assets belong to `console/public/` only if they are deployment assets; feature-owned media belongs inside the relevant feature folder.

### Format Patterns

**API Response Formats:**

New additive console-facing successful JSON responses should prefer a consistent envelope:

```json
{
  "data": {},
  "meta": {
    "requestId": "req_123",
    "generatedAt": "2026-04-21T08:00:00Z"
  }
}
```

Collection responses add pagination or filter metadata under `meta`. Command-style responses that start async work return `data.taskId`, `data.status`, and `data.nextPoll` or stream URL when relevant. Reused compatibility endpoints may continue returning existing AppHub shapes until the migration plan explicitly retires them.

New additive console-facing errors should converge on a problem-details-inspired structure:

```json
{
  "error": {
    "code": "proxy.domain_conflict",
    "message": "The domain is already in use.",
    "details": {
      "domain": "app.example.com"
    },
    "requestId": "req_123"
  }
}
```

**Data Exchange Formats:**

1. Normalized console-facing JSON should prefer camelCase, while compatibility endpoints may keep current AppHub field naming when that avoids unnecessary breakage.
2. Internal Python models may stay snake_case, but aliasing and translation rules must be explicit and one-way consistent.
3. Dates and times use ISO 8601 UTC strings with `Z` suffix.
4. Booleans are always `true` or `false`; status is never encoded as `0` or `1` in external contracts.
5. Null is preferred over empty-string sentinel values.
6. Legacy `code/message/data` envelopes may remain behind compatibility endpoints until upgrade-sensitive clients are retired or explicitly migrated.

### Communication Patterns

**Event System Patterns:**

1. SSE event names use lowercase dotted domain names: `task.updated`, `backup.completed`, `upgrade.failed`.
2. Every event payload includes `type`, `version`, `occurredAt`, and `data`.
3. WebSocket messages for terminal sessions use explicit packet types such as `terminal.input`, `terminal.output`, `terminal.resize`, `terminal.exit`.
4. Background task state changes are emitted from the central task subsystem only; feature modules publish state through that subsystem instead of inventing custom streaming contracts.

**State Management Patterns:**

1. TanStack Query owns all server-state fetching, caching, invalidation, and background refetch.
2. Query keys use stable arrays by domain: `['apps', 'list', filters]`, `['tasks', taskId]`, `['settings', 'general']`.
3. Zustand stores are limited to shell and workspace state and must use slice-based organization.
4. Derived state lives in selectors or query transforms, not duplicated into multiple stores.
5. Mutations invalidate or patch query cache explicitly; hidden implicit refresh logic is not allowed.

### Process Patterns

**Error Handling Patterns:**

1. Backend route handlers raise typed domain errors and rely on central exception mapping.
2. Logs keep technical details; user-facing messages stay concise and actionable.
3. Frontend views render inline recoverable errors at the feature boundary and use route-level error boundaries for unrecoverable failures.
4. Destructive actions always return a stable machine-readable error code if they fail.

**Loading State Patterns:**

1. Page-level initial loads use skeletons.
2. Table refreshes use non-blocking progress indicators and preserve existing data when safe.
3. Button-triggered mutations show pending state on the action origin, not only global spinners.
4. Long-running operations immediately transition into tracked tasks with visible status linkage.

### Enforcement Guidelines

**All AI Agents MUST:**

1. Keep database naming snake_case and document clearly where normalized console-facing camelCase contracts coexist with compatibility endpoints.
2. Add new business capability code under the correct feature/module boundary instead of `utils` or `common` by default.
3. Reuse the centralized response, error, and task-streaming patterns rather than inventing per-feature variants.

**Pattern Enforcement:**

1. Architecture-breaking deviations should be treated as review findings, not stylistic preferences.
2. Shared contract changes must update both backend schemas and frontend typed clients in the same unit of work.
3. New modules should add at least one example test proving they follow the canonical boundary pattern.

### Pattern Examples

**Good Examples:**

1. Backend: `apphub/src/api/v1/routers/app.py` should return explicit response schemas instead of leaking raw upstream payloads, while `apphub/src/services/app_manager.py` keeps snake_case service logic and adapter calls.
2. Frontend: `features/my-apps/api/useMyAppsQuery.ts` owns fetch/invalidation, while `features/my-apps/components/MyAppsTable.tsx` stays presentation-first.
3. Task action: a backup request returns `taskId`, then the UI subscribes to `task.updated` SSE rather than polling arbitrary endpoints.

**Anti-Patterns:**

1. Returning raw persistence objects or upstream client payloads directly from route handlers.
2. Placing integration logic for Portainer or NPM inside React components.
3. Creating a single global Zustand store for all business state.
4. Mixing host-privileged terminal/file code into generic settings or app-management modules.

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
websoft9/
├── README.md
├── CHANGELOG.md
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose-dev.yml
│   ├── apphub/
│   └── proxy/
├── docs/
│   ├── architecture.md
│   ├── prd.md
│   ├── epics/
│   └── sprint-artifacts/
├── media/
│   ├── media.json
│   └── media/
├── console/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── .env.example
│   ├── public/
│   │   └── locales/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/
│   │   │   ├── App.tsx
│   │   │   ├── providers/
│   │   │   ├── router/
│   │   │   └── shell/
│   │   ├── shared/
│   │   │   ├── api/
│   │   │   ├── config/
│   │   │   ├── design-system/
│   │   │   ├── i18n/
│   │   │   ├── lib/
│   │   │   └── types/
│   │   ├── features/
│   │   │   ├── overview/
│   │   │   ├── app-store/
│   │   │   ├── my-apps/
│   │   │   ├── proxy-management/
│   │   │   ├── backup-restore/
│   │   │   ├── system-settings/
│   │   │   ├── identity/
│   │   │   ├── tasks/
│   │   │   ├── integrations/
│   │   │   │   ├── gitea/
│   │   │   │   ├── portainer/
│   │   │   │   └── nginx-proxy-manager/
│   │   │   └── host-tools/
│   │   │       ├── terminal/
│   │   │       └── files/
│   │   └── test/
│   │       └── setup/
│   └── tests/
│       └── e2e/
├── apphub/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .env.example
│   ├── src/
│   │   ├── main.py
│   │   ├── media.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── routers/
│   │   │           ├── app.py
│   │   │           ├── backup.py
│   │   │           ├── proxy.py
│   │   │           ├── settings.py
│   │   │           ├── auth.py
│   │   │           ├── overview.py
│   │   │           ├── terminal.py
│   │   │           ├── files.py
│   │   │           ├── integrations.py
│   │   │           ├── tasks.py
│   │   │           ├── audit.py
│   │   │           └── upgrade.py
│   │   ├── services/
│   │   │   ├── app_manager.py
│   │   │   ├── back_manager.py
│   │   │   ├── proxy_manager.py
│   │   │   ├── settings_manager.py
│   │   │   ├── portainer_manager.py
│   │   │   ├── gitea_manager.py
│   │   │   ├── auth_manager.py
│   │   │   ├── task_manager.py
│   │   │   ├── audit_manager.py
│   │   │   ├── terminal_manager.py
│   │   │   ├── file_manager.py
│   │   │   └── upgrade_manager.py
│   │   ├── external/
│   │   │   ├── gitea_api.py
│   │   │   ├── nginx_proxy_manager_api.py
│   │   │   └── portainer_api.py
│   │   ├── schemas/
│   │   ├── core/
│   │   ├── config/
│   │   ├── data/
│   │   ├── cli/
│   │   └── utils/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
├── scripts/
└── tools/
```

### Architectural Boundaries

**API Boundaries:**

1. `apphub/src/api/v1/routers` remains the primary public HTTP boundary.
2. Route handlers should continue to translate HTTP concerns into AppHub service calls using the existing router/service layering.
3. Authentication, permission evaluation, request IDs, and response handling should be applied at the API layer without forcing a backend-core reorganization.

**Component Boundaries:**

1. `console/src/app` owns shell, providers, and route composition.
2. `console/src/features/*` owns domain UI, queries, forms, and page composition for one business capability.
3. `console/src/shared/design-system` owns reusable primitives only; it does not absorb domain widgets.

**Service Boundaries:**

1. Backend business rules should continue to live primarily in existing AppHub service classes.
2. Existing `external/` integrations remain the translation boundary to third-party APIs.
3. Shared task and audit infrastructure should be added around the existing AppHub service model rather than by replacing it.

**Data Boundaries:**

1. The current AppHub persistence baseline remains the operational source of truth in this track.
2. Media/catalog metadata continues to enter through existing AppHub catalog logic and should be normalized before reuse.
3. Secrets remain encrypted or masked inside the smallest required service boundary as audit optimization is introduced.

### Requirements to Structure Mapping

**Feature/Epic Mapping:**

1. Application Management epic maps to `console/src/features/app-store`, `console/src/features/my-apps`, plus existing AppHub `api/v1/routers/app.py`, `services/app_manager.py`, and related schemas/external integrations.
2. Proxy Management epic maps to `console/src/features/proxy-management`, existing AppHub proxy routers/services, and existing Nginx Proxy Manager integration code.
3. Backup & Restore epic maps to `console/src/features/backup-restore`, existing AppHub backup routers/services, and additive task or audit support where needed.
4. System Settings epic maps to `console/src/features/system-settings`, existing AppHub settings routers/services, and additive session/audit support.
5. PRD-only control-plane capabilities beyond the older epics map to new console features plus additive AppHub routers/services for overview, identity/session, tasks, host-tools, upgrade, and audit.
6. The file-management requirement also carries an explicit brownfield reuse check against existing Cockpit file-manager assets or reusable implementation pieces before a full rewrite is approved.

**Cross-Cutting Concerns:**

1. Authentication and coarse-grained MVP authorization live in additive AppHub identity/session capability plus frontend app providers and route guards.
2. Task orchestration spans additive AppHub task/audit infrastructure and frontend task/notification surfaces.
3. Internationalization lives in `console/src/shared/i18n` and backend message definitions, not in ad hoc string duplication.

### Integration Points

1. Frontend features communicate through typed shared API clients and query invalidation, not direct cross-feature imports.
2. Backend capabilities communicate through existing AppHub services and shared task dispatching, not route-to-route calls.
3. Gitea, Portainer, and Nginx Proxy Manager continue through isolated AppHub adapters and contract tests.
4. Docker and host tooling access remain behind privileged backend services.
5. Core flow stays consistent: user action -> frontend mutation -> backend route -> module service -> task/integration/repository; long-running work persists task state, emits SSE, and updates task views.

### File Organization Patterns

1. Workspace config stays at workspace roots; runtime secrets use environment variables or mounted secret files.
2. Frontend source remains feature-first; backend source remains evolutionary around the current AppHub router/service/external/core structure.
3. Shared code must prove reuse across at least two domains before entering a common layer.
4. Backend unit tests validate services and policies; integration tests validate API and adapter boundaries; frontend unit tests stay near components and hooks; E2E covers login, install, proxy, backup, and upgrade-critical flows.
5. Static product assets and locale files live in `console/public`; dynamic media and catalog inputs stay outside the frontend bundle.

### Development Workflow Integration

1. Frontend and backend run as separate workspaces during development, with same-origin behavior reproduced through proxying or dev-compose.
2. The frontend builds static assets; the backend builds the AppHub service image plus additive migration capabilities such as session, audit, or task support.
3. The structure supports one deployable product stack while still allowing independent frontend and backend CI validation.

## Validation Summary

The architecture is coherent on the current evolutionary backend path. The frontend stack has clear responsibility boundaries, AppHub remains the backend control core, and Portainer, Gitea, and Nginx Proxy Manager remain integrated services. The document now explicitly constrains Cockpit replacement, third-party workspace continuity, proxy separation, audit optimization, and direct upgrade.

Requirements coverage is complete at the architecture level. The major functional areas, the existing epics, and the newer PRD additions all have structural homes in the frontend, AppHub extensions, or integration boundaries. The main remaining implementation-time gaps are the detailed schema for task and audit events, retained metrics, and the direct-upgrade migration playbook.

Overall status is ready for epic and story decomposition on the preserved-backend path. Follow the documented module boundaries, keep task orchestration and permission checks as shared infrastructure, and prefer feature-first placement when code ownership is unclear.

## Next Steps

The architecture document is complete and now serves as the implementation source of truth for boundaries, technology choices, consistency rules, and target structure.

The next required planning step is `CE` (`bmad-create-epics-and-stories`). The strongest optional gate after that is `IR` (`bmad-check-implementation-readiness`). Before migration-sensitive implementation begins, produce the direct-upgrade migration playbook and gateway split implementation notes.