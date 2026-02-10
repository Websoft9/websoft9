# Epic 6: Dashboard - Services Module

## Overview

**Objective**: Implement services management module within Dashboard - monitor and control application services and containers

**Business Value**: Unified service management experience with real-time status updates and control operations

**Priority**: P1

**Status**: Not Started

## Scope

Build Services module as part of Dashboard (Epic 7 framework):
- List all deployed applications and their services
- Display real-time container/service status (via BaaS subscriptions)
- Start/stop/restart operations for services
- View service logs in real-time
- Resource usage monitoring per service

## Success Criteria

- Services module integrates seamlessly with Dashboard routing
- Real-time status updates via BaaS subscriptions
- Service control operations (start/stop/restart) work reliably
- Logs display in real-time with filtering
- UI follows Dashboard design system (shadcn/ui + Tailwind)

## Stories

- [ ] 6.1: Service List & Status Display
- [ ] 6.2: Service Control Operations (Start/Stop/Restart)

## Dependencies

- Prerequisites: 
  - Epic 7 (Dashboard framework) must be completed first
  - BaaS service management APIs available
  - cockpit.js integration for system operations (from Epic 7)
- Downstream: None

## Technical Notes

- **Technology**: React components within Dashboard framework
  - UI: shadcn/ui + Tailwind CSS (from Epic 7)
  - Routing: TanStack Router (`/services/*` routes)
  - Data: TanStack Query + BaaS subscriptions for real-time updates
  - i18n: react-i18next for translations
- **Location**: `dashboard/src/routes/_app/_auth/services/` (TanStack Router file-based structure)
- **Integration**: 
  - BaaS API for service list, status, and operations
  - BaaS subscriptions for real-time status updates
  - cockpit.js for docker/systemctl system operations (from Epic 7.8)
  - TanStack Query for data fetching and optimistic updates
  - Shared Dashboard state (theme, locale from React Context)
