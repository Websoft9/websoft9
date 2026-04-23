# Story 3.5: Build lifecycle actions and the application detail header

## Status

done

## Story

As a day-to-day operator,
I want the application detail header to expose high-frequency lifecycle actions,
so that Websoft9 can take over the real application-management path instead of only showing application information.

## Acceptance Criteria

1. Given the user enters an application detail page, when the page renders, then the header exposes access, start, stop, restart, redeploy, and uninstall actions, and those actions share one consistent header-action model.
2. Given the user triggers any lifecycle action, when the backend accepts the request, then the platform executes it through unified APIs and task-capable contracts, and state changes flow back into the UI feedback chain.

## Dependencies

- Story 3.4 already established the native detail route and stable detail shell.
- AppHub lifecycle routes already exist for start, stop, restart, redeploy, and uninstall.
- Story 3.3 already established My Apps list invalidation and status refresh as the nearest current feedback chain.

## Previous Story Intelligence

- The old plugin kept high-frequency app-management actions directly in the detail header, so continuing that rhythm matters more than inventing a deeper action menu first.
- Story 3.4 intentionally deferred lifecycle execution and only reserved the detail shell, so Story 3.5 should fill that exact shell instead of reshaping the page again.
- The current backend is mixed-mode: start, stop, restart, and uninstall are synchronous acceptance endpoints, while redeploy already exposes a task-like streaming log pattern. The first native header implementation should reuse that split without pretending the platform already has one universal SSE task model.

## Developer Context

- Frontend detail owner: `console/src/features/my-apps/my-app-detail-page.tsx`.
- Current detail data owner: `console/src/features/my-apps/use-my-app-detail.ts`.
- AppHub lifecycle owners: `apphub/src/api/v1/routers/app.py` and `apphub/src/services/app_manager.py`.
- Legacy header rhythm reference: `pluings/plugin-myapps/src/pages/appdetail.js`.

## Implementation Guardrails

- Keep one shared header-action model instead of scattering lifecycle buttons across tabs.
- Reuse the current AppHub routes instead of adding frontend-side host command execution.
- Treat redeploy as the closest current task-flow baseline and keep its log feedback visible in the native UI.
- Keep uninstall confirmation explicit and support the existing purge-data flag.
- Do not expand into access/proxy editing, backup execution, or detailed terminal-style runtime diagnostics; those belong to later stories.

## Suggested File Targets

- `console/src/features/my-apps/my-app-detail-page.tsx`
- `console/src/shared/i18n/resources.ts`
- `apphub/src/api/v1/routers/app.py`
- `pluings/plugin-myapps/src/pages/appdetail.js`

## Implementation Tasks

1. Build one shared detail-header action model for access and lifecycle actions. (AC: 1)
2. Wire start, stop, restart, and uninstall to the existing AppHub APIs and refresh the My Apps feedback chain after acceptance. (AC: 2)
3. Reuse the current redeploy streaming contract inside a native dialog/log surface. (AC: 2)
4. Keep success or error feedback visible in the detail shell after each action. (AC: 2)

## Testing Requirements

- Validate the touched console slice with `npm run typecheck`.
- Validate the console bundle with `npm run build`.
- Verify the detail header exposes access, start, stop, restart, redeploy, and uninstall actions.
- Verify action completion or acceptance refreshes list/detail status feedback.

## Definition of Done

- The detail header exposes the required action set through one consistent action model.
- Start, stop, restart, redeploy, and uninstall all call unified backend routes.
- Redeploy shows task-like log feedback in the native UI.
- Action outcomes flow back into visible UI feedback and data refresh.

## Source Notes

- Primary sources: `_bmad-output/planning-artifacts/epics.md` Epic 3 Story 3.5 and `_bmad-output/planning-artifacts/prd.md` FR-APP-004.
- Legacy reference: `pluings/plugin-myapps/src/pages/appdetail.js`.
- Current native shell reference: `console/src/features/my-apps/my-app-detail-page.tsx` from Story 3.4.

## Tasks / Subtasks

- [x] Add one shared header-action model to the native detail page. (AC: 1)
  - [x] Expose access, start, stop, restart, redeploy, and uninstall actions in the header area.
  - [x] Keep action availability aligned with current app state where the current contract allows it.
- [x] Wire lifecycle actions to AppHub-backed routes. (AC: 2)
  - [x] Start, stop, and restart now call the current acceptance routes and refresh list/detail queries afterward.
  - [x] Uninstall now uses an explicit confirmation dialog with the existing purge-data flag.
- [x] Reuse current task-capable feedback for redeploy. (AC: 2)
  - [x] The native detail page now opens a redeploy dialog with pull-image toggle and streaming logs.
  - [x] Redeploy success or failure now reports back through native feedback plus data refresh.

## Dev Notes

### Architecture Compliance

- The detail header remains product-owned and React-native instead of delegating lifecycle control back to Cockpit-era modal logic.
- Start, stop, restart, and uninstall currently use acceptance-style AppHub endpoints; redeploy remains the closest task/log baseline already present in AppHub.
- The current implementation refreshes My Apps list/detail queries after action acceptance so UI state stays within the current product feedback chain.

### Validation Notes

- 2026-04-23: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `cd /workspace/websoft9/console && npm run build`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- The native My Apps detail header now owns one shared action model for access, start, stop, restart, redeploy, and uninstall.
- Start, stop, restart, and uninstall now call the current AppHub lifecycle routes and refresh My Apps list/detail feedback after acceptance.
- Redeploy now stays inside the native UI through a dialog with pull-image toggle and streamed log output.
- Success and error outcomes now surface through native snackbar feedback instead of leaving lifecycle actions silent.

### File List

- console/src/features/my-apps/my-app-detail-page.tsx
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/app.py
- pluings/plugin-myapps/src/pages/appdetail.js

### Change Log

- 2026-04-23: Implemented the first native lifecycle-action header on the My Apps detail page, including redeploy log feedback and uninstall confirmation.