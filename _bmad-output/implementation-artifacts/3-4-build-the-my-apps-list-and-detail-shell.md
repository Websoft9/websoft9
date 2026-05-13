# Story 3.4: Build the My Apps list and detail shell

## Status

done

## Story

As a user managing installed applications,
I want My Apps to provide a stable list and detail shell,
so that the old high-frequency management path moves into the new Websoft9 console without losing continuity.

## Acceptance Criteria

1. Given the user opens the My Apps page, when the page loads, then the UI shows installed application name, status, access entry, and basic actions, and the list structure remains recognizable to existing users.
2. Given the user enters an application detail page, when the page renders, then the page provides at least overview, access, runtime information, volumes or files, backup, and uninstall structure slots, and later lifecycle or operations work can mount onto that layout.

## Dependencies

- Story 3.3 already established App Store to My Apps handoff, installation tracking continuity, and the native My Apps list baseline.
- `GET /api/apps` and `GET /api/apps/{app_id}` already provide the nearest AppHub-backed inventory and detail contract available for the first native My Apps detail shell.
- `plugin-myapps` remains the UX or IA migration baseline for recognizable list and detail continuity.

## Previous Story Intelligence

- Story 3.3 already turned My Apps from a placeholder into a native list page with install-tracking continuity, but it did not yet create the stable detail route or detail-shell layout expected by old plugin users.
- The user explicitly asked that My Apps, install continuity, and later lifecycle work continue to reference `plugin-myapps` rather than diverging into an unrelated navigation model.
- The next architecture-safe step is to create a stable detail shell and recognizable list affordances without prematurely pulling lifecycle execution, backup workflows, or proxy management into the same story.

## Developer Context

- The primary current frontend owner is `console/src/features/my-apps/my-apps-page.tsx`.
- The new detail-shell owner is `console/src/features/my-apps/my-app-detail-page.tsx` plus `console/src/features/my-apps/use-my-app-detail.ts`.
- Routing continuity is owned by `console/src/app/router/index.tsx`.
- The legacy detail IA reference remains `pluings/plugin-myapps/src/pages/appdetail.js`, especially its tab structure for overview, access, runtime or containers, volumes, backup, and uninstall.

## Implementation Guardrails

- Keep recognizable My Apps continuity from the old plugin while staying inside the native React shell and AppHub-backed contracts.
- Do not pull lifecycle execution into this story; that belongs to Story 3.5.
- Do not expose broken detail routes for transient installing, error, or non-stable rows that AppHub cannot yet resolve through `GET /api/apps/{app_id}`.
- Use the detail shell as a stable mounting surface so later access, lifecycle, backup, and uninstall stories do not need to move the page structure again.

## Suggested File Targets

- `console/src/features/my-apps/my-apps-page.tsx`
- `console/src/features/my-apps/my-app-detail-page.tsx`
- `console/src/features/my-apps/use-my-app-detail.ts`
- `console/src/app/router/index.tsx`
- `console/src/shared/i18n/resources.ts`
- `pluings/plugin-myapps/src/pages/appdetail.js`

## Implementation Tasks

1. Keep the My Apps list recognizable while exposing access entry and stable basic actions. (AC: 1)
2. Introduce a native detail route under My Apps. (AC: 2)
3. Create a stable detail shell with overview, access, runtime, volumes/files, backup, and uninstall structure slots. (AC: 2)
4. Keep the implementation aligned with current AppHub detail contracts and avoid surfacing unsupported detail paths. (AC: 1, 2)

## Testing Requirements

- Validate the touched console slice with `npm run typecheck`.
- Validate the console bundle with `npm run build`.
- Verify My Apps list cards now expose access entry and stable drill-down actions for resolvable installed apps.
- Verify `/myapps/:appId` renders the native detail shell and section placeholders.

## Definition of Done

- My Apps list exposes name, status, access entry, and basic actions.
- The native shell has a stable `/myapps/:appId` detail route.
- The detail view includes overview, access, runtime, volumes/files, backup, and uninstall slots.
- The list and detail IA stay recognizable relative to the old plugin baseline.

## Source Notes

- Primary sources: `_bmad-output/planning-artifacts/epics.md` Epic 3 Story 3.4 and `_bmad-output/planning-artifacts/prd.md` FR-APP-003.
- Legacy migration references: `pluings/plugin-myapps/src/pages/myapps.js`, `pluings/plugin-myapps/src/pages/appdetail.js`.
- Current frontend baseline: `console/src/features/my-apps/my-apps-page.tsx` from Story 3.3.

## Tasks / Subtasks

- [x] Extend the My Apps list so it keeps recognizable management continuity. (AC: 1)
  - [x] Show name, status, access entry, and stable basic actions on list cards.
  - [x] Avoid offering unsupported detail drill-down for transient or unresolved rows.
- [x] Create the native detail route and shell. (AC: 2)
  - [x] Add `/myapps/:appId` to the console router.
  - [x] Load detail data through an AppHub-backed hook.
- [x] Provide the first stable detail-shell layout. (AC: 2)
  - [x] Add overview, access, runtime, volumes/files, backup, and uninstall slots.
  - [x] Keep later lifecycle and operations work attachable without reshaping the page again.

## Dev Notes

### Architecture Compliance

- The new detail shell stays inside the native console route tree and does not reintroduce Cockpit modal-driven detail ownership.
- AppHub detail reads remain the current source of truth for stable detail content while transient install or error continuity stays on the My Apps list.
- Lifecycle execution was intentionally deferred so Story 3.4 only establishes the stable shell, not the next action system.

### Validation Notes

- 2026-04-23: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `cd /workspace/websoft9/console && npm run build`
- 2026-05-13: `cd /workspace/websoft9/console && npm run typecheck`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- My Apps list cards now expose access-entry continuity and stable drill-down actions for resolvable installed applications.
- The native console now owns a stable `/myapps/:appId` detail route and detail-shell page.
- The detail shell already reserves overview, access, runtime, volumes/files, backup, and uninstall sections so later stories can add real behavior without moving the IA again.
- Detail entry is intentionally limited to stable official apps because the current AppHub detail endpoint does not yet resolve transient installing or error rows.
- My Apps now behaves more like an installed-application control plane: navigation copy is aligned to Applications, the list adds install-source filters and source badges, and the primary toolbar action sends users back to Install Apps for new deployments.

### File List

- console/src/app/router/index.tsx
- console/src/features/my-apps/my-app-detail-page.tsx
- console/src/features/my-apps/my-apps-page.tsx
- console/src/features/my-apps/use-my-app-detail.ts
- console/src/shared/i18n/resources.ts
- pluings/plugin-myapps/src/pages/appdetail.js

### Change Log

- 2026-04-23: Implemented the first native My Apps detail route and detail shell, and extended the My Apps list to meet the Story 3.4 acceptance baseline.
- 2026-05-13: Refined the My Apps list IA with install-source filtering, source badges, and an Add Application action that routes back to the App Store install-entry surface.