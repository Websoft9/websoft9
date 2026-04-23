# Story 3.3: Build the installation task loop

## Status

done

## Story

As a user installing an application,
I want installation to produce explicit task feedback,
so that I can understand progress, failure causes, and what to do next.

## Acceptance Criteria

1. Given the user submits a valid installation request, when the backend accepts it, then Websoft9 creates an installation task through the unified API model, and the frontend does not execute host commands directly.
2. Given the installation task changes state, when the backend updates task status, then the UI shows queued, running, success, failure, or canceled states through one task-feedback model, and failure states include a summary and diagnostics entry.

## Dependencies

- Story 3.2 already establishes the detail-first App Store modal, backend-driven install-parameter rendering, and the current `/api/apps/install` submission surface.
- Epic 3 later depends on installation success feeding naturally into My Apps continuity.
- Architecture requires AppHub-centered task orchestration with REST reads/mutations plus SSE for progress updates as the target model.

## Previous Story Intelligence

- The user has already made two migration constraints explicit: the App Store must stay close to the old plugin mental model, and the upcoming installation plus My Apps path must reference `plugin-myapps` rather than inventing an unrelated workflow.
- Story 3.2 already preserves the old browse-detail-install rhythm in the App Store; Story 3.3 should preserve the old “install starts, then user naturally continues in My Apps” handoff rather than trapping all feedback inside the App Store modal.
- The current AppHub install endpoint still returns a plain success payload and starts installation in a background thread, so the next story is fundamentally about closing the feedback gap rather than reworking App Store parameter entry again.

## Developer Context

- The primary legacy migration reference is `pluings/plugin-myapps/src/pages/myapps.js`, which already models the current user expectation for installation continuity: installed-app polling, installing/error states, installing-log modal, and natural post-install tracking inside My Apps.
- The companion detail shell reference is `pluings/plugin-myapps/src/pages/appdetail.js`, which shows how the old system mixes lifecycle actions and progress-heavy operations into the My Apps detail path. Story 3.3 should learn from that continuity without carrying forward Cockpit-specific implementation patterns.
- Current backend install behavior lives in `apphub/src/api/v1/routers/app.py` and returns immediate success from `/api/apps/install` while delegating the actual install work to `AppManger().install_app(...)` in a background thread.
- Current installed-app reads already exist at `GET /api/apps` and `GET /api/apps/{app_id}`. The API baseline document notes that these endpoints currently merge Portainer state with in-memory installing/error state, which is the nearest existing bridge toward task feedback.
- Architecture explicitly sets the target direction: REST for commands and reads, SSE for task progress, WebSocket only for terminal transport, and AppHub as the unified orchestration layer.

## Implementation Guardrails

- Preserve the `plugin-myapps` continuity goal: after install submission, the user should be able to continue tracking the operation through My Apps rather than relying on App Store-only transient success toasts.
- Do not reintroduce Cockpit polling, `cockpit.spawn`, or frontend-executed host commands.
- Do not lock the implementation to the legacy plugin's exact polling mechanics; use the plugin as UX and information-architecture reference, but refactor toward the AppHub task-model target.
- Do not design the task loop as App Store-only state. The install result must be reusable by the future My Apps list/detail surfaces.
- Failure states must expose more than a boolean error. Preserve summary plus diagnostics/log-entry expectations.

## Suggested File Targets

- `console/src/features/app-store/app-store-page.tsx`
- `console/src/features/my-apps/` (new feature area expected)
- `console/src/shared/` or feature-local task hooks/stores if needed
- `console/src/shared/i18n/resources.ts`
- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- potential new AppHub task or status routes under `apphub/src/api/v1/routers/`
- `docs/api-contracts-apphub.md`

## Implementation Tasks

1. Define the installation-feedback contract that bridges App Store submission into reusable task/My Apps tracking. (AC: 1, 2)
2. Refactor install acceptance so the backend exposes a task-oriented response rather than only a fire-and-forget success message. (AC: 1)
3. Add frontend task feedback that can survive navigation away from the App Store and naturally hand off into My Apps. (AC: 2)
4. Expose failure summaries and diagnostics/log-entry surfaces in a product-owned way informed by the old `plugin-myapps` installing/error flow. (AC: 2)
5. Keep the resulting model reusable for later lifecycle actions, not only fresh installs. (AC: 2)

## Testing Requirements

- Validate the touched frontend slice with `npm run typecheck`.
- Validate the console bundle with `npm run build`.
- Add focused backend validation for any new task/status contract introduced around `/api/apps/install`.
- Verify an accepted installation can be observed after leaving the App Store surface.
- Verify failure states carry both a user-readable summary and a diagnostics/log path.

## Definition of Done

- Install submission returns or creates a reusable task-tracking identity/model.
- The frontend can show installation progress outside a single App Store modal lifecycle.
- Success naturally hands off into My Apps continuity.
- Failure states expose actionable summary and diagnostics/log context.
- The feedback model is aligned with the future lifecycle-action task loop rather than being a one-off install hack.

## Source Notes

- Primary sources: `_bmad-output/planning-artifacts/epics.md` Epic 3 Story 3.3, `_bmad-output/planning-artifacts/prd.md` FR-APP-002 and FR-APP-004, `_bmad-output/planning-artifacts/architecture.md` task-model and SSE decisions.
- Legacy migration references: `pluings/plugin-myapps/src/pages/myapps.js`, `pluings/plugin-myapps/src/pages/appdetail.js`.
- Backend contract references: `apphub/src/api/v1/routers/app.py`, `docs/api-contracts-apphub.md`.
- Plugin baseline context: `docs/ui-plugin-baseline.md`.

## Tasks / Subtasks

- [x] Analyze the current install acceptance and status gap between App Store and My Apps continuity. (AC: 1, 2)
  - [x] Document what `/api/apps/install` returns today versus the target task-oriented contract.
  - [x] Identify what current `/api/apps` and `/api/apps/{app_id}` state can already support.
- [x] Define the first reusable install-task contract in AppHub. (AC: 1)
  - [x] The first slice now returns a resolved `app_id` plus `tracking_id` accepted contract.
  - [x] The contract remains compatible with later SSE-based task updates because My Apps consumes the same tracking identity through `/api/apps`.
- [x] Build frontend task feedback and My Apps handoff continuity. (AC: 2)
  - [x] App Store install submission now navigates into My Apps instead of ending on a transient success-only toast.
  - [x] My Apps now polls `/api/apps`, shows installing or error states, and exposes installation logs or error details.
- [x] Preserve legacy continuity without carrying forward legacy implementation coupling. (AC: 1, 2)
  - [x] `plugin-myapps` remains the UX/IA baseline for installing, failed, and log-oriented states.
  - [x] The implementation stays inside the React shell plus AppHub contracts and does not reintroduce Cockpit runtime dependencies or host-command execution.

## Dev Notes

### Architecture Compliance

- Long-running operational feedback must move toward the architecture target: AppHub-centered task orchestration, REST for command/read, SSE for progress updates.
- The new frontend should use TanStack Query plus feature-local hooks/state rather than global ad hoc polling logic copied from the legacy plugin.
- My Apps continuity is a first-class product spine, so install feedback should be designed to feed My Apps directly rather than remain App Store-local.

### API / Data Contract Notes

- `/api/apps/install` currently returns a generic success payload and starts work asynchronously in a background thread; this is not yet a true task API.
- `/api/apps` already aggregates installed apps plus in-memory installing/error state and is therefore the nearest current compatibility layer for transitional status feedback.
- `/api/apps/{app_id}/redeploy` already streams logs and is the closest existing backend pattern to future task/log feedback.

### Legacy Plugin Migration Notes

- `pluings/plugin-myapps/src/pages/myapps.js` provides the clearest current baseline for install continuity: status ordering, explicit installing/error states, install-log modal, refresh behavior, and natural “track it in My Apps” workflow.
- `pluings/plugin-myapps/src/pages/appdetail.js` shows how progress-heavy operations eventually converge into the My Apps detail surface.
- Use these files as behavior and information-architecture references, not as implementation patterns. Their Cockpit command execution, config bootstrapping, and ad hoc polling should be refactored away.

### Project Structure Notes

- Current App Store owner: `console/src/features/app-store/`.
- Expected upcoming owner for continuity: `console/src/features/my-apps/`.
- Backend owner: `apphub/src/api/v1/routers/app.py`, `apphub/src/services/app_manager.py`.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- `/api/apps/install` now returns a typed acceptance contract with resolved `app_id` and `tracking_id`, instead of only a generic success message.
- `/api/apps` transient installing and error rows now expose `tracking_id`, which lets the product shell hand off from App Store submission into My Apps tracking without inventing a second state model.
- `console/src/features/my-apps/` now owns the first native My Apps continuity slice: auto-refreshing inventory, status filters, installing or error cards, and install-log or error-detail dialogs.
- App Store installation success now navigates directly to My Apps with tracking context, preserving the old plugin expectation that install progress continues there rather than staying trapped in the store modal.
- The current implementation is intentionally transitional: it reuses AppHub in-memory install state and `/api/apps` aggregation now, while keeping room for later SSE-backed task orchestration in follow-on stories.

### File List

- apphub/src/api/v1/routers/app.py
- apphub/src/schemas/appInstallAcceptedResponse.py
- apphub/src/schemas/appResponse.py
- apphub/src/services/app_manager.py
- apphub/src/services/app_status.py
- console/src/app/router/index.tsx
- console/src/features/app-store/app-store-page.tsx
- console/src/features/my-apps/my-apps-page.tsx
- console/src/features/my-apps/use-my-apps.ts
- console/src/shared/i18n/resources.ts
- docs/api-contracts-apphub.md
- pluings/plugin-myapps/src/pages/myapps.js
- pluings/plugin-myapps/src/pages/appdetail.js
- docs/ui-plugin-baseline.md

### Change Log

- 2026-04-23: Created Story 3.3 with explicit `plugin-myapps` migration references for installation feedback, My Apps handoff, and later lifecycle-task continuity.
- 2026-04-23: Implemented the first install-tracking contract, native My Apps continuity page, and App Store-to-My Apps handoff on top of the existing AppHub in-memory install state.