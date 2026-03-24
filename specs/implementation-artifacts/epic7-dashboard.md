# Epic 7: Dashboard - Unified Frontend Framework

## Overview

**Objective**: Build the core Dashboard application - unified React-based frontend framework integrating BaaS backend and Cockpit.js for system operations

**Business Value**: Central user interface for all websoft9 features, eliminating fragmented UIs and providing cohesive user experience

**Priority**: P0 (Foundation for Epic 5, 6)

**Status**: Not Started

## Scope

Implement the "Custom Dashboard (React)" from architecture diagram:
- Vite + React 18 + TypeScript SPA foundation
- **TanStack Router** for file-based routing
- **shadcn/ui + Tailwind CSS** design system with **Dark/Light mode** support
- **react-i18next** for internationalization
- State Management:
  - **TanStack Query** for server state (BaaS API, data fetching, caching)
  - **React Context** for client state (theme, locale, user session, UI state)
- BaaS client integration (auth, database, subscriptions)
- cockpit.js integration for system operations
- Reverse proxy integration (same-origin requirement)

## Success Criteria

- Dashboard loads in < 3 seconds (NFR-1.7)
- BaaS authentication and session management working
- cockpit.js successfully connects via same-origin reverse proxy
- Responsive layout (1024px+ tablet support)
- Modular architecture ready for Store/Services modules
- Build pipeline produces optimized static assets

## Stories

- [ ] 7.1: Project Setup & Build Pipeline (Vite, React, TypeScript, linting)
- [ ] 7.2: TanStack Router Setup (file-based routing, route tree)
- [ ] 7.3: Design System Foundation (shadcn/ui, Tailwind, Dark/Light theme)
- [ ] 7.4: i18n Setup (react-i18next, language detection, translation structure)
- [ ] 7.5: State Management Architecture (TanStack Query + React Context)
- [ ] 7.6: Layout Components (Header, Sidebar, Content Area, theme/locale switchers)
- [ ] 7.7: BaaS Client Integration (auth, session, API client, TanStack Query hooks)
- [ ] 7.8: Cockpit.js Integration & System Operations Bridge
- [ ] 7.9: Error Handling, Loading States & Suspense Boundaries
- [ ] 7.10: Responsive Design & Mobile Optimization (1024px+ tablet support)

## Dependencies

- Prerequisites: 
  - Epic 1 (Infrastructure) - Docker, build tools
  - Epic 2 (Configuration) - Service configuration
  - BaaS backend deployed and accessible
  - Cockpit installed and cockpit-ws running
  - Reverse proxy configured
- Downstream: 
  - Epic 5 (Store Module) depends on Epic 7 framework
  - Epic 6 (Services Module) depends on Epic 7 framework

## Technical Notes

### Core Stack
- **Build Tool**: Vite 5+
- **Framework**: React 18 + TypeScript 5+
- **Routing**: TanStack Router (file-based routing)
- **UI Library**: shadcn/ui + Tailwind CSS + CSS variables for theming
- **Theme**: Dark/Light mode with system preference detection
- **i18n**: react-i18next + i18next-browser-languagedetector

### State Management Strategy
- **Server State**: TanStack Query (formerly React Query)
  - All BaaS API calls
  - Data fetching, caching, synchronization
  - Optimistic updates for mutations
  - Real-time subscriptions integration
- **Client State**: React Context API
  - Theme preference (dark/light)
  - Locale selection (en/zh/etc)
  - User session/auth state
  - UI state (sidebar collapsed, etc)

### Backend Integration
- **BaaS**: Auth, DB queries, server functions, real-time subscriptions
- **System Access**: cockpit.js (spawn, file, dbus APIs)
- **Build Output**: Static files served by reverse proxy at `/dashboard`
- **Same-origin requirement**: Dashboard + cockpit-ws + BaaS must share origin via reverse proxy
