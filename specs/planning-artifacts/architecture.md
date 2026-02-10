---
stepsCompleted: [1, 2, 3, 4, 5, 7, 8]
inputDocuments:
  - specs/planning-artifacts/product-brief.md
  - specs/planning-artifacts/prd.md
workflowType: 'architecture'
project_name: 'websoft9'
user_name: 'Websoft9'
date: '2026-02-04'
lastStep: 8
status: 'complete'
completedAt: '2026-02-05'
lastUpdated: '2026-02-10'
---

# Architecture Decision Document - websoft9

## Architecture Overview

**BaaS + Cockpit-Bridge Hybrid**: Custom React Dashboard backed by a self-hosted BaaS for data/auth/logic, combined with Cockpit (cockpit-ws + cockpit-bridge) for secure Linux system operations.

```
┌──────────────────────────────────────────┐
│           Custom Dashboard (React)        │
│  ┌─────────────────┐  ┌────────────────┐ │
│  │ BaaS Client      │  │ cockpit.js     │ │
│  │ (data, auth,     │  │ (spawn, file,  │ │
│  │  subscriptions)  │  │  dbus)         │ │
│  └────────┬────────┘  └───────┬────────┘ │
└───────────┼────────────────────┼──────────┘
            │                    │
            ▼ Same Origin (※)   ▼
┌───────────────────────────────────────────┐
│         Reverse Proxy (critical)          │
│  https://example.com                      │
│  ├── /              → Dashboard           │
│  ├── /cockpit/      → cockpit-ws          │
│  └── /baas/         → BaaS Backend        │
└──────────┬────────────────────┬───────────┘
           ▼                    ▼
┌───────────────────┐  ┌──────────────────┐
│ BaaS Backend      │  │ cockpit-ws       │
│ (self-hosted)     │  │ + cockpit-bridge │
│                   │  │                  │
│ • Auth (users)    │  │ • spawn()        │
│ • Database        │  │ • file read/write│
│ • Server functions│  │ • dbus (systemd) │
│ • Realtime sync   │  │ • Polkit security│
│ • Scheduler       │  │                  │
└───────────────────┘  └──────────────────┘

※ cockpit.js uses window.location.origin for WebSocket.
  Dashboard and cockpit-ws MUST share the same origin.
  Reverse proxy is the only supported way to achieve this.
```

## Core Decisions

### Architecture Approach

**Integration-Based**: Integrate existing mature open-source components rather than building from scratch. The platform's own code focuses on Dashboard UI and BaaS server functions — all infrastructure capabilities (reverse proxy, Git repository, container runtime) come from proven tools.

### Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Frontend** | Vite + React + React Router | SPA, pure static build, no Node.js runtime needed |
| **UI** | shadcn/ui + Tailwind CSS | Code-ownership components, zero dependency lock-in, CSS variable theming |
| **Backend** | Self-hosted BaaS | Server functions, built-in auth, reactive database, scheduler |
| **System Access** | Cockpit (cockpit-ws + cockpit-bridge) | Secure host command execution via WebSocket |
| **Container Runtime** | docker-compose | Single-server optimized, no K8s overhead |
| **Reverse Proxy** | Self-hosted reverse proxy | Application routing, SSL termination, API gateway |
| **Git Repository** | Self-hosted Git server | GitOps backend, compose file storage |

### Infrastructure Components

The platform requires 4 infrastructure services. Specific product choices are implementation details, not architectural decisions:

- **BaaS**: Handles user auth, database, server-side logic, realtime subscriptions
- **Reverse Proxy** (critical): Application routing + SSL + **same-origin bridge** between Dashboard and cockpit-ws. cockpit.js requires the Dashboard page and cockpit-ws to share the same origin — reverse proxy is the only way to achieve this without running Dashboard inside Cockpit
- **Git Repository**: Stores docker-compose files for GitOps deployments
- **Cockpit**: The only component specified by name — provides cockpit-ws (WebSocket transport) and cockpit-bridge (host-side command execution)

## Role Division

| Concern | Owner | Rationale |
|---------|-------|-----------|
| User authentication | BaaS Auth | Modern auth flows (OAuth, email, custom) |
| Business data & API | BaaS server functions | Type-safe, reactive queries |
| Task orchestration | BaaS (mutations + scheduler) | Transactional state + async scheduling |
| System commands (docker, systemctl) | cockpit-bridge via cockpit.js | Secure, audited, polkit-controlled execution on host |
| File read/write on host | cockpit-bridge via cockpit.js | Atomic file operations with permission control |
| Realtime UI updates | BaaS subscriptions | Deployment status, app state changes pushed automatically |

## Cockpit's Role

Cockpit is **not** used as a UI shell or plugin platform. Only two components are retained:

- **cockpit-ws**: WebSocket server providing authenticated transport
- **cockpit-bridge**: Host-side process executing commands with Linux permission model

The Dashboard loads `cockpit.js` from `/cockpit/@localhost/base1/cockpit.js` to access: `cockpit.spawn()`, `cockpit.file()`, `cockpit.dbus()`, `cockpit.http()`.

**Why Cockpit specifically**: cockpit-bridge is the only lightweight, battle-tested solution that exposes secure, polkit-controlled Linux system operations over WebSocket. No comparable alternative exists.

## Authentication

BaaS owns the user session. Cockpit uses a fixed system user for bridge access.

1. User authenticates via BaaS Auth → session
2. Dashboard verifies session before enabling any cockpit.js operations
3. cockpit-ws authenticates with a dedicated system user (e.g. `websoft9`)
4. Reverse proxy enforces: cockpit-ws only accessible from Dashboard origin

## Key Flows

### Application Deployment

1. User clicks "Deploy App" in Dashboard
2. Dashboard calls BaaS mutation → creates task record (status: pending)
3. BaaS schedules an action → task status: running (frontend auto-updates via subscription)
4. Dashboard uses `cockpit.spawn()` to execute `docker compose up -d` on host
5. Stream output back to Dashboard via cockpit.js stream handler
6. On completion, Dashboard calls BaaS mutation → task status: complete

### GitOps

docker-compose files stored in Git repository. BaaS server functions fetch on-demand during deployment.

## Container Topology

```
websoft9-baas           # BaaS backend + admin dashboard
websoft9-cockpit        # cockpit-ws only, bridge access
websoft9-proxy          # Reverse proxy (SSL, routing, API gateway)
websoft9-git            # Git server (GitOps, compose file storage)
app-containers          # User-deployed applications
```

## Constraints

- **Same-origin requirement** (hard constraint): cockpit.js initiates WebSocket to `window.location.origin`. Dashboard and cockpit-ws must be served under the same origin via reverse proxy. Without this, cockpit.js will not connect.
- cockpit-bridge requires cockpit packages installed on host (or in a privileged container)
- Single-server only: no distributed systems, vertical scaling only
- docker-compose for orchestration: simple but no horizontal scaling
