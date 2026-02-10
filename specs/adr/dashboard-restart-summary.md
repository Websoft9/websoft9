# Dashboard Restart - Change Summary

**Date**: 2026-02-10  
**Type**: Strategic Direction Change  
**Impact**: Epic 7, Epic 5, Epic 6

---

## What Changed

### 🗑️ Removed
- **Deleted**: Entire `dashboard/` directory (Convex SaaS codebase)
- **Reason**: Convex-specific patterns incompatible with websoft9 BaaS architecture

### ✅ Decision
- **Start fresh**: Build Dashboard from scratch following Epic 7 stories
- **Approach**: Story-by-story implementation with clear technical decisions

---

## Updated Epic Documentation

### Epic 7: Dashboard - Unified Frontend Framework

#### Clarified Technology Stack
1. **Routing**: ✅ **TanStack Router** (file-based routing)
   - Type-safe routing
   - File-based structure matches our needs

2. **Theme Support**: ✅ **Dark/Light mode**
   - System preference detection
   - Manual toggle
   - CSS variables for theming

3. **Internationalization**: ✅ **react-i18next**
   - Browser language detector
   - English + Chinese support
   - Extensible translation structure

4. **State Management**: ✅ **Hybrid approach**
   - **TanStack Query** → Server state (BaaS API, caching, subscriptions)
   - **React Context** → Client state (theme, locale, user session, UI state)
   - **Rationale**: Best tool for each type of state, no unnecessary complexity

#### Updated Stories (7.1 - 7.10)
```
7.1: Project Setup & Build Pipeline (Vite, React, TypeScript, linting)
7.2: TanStack Router Setup (file-based routing, route tree)
7.3: Design System Foundation (shadcn/ui, Tailwind, Dark/Light theme)
7.4: i18n Setup (react-i18next, language detection, translation structure)
7.5: State Management Architecture (TanStack Query + React Context)
7.6: Layout Components (Header, Sidebar, Content Area, theme/locale switchers)
7.7: BaaS Client Integration (auth, session, API client, TanStack Query hooks)
7.8: Cockpit.js Integration & System Operations Bridge
7.9: Error Handling, Loading States & Suspense Boundaries
7.10: Responsive Design & Mobile Optimization (1024px+ tablet support)
```

### Epic 5: Store Module
- **Updated**: Technology stack references
- **Location**: `dashboard/src/routes/_app/_auth/store/` (TanStack Router structure)
- **Integration**: TanStack Query for catalog caching, react-i18next for translations

### Epic 6: Services Module
- **Updated**: Technology stack references
- **Location**: `dashboard/src/routes/_app/_auth/services/` (TanStack Router structure)
- **Integration**: TanStack Query + BaaS subscriptions for real-time updates

---

## New Documentation

### Created: `tech-stack-decisions.md`
- Comprehensive technology stack rationale
- State management decision record (TanStack Query + React Context)
- File structure guidelines
- Migration decision justification

### Updated: `sprint-status.yaml`
- Renamed story keys to match new Epic 7 structure
- Added descriptive comments for each story

---

## Why This Approach?

### ❌ Problems with Convex SaaS Adaptation
1. **Auth incompatibility**: Resend OTP + GitHub OAuth don't match websoft9 auth
2. **Backend coupling**: Convex-specific queries/mutations patterns
3. **Unnecessary features**: Stripe billing, checkout flows, email verification
4. **Cleanup overhead**: More work to remove unwanted features than build fresh

### ✅ Benefits of Starting Fresh
1. **Clean architecture**: Build exactly what Epic 7 stories define
2. **No technical debt**: No legacy patterns or unused code
3. **Clear learning path**: Each story teaches one concept
4. **Better documentation**: Implementation matches documentation
5. **Websoft9-native**: BaaS + cockpit.js integration from start

---

## Learnings Kept from Convex SaaS

Even though we're not adapting the code, we learned valuable patterns:

1. ✅ **TanStack Router** file-based routing structure
2. ✅ **shadcn/ui** component organization
3. ✅ **Dark/light theme** implementation patterns
4. ✅ **i18next** configuration approach
5. ✅ **TanStack Query** for server state management

---

## Next Steps

1. **Story 7.1**: Initialize fresh `dashboard/` project
   ```bash
   npm create vite@latest dashboard -- --template react-ts
   cd dashboard
   npm install
   ```

2. **Story 7.2**: Install and configure TanStack Router
   ```bash
   npm install @tanstack/react-router
   npm install -D @tanstack/router-vite-plugin
   ```

3. **Story 7.3**: Setup shadcn/ui + Tailwind CSS
   ```bash
   npx shadcn-ui@latest init
   ```

4. **Story 7.4**: Configure react-i18next
   ```bash
   npm install i18next react-i18next i18next-browser-languagedetector
   ```

5. **Story 7.5**: Install TanStack Query + setup Context
   ```bash
   npm install @tanstack/react-query
   ```

---

## Files Modified

- ✅ `specs/implementation-artifacts/epic7-dashboard.md` (technology stack clarified)
- ✅ `specs/implementation-artifacts/epic5-store.md` (tech stack references updated)
- ✅ `specs/implementation-artifacts/epic6-services.md` (tech stack references updated)
- ✅ `specs/implementation-artifacts/sprint-status.yaml` (story keys renamed)
- ✅ `specs/planning-artifacts/tech-stack-decisions.md` (created - ADR document)
- ✅ `specs/planning-artifacts/dashboard-restart-summary.md` (this file)

---

## Questions Answered

### Q: Why TanStack Router over React Router?
**A**: Better TypeScript support, file-based routing simplifies organization, matches our structure needs.

### Q: Why both TanStack Query AND React Context?
**A**: Different purposes:
- **TanStack Query** = Server state (API, caching, sync) - complex problem needs specialized tool
- **React Context** = Client state (theme, locale, UI) - simple problem, native solution sufficient

### Q: Why not use Redux/Zustand/Recoil?
**A**: Unnecessary complexity. TanStack Query handles server state better than any global store. React Context sufficient for our client state needs.

### Q: Will we reuse ANY Convex SaaS code?
**A**: No code, but we will follow similar patterns for routing, theming, and UI components.

---

**Status**: ✅ Epic 7 specifications updated, ready to begin Story 7.1
