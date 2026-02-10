# Epic 5: Dashboard - Store Module

## Overview

**Objective**: Implement application store module within Dashboard - browse, search, and deploy applications from 300+ app catalog

**Business Value**: Unified app discovery and deployment experience integrated into main Dashboard UI

**Priority**: P1

**Status**: In Progress

## Scope

Build Store module as part of Dashboard (Epic 7 framework):
- Application catalog browsing and search
- Category-based filtering and navigation
- Application detail views with metadata
- One-click deployment integration (calls BaaS deployment API)
- Media data integration from `/data/dev/websoft9/media`

## Success Criteria

- Store module integrates seamlessly with Dashboard routing
- Application catalog displays with categories and search
- Detail modal shows app metadata (description, ports, volumes)
- Deploy button triggers BaaS deployment workflow
- UI follows Dashboard design system (shadcn/ui + Tailwind)

## Stories

- [x] 5.1: Core UI Components & Data Loading
- [x] 5.2: Media API Integration
- [x] 5.3: Category Management
- [ ] 5.4: Build & Deployment Configuration
- [x] 5.5: Internationalization (i18n) Support
- [ ] 5.6: Application Detail Modal
- [ ] 5.7: Search Autocomplete

## Dependencies

- Prerequisites: 
  - Epic 7 (Dashboard framework) must be completed first
  - Media data available at `/data/dev/websoft9/media`
  - BaaS deployment API available
- Downstream: None

## Technical Notes

- **Technology**: React components within Dashboard framework
  - UI: shadcn/ui + Tailwind CSS (from Epic 7)
  - Routing: TanStack Router (`/store/*` routes)
  - Data: TanStack Query for API calls and caching
  - i18n: react-i18next for translations
- **Location**: `dashboard/src/routes/_app/_auth/store/` (TanStack Router file-based structure)
- **Data Source**: `/data/dev/websoft9/media` (loaded via BaaS API)
- **Integration**: 
  - BaaS deployment API for app installation
  - Shared Dashboard state (theme, locale from React Context)
  - TanStack Query for catalog data caching
