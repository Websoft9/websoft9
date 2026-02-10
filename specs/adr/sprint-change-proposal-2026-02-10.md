# Sprint Change Proposal - Epic 7 Dashboard Addition

**Date:** 2026-02-10  
**Project:** websoft9  
**Change Initiator:** Websoft9  
**Change Type:** Epic Addition & Restructuring

---

## 1. Issue Summary

### Problem Statement
The current implementation plan lacks a unified Dashboard framework, leading to fragmented UI development. Epic 5 and Epic 6 were originally planned as standalone Cockpit plugins, creating architectural inconsistency with the defined architecture.

### Context
**Discovery Point:** Strategic review of implementation plan against architecture document  
**Trigger:** Need to align implementation with architectural decision - "Custom Dashboard (React)" as defined in the Architecture document

### Evidence
- Architecture document explicitly defines "Custom Dashboard (React)" as the core UI layer
- PRD requirements (FR-1 through FR-8) all require unified dashboard interfaces
- Epic 5 (Store Plugin) and Epic 6 (Services Plugin) were designed as separate Cockpit plugins, conflicting with the unified dashboard architecture
- Current fragmented approach would result in inconsistent UX and duplicated infrastructure

---

## 2. Impact Analysis

### Epic Impact

**Added:**
- **Epic 7: Dashboard - Unified Frontend Framework** (NEW)
  - Priority: P0 (Foundation)
  - 10 Stories covering Vite + React setup, BaaS integration, cockpit.js integration, design system
  - Status: backlog

**Modified:**
- **Epic 5**: "Store Plugin - Decoupling from AppHub" → "Dashboard - Store Module"
  - Scope Change: From standalone Cockpit plugin to Dashboard module
  - Technology Change: Material-UI → shadcn/ui + Tailwind (Dashboard design system)
  - New Dependency: Now requires Epic 7 completion
  - Status: Remains in-progress (existing work can be migrated)

- **Epic 6**: "Services Plugin - Container Process Management" → "Dashboard - Services Module"  
  - Scope Change: From standalone Cockpit plugin to Dashboard module
  - Technology Change: PatternFly → shadcn/ui + Tailwind (Dashboard design system)
  - New Dependency: Now requires Epic 7 completion
  - Status: Remains backlog (no work started, clean transition)

**Epic Sequencing:**
```
Priority Order (revised):
Epic 1-4 (Infrastructure) → Epic 7 (Dashboard) → Epic 5 (Store) → Epic 6 (Services) → Epic 10 (i18n)
```

### Artifact Conflicts

**PRD:**
- ✅ No conflicts - Epic 7 enables implementation of all FR requirements
- ✅ Enhancement - Provides the core UI infrastructure implied by requirements
- ✅ NFR-1.7 satisfied - Vite + React optimized for < 3 second load time
- ✅ NFR-4 (Usability) improved - Unified dashboard provides better UX

**Architecture:**
- ✅ Perfect alignment - Epic 7 directly implements "Custom Dashboard (React)" from architecture diagram
- ✅ Technology stack matches: Vite + React + shadcn/ui + Tailwind CSS
- ✅ Integration points defined: BaaS Client + cockpit.js
- ⚠️ Minor documentation gap - Architecture should be supplemented with Dashboard module structure

**UX/UI:**
- ✅ No conflicts - Design system decisions already made (shadcn/ui + Tailwind)
- ℹ️ Epic 7 will establish layout patterns and component library

### Story Impact

**Epic 5 Stories (in-progress):**
- Stories 5.1, 5.2, 5.3, 5.7 can be migrated to Dashboard module context
- UI components need refactoring from Material-UI to shadcn/ui
- Business logic and data loading remain applicable
- Minimal code loss, primarily UI library swap

**Epic 6 Stories (backlog):**
- Clean slate - no work started
- Stories 6.1, 6.2 will be implemented directly in Dashboard context
- No rework required

**New Stories:**
- 10 new stories added under Epic 7 (7.1 through 7.10)
- All stories in backlog status

---

## 3. Recommended Approach

**Selected Path:** Direct Adjustment (Option 1)

### Rationale

1. **Architectural Alignment**
   - Epic 7 directly implements the documented architecture
   - Eliminates mismatch between architecture and implementation
   - Provides clean foundation for all UI features

2. **Minimal Disruption**
   - Epic 1-4 unaffected (infrastructure work continues)
   - Epic 5 in-progress work can be migrated (UI refactor only)
   - Epic 6 not started - clean transition to new approach
   - No rollback needed

3. **Technical Benefits**
   - Unified design system (shadcn/ui + Tailwind)
   - Shared state management via BaaS subscriptions
   - Single build pipeline and deployment
   - Consistent routing and navigation
   - Better code reuse across modules

4. **Risk Assessment**
   - **Effort:** Medium (Epic 7 = 10 stories, Epic 5 refactor = 2-3 stories worth)
   - **Risk:** Low (standard React/Vite setup, proven tech stack)
   - **Timeline Impact:** +2-3 weeks for Epic 7, offset by reduced Epic 5/6 complexity
   - **Team Impact:** Positive (cleaner architecture, less context switching)

### Alternatives Considered

- **Rollback Epic 5:** Not needed - migration is straightforward
- **MVP Scope Reduction:** Not applicable - Dashboard is core infrastructure, not optional feature
- **Keep Separate Plugins:** Rejected - conflicts with architecture, creates UX fragmentation

---

## 4. Detailed Change Proposals

### Change 1: Create Epic 7 Document

**File:** `specs/implementation-artifacts/epic7-dashboard.md` (NEW)

**Content:** Complete Epic 7 specification including:
- Objective: Build unified React Dashboard with BaaS + cockpit.js integration
- 10 Stories: Project setup, design system, routing, BaaS integration, cockpit.js, layouts, state mgmt, proxy config, error handling, responsive design
- Dependencies: Epic 1, 2 infrastructure; BaaS backend; Cockpit installed
- Technology: Vite + React 18 + TypeScript + shadcn/ui + Tailwind CSS

**Status:** ✅ Applied

---

### Change 2: Refactor Epic 5 Specification

**File:** `specs/implementation-artifacts/epic5-store.md` (MODIFIED)

**Changes:**
- Title: "Store Plugin - Decoupling from AppHub" → "Dashboard - Store Module"
- Objective: From standalone plugin → Dashboard module for app catalog
- Scope: Integration with Dashboard routing, BaaS deployment API, unified design system
- Dependencies: Added Epic 7 as prerequisite
- Technology: Material-UI → shadcn/ui + Tailwind CSS
- Location: `/plugins/store` → `dashboard/src/modules/store/`

**Migration Notes:**
- Existing UI components (5.1, 5.3, 5.7) need Material-UI → shadcn/ui refactor
- Media API integration (5.2) and business logic remain valid
- Store routing becomes `/store/*` within Dashboard

**Status:** ✅ Applied

---

### Change 3: Refactor Epic 6 Specification

**File:** `specs/implementation-artifacts/epic6-services.md` (MODIFIED)

**Changes:**
- Title: "Services Plugin - Container Process Management" → "Dashboard - Services Module"
- Objective: From standalone plugin → Dashboard module for service management
- Scope: Real-time status via BaaS subscriptions, integrated with Dashboard
- Dependencies: Added Epic 7 as prerequisite, leverage cockpit.js from Epic 7
- Technology: PatternFly → shadcn/ui + Tailwind CSS
- Location: `/plugins/services` → `dashboard/src/modules/services/`

**Migration Notes:**
- No existing work - clean implementation in Dashboard context
- Service routing becomes `/services/*` within Dashboard
- Leverages BaaS real-time subscriptions for status updates

**Status:** ✅ Applied

---

### Change 4: Update Sprint Status Tracker

**File:** `specs/implementation-artifacts/sprint-status.yaml` (MODIFIED)

**Changes:**
- Updated Epic 5 comment to reflect new title
- Added Epic 6 section with stories 6.1, 6.2
- Added Epic 7 section with stories 7.1-7.10 (all backlog)
- Added Epic 10 placeholder (i18n)

**New Epic Entries:**
```yaml
epic7: backlog
7.1-project-setup-build: backlog
7.2-design-system: backlog
7.3-routing-navigation: backlog
7.4-baas-integration: backlog
7.5-cockpit-integration: backlog
7.6-layout-components: backlog
7.7-state-management: backlog
7.8-reverse-proxy-config: backlog
7.9-error-handling: backlog
7.10-responsive-design: backlog
epic7-retrospective: optional

epic6: backlog
6.1-service-list-status: backlog
6.2-service-control: backlog
epic6-retrospective: optional

epic10: backlog
epic10-retrospective: optional
```

**Status:** ✅ Applied

---

## 5. Implementation Handoff

### Change Scope Classification

**Category:** Moderate

**Justification:**
- New epic addition (Epic 7)
- Scope modifications to two existing epics (5, 6)
- No fundamental product direction change
- Architecture alignment, not pivot
- Some in-progress work requires migration (Epic 5)

### Handoff Recipients

**Primary:** Scrum Master (Bob)
- Responsibilities:
  - Manage Epic 7 story creation workflow
  - Coordinate Epic 5 migration planning with dev team
  - Update sprint planning based on new epic sequence
  - Monitor Epic 7 → Epic 5/6 dependency chain

**Secondary:** Development Team (Amelia)
- Responsibilities:
  - Implement Epic 7 stories (Dashboard framework)
  - Refactor Epic 5 in-progress work to Dashboard module
  - Follow unified design system (shadcn/ui + Tailwind)

**Tertiary:** Product Owner / Architect (Winston)
- Responsibilities:
  - Review and approve any additional architecture documentation needs
  - Validate Dashboard module structure aligns with system design
  - Provide guidance on BaaS API contracts for Dashboard integration

### Success Criteria

**Epic 7 Completion Criteria:**
- [ ] Dashboard application builds and deploys via reverse proxy at `/`
- [ ] BaaS authentication and session management functional
- [ ] cockpit.js successfully connects (same-origin requirement met)
- [ ] Routing framework supports module registration (`/store/*`, `/services/*`)
- [ ] Design system documented and component library established
- [ ] Build time < 30s, load time < 3s

**Epic 5/6 Migration Criteria:**
- [ ] Store module integrated into Dashboard routing
- [ ] Services module integrated into Dashboard routing
- [ ] UI components follow unified design system
- [ ] BaaS API integration functional for both modules
- [ ] No regression in functionality from original plugin designs

### Timeline Impact

**Estimated Effort:**
- Epic 7: 3-4 weeks (10 stories, foundational work)
- Epic 5 migration: +1 week (UI refactoring)
- Epic 6: No change (not started)

**Net Timeline:** +3-4 weeks overall, but Epic 5/6 complexity reduced by ~1 week each due to shared infrastructure

---

## 6. Next Steps

### Immediate Actions (This Sprint)
1. ✅ Create Epic 7 documentation
2. ✅ Update Epic 5, 6 specifications
3. ✅ Update sprint-status.yaml
4. [ ] Archive this Sprint Change Proposal
5. [ ] Communicate changes to development team

### Next Sprint Actions
1. [ ] Begin Epic 7 Story 7.1 (Project Setup & Build Pipeline)
2. [ ] Define Dashboard module structure and conventions
3. [ ] Establish BaaS API contracts for Dashboard integration
4. [ ] Plan Epic 5 in-progress work migration strategy

### Review Checkpoints
- After Epic 7 Story 7.2 (Design System): Review component patterns with team
- After Epic 7 Story 7.5 (Cockpit.js): Validate same-origin reverse proxy setup
- After Epic 7 completion: Architecture review before Epic 5/6 begin

---

## 7. Approval Record

**Proposal Created:** 2026-02-10  
**Reviewed By:** Websoft9  
**Approved:** 2026-02-10  
**Status:** ✅ APPROVED - All changes applied

**Approver Comments:**
- Epic 7 addresses architectural gap
- Method: Incremental refinement (each proposal reviewed individually)
- All 4 change proposals approved without modification

---

## Appendix: Epic Priority Matrix

| Epic | Title | Status | Priority | Dependencies | Target Phase |
|------|-------|--------|----------|--------------|--------------|
| 1 | Infrastructure and Build | Backlog | P0 | None | Phase 4.1 |
| 2 | Configuration Management | Backlog | P0 | Epic 1 | Phase 4.2 |
| 3 | Cockpit Customization | In Progress | P1 | Epic 1, 2 | Phase 4.3 |
| 7 | **Dashboard Framework** | **Backlog** | **P0** | **Epic 1, 2** | **Phase 4.4** |
| 5 | Dashboard - Store Module | In Progress | P1 | Epic 7 | Phase 4.5 |
| 6 | Dashboard - Services Module | Backlog | P1 | Epic 7 | Phase 4.6 |
| 10 | Internationalization | Backlog | P2 | Epic 7 | Phase 4.7 |

**Critical Path:** Epic 1 → Epic 2 → Epic 7 → Epic 5/6
