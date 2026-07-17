# Architecture

## Overview

Websoft9 uses a **single-container integrated control plane** architecture. Unlike traditional multi-container PaaS platforms, all core services run inside one Docker container, orchestrated by supervisord.

```
┌──────────────────────────────────────────────────┐
│                  Websoft9 Container               │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Console  │  │  AppHub   │  │  Nginx Proxy  │  │
│  │  (React)  │  │ (FastAPI) │  │    Manager    │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │              │                │           │
│  ┌────┴─────┐  ┌────┴─────┐  ┌───────┴───────┐  │
│  │  Gitea   │  │ Portainer │  │  supervisord  │  │
│  │ (Git)    │  │(Container)│  │  (init/pid1)  │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                   │
└──────────────────────┬────────────────────────────┘
                       │
              ┌────────┴────────┐
              │  Docker Socket  │
              │  Data Volumes   │
              │  Host Network   │
              └─────────────────┘
```

## Core Components

### 1. Console (Frontend)
- **Tech**: React 19 + TypeScript + Vite + MUI
- **Role**: Web-based management UI served at port `9000`
- **Features**: Application catalog, My Apps, file manager, terminal, settings, services logs

### 2. AppHub (Backend API)
- **Tech**: Python 3.11 + FastAPI
- **Role**: Business logic API for apps, auth, proxy, backup, files, settings
- **Auth**: API key + internal gateway trust key
- **Base Path**: `/api`

### 3. Gitea
- **Tech**: Go, embedded within the product container
- **Role**: Git repository hosting and embedded workspace for code editing
- **Port**: Internal only

### 4. Portainer
- **Tech**: Go + React, embedded within the product container
- **Role**: Docker container and stack lifecycle management
- **Port**: Internal only

### 5. Nginx Proxy Manager (NPM)
- **Tech**: Node.js, embedded within the product container
- **Role**: Reverse proxy, domain binding, SSL certificate management (Let's Encrypt)
- **Port**: 80, 443 (host-bound)

## Data Flow

```
User Browser → :9000 (Console) → /api/* (AppHub)
                                   ├→ Portainer API (container ops)
                                   ├→ NPM API (proxy/SSL)
                                   ├→ Gitea API (git repos)
                                   └→ Docker socket (host ops)
```

## Host Dependencies

- **Docker Engine** (required) — container runtime
- **Docker Socket** (`/var/run/docker.sock`) — mounted for container management
- **Data Root** (`/opt/websoft9/data`) — persistent data, bind-mounted at same path inside container
- **Ports**: 80, 443, 9000

## Key Design Decisions

1. **Single container** — simplifies deployment, upgrade, and migration compared to multi-container PaaS
2. **Same-path volume binding** — ensures Portainer-generated compose paths resolve identically on host and container
3. **No Kubernetes dependency** — designed for single-server deployments; microservices on one machine
4. **Integrated third-party components** — Gitea, Portainer, NPM are embedded rather than reinvented
