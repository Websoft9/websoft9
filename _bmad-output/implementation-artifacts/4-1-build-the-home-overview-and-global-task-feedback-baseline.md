---
title: 'Story 4.1: Build the home overview and global task-feedback baseline'
type: 'feature'
created: '2026-05-07'
status: 'done'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The top-level `dashboard` route still renders a shell placeholder. Operators can enter App Store, My Apps, gateway, repository, containers, files, and other modules, but they still do not land on a product-owned overview that answers the first operational questions after sign-in: whether Websoft9 itself is healthy, whether application state needs attention, and which action should happen next. In parallel, long-running work across install, proxy, backup, upgrade, and future privileged modules still lacks a product-level shared task-feedback surface.

**Solution:** Replace the placeholder `dashboard` route with a product-native home overview page. The first version should focus on product status, app-state summary, recent task feedback, alert-style reminders, and high-frequency entry points. It should introduce a reusable home-page task timeline baseline rather than a full standalone task center. The page should stay clearly separate from diagnostics: `dashboard` owns overview and navigation; `services` and `logs` continue to own deeper troubleshooting.

## Boundaries & Constraints

**Always:** Keep the overview page centered on Websoft9 product status rather than host-resource monitoring; reuse the current shell route, navigation position, and product-auth shell boundary; keep AppHub as the only public API layer; prefer additive AppHub overview and task-summary contracts over cross-route frontend stitching; keep bilingual resources; design the task-feedback model so later install, backup, upgrade, and restore flows can plug into the same summary surface without redefining status semantics.

**Ask First:** Turning the first version into a full observability dashboard; adding generic host CPU, memory, network, firewall, or partition management as the dominant content; introducing a brand-new event bus, metrics store, or always-on worker framework; exposing raw internal task payloads, stack traces, or sensitive config values directly on the home page; rebuilding a complete cross-module notifications center instead of the baseline task-feedback strip or timeline required here.

**Never:** Regress the home page into a Cockpit-style host console; make `dashboard` a dumping ground for every module summary; force operators into services/logs detail just to understand headline state; bypass the existing shared shell or product-auth boundary; hard-code task logic into only app-install flows so later modules cannot reuse it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|----------------|---------------------------|----------------|
| LOAD_HOME_PAGE | Authenticated operator opens `/dashboard` | Page renders a product-native overview instead of `ShellPlaceholderPage`, showing product summary, app summary, task summary, and shortcut entries | Partial sections may degrade independently; the page must still render a stable shell and fallback blocks |
| LOAD_OVERVIEW_SUMMARY | App counts, service summary, version/upgrade state, and recent-task data are available | Overview cards show concise counts, state labels, and links to the owning modules | Missing one data source must not collapse unrelated cards |
| NO_RECENT_TASKS | No shared tasks are available yet | The task area shows an intentional empty state that explains no recent activity has been recorded | Empty state must not read like an error |
| PARTIAL_TASK_SOURCES | Some task domains expose summary events while others do not yet | Timeline or list renders available tasks and keeps clear placeholders or omission rules for unsupported domains | Unsupported task domains must degrade silently rather than appearing as failed tasks |
| APPS_NEED_ATTENTION | Installed-app summary includes abnormal or installing apps | Home page highlights attention-needed state and links directly to `myapps` | Summary remains high-level and does not duplicate the full My Apps table |
| SERVICE_DEGRADED | Core-service summary reports degraded bundled services | Home page surfaces the risk in a compact status card and links to `services` or `logs` | It must not expand into service-level diagnostics on the home page |
| SHORTCUT_ENTRY | User clicks App Store, My Apps, Settings, Backup, Logs, or Services shortcut | The page routes into the existing module entry without replacing those modules' own UX | Unknown shortcut config should be ignored safely |
| SLOW_OVERVIEW_SOURCE | One overview API source is slower than others | Home page shows loading placeholders per region and reveals ready regions as soon as they resolve | The whole page should not block on the slowest region |

</frozen-after-approval>

## Code Map

- `console/src/app/router/index.tsx` -- the shell currently redirects `/` to `dashboard`; Story 4.1 must replace the `dashboard` placeholder route target with a real overview page while preserving shell routing behavior.
- `console/src/app/pages/shell-placeholder-page.tsx` -- current fallback implementation for shell-owned pages; `dashboard` should stop depending on this placeholder once the overview page exists.
- `console/src/app/shell/shell-navigation.ts` and `console/src/app/shell/app-shell.tsx` -- the overview entry already exists as the first top-level module and remains the expected landing route after sign-in.
- `console/src/shared/i18n/resources.ts` -- `pages.dashboard` still contains placeholder copy and fake status values; Story 4.1 should replace that content with real home-page strings and task-feedback labels.
- `console/src/features/product-auth/product-auth-page.tsx` -- successful sign-in already navigates to `/dashboard`; the overview page becomes the first real post-auth destination.
- `console/src/features/overview/` -- currently absent; Story 4.1 should add the first product-owned overview feature slice here.
- `console/src/features/tasks/` -- currently absent; the task-feedback baseline should be introduced as a reusable feature slice or shared sub-surface rather than embedding one-off JSX directly in the page.
- `apphub/src/api/v1/routers/overview.py` -- currently absent even though the architecture already reserves this route area; Story 4.1 should create the first overview router.
- `apphub/src/services/overview_service.py` or equivalent additive service -- currently absent; should aggregate version, app-state counts, service summary, and recent task summaries without moving ownership away from existing domain services.
- `apphub/src/api/v1/routers/app.py` and `apphub/src/services/app_manager.py` -- the installed-app source of truth already exists and should be reused for installed/running/abnormal summary counts.
- `apphub/src/api/v1/routers/services.py` and `apphub/src/services/core_services.py` -- existing service-summary logic can inform the compact bundled-service status shown on the home page rather than duplicating service probes.
- `apphub/src/services/proxy_task_manager.py` plus install-tracking flows in `apphub/src/api/v1/routers/app.py` -- these are current examples of long-running task state that should feed the baseline shared task-feedback model.
- `_bmad-output/implementation-artifacts/2-1-establish-integration-workspace-entry-cards.md` -- records that `dashboard` was deliberately left as a reserved shell entry and not yet implemented; Story 4.1 is the approved place to replace that placeholder.

## Tasks & Acceptance

**Execution Tasks:**
- [x] `apphub/src/schemas/` -- added overview summary and overview task-summary DTOs that keep headline counts, severity labels, updated timestamps, and target-route metadata compact and stable.
- [x] `apphub/src/services/` -- implemented an additive overview aggregation service that composes product version summary, installed-app counts, bundled-service summary, and recent shared task feedback from existing AppHub sources.
- [x] `apphub/src/api/v1/routers/` and `apphub/src/main.py` -- exposed a protected overview API surface for the home page and kept response contracts additive.
- [x] `apphub/tests/` -- added focused tests for full overview summary, partial-source degradation, empty recent-task state, stable count semantics, and runtime AppResponse compatibility.
- [x] `console/src/features/overview/` -- built the first native overview page with summary cards, shortcuts, and a compact recent-task area.
- [x] `console/src/features/tasks/` or equivalent shared home/task slice -- introduced a reusable task-feedback component and client-side status model for later stories to reuse.
- [x] `console/src/app/router/index.tsx` -- switched `dashboard` from placeholder content to the new overview page while keeping the existing shell and auth entry path intact.
- [x] `console/src/shared/i18n/resources.ts` -- replaced placeholder dashboard copy with real bilingual overview and task-feedback strings.
- [x] If runtime glue is required, keep it minimal -- limited runtime changes to additive overview routing, auth bypass, and task timestamp accuracy without introducing a notifications platform.

**Acceptance Criteria:**
- Given the user opens the home page, when the page loads, then the page prioritizes platform overview data, recent tasks, and frequent entry points, and it does not fall back to host-resource monitoring as the main view.
- Given long-running actions exist across the platform, when the global task area is initialized, then the home page and shared shell provide a reusable task-timeline or task-feedback surface, and later install, backup, and other tasks can share the same feedback model.
- Given overview data sources return partial degradation, when the page renders, then unaffected cards still show stable summary information, and the degraded region communicates a scoped fallback instead of collapsing the whole home page.
- Given the operator needs to continue work, when they use overview shortcuts or status cards, then navigation lands in the owning modules such as My Apps, Services, Logs, Settings, Backup, or Upgrade rather than reproducing those modules inside the home page.
- Given the page shows service or application attention states, when the operator scans the home page, then it answers the three core questions from the PRD: whether the platform is healthy, whether apps are normal, and whether anything needs attention.

## Spec Change Log

- 2026-05-07: Created Story 4.1 to replace the reserved `dashboard` shell placeholder with the first product-native home overview and a reusable global task-feedback baseline.
- 2026-05-07: Bound the story to PRD FR-HOME-001, the Epic 4 scope for product-native operations, and the architecture requirement that overview and tasks land as additive AppHub plus console feature slices.

## Design Notes

The most important guardrail is information hierarchy. This story is not a metrics exercise; it is a product-orientation exercise. The page must answer “what is happening in Websoft9?” before it answers “what is happening on the host?” If host summary data is shown at all in later phases, it remains secondary.

The second guardrail is task reuse. The first version does not need a universal task center, but it does need a durable shared model. If install, proxy, backup, and upgrade each continue to ship their own isolated feedback semantics, the home page will drift into a stitched dashboard with no stable meaning. The story should therefore introduce the smallest reusable task summary contract that later stories can plug into.

The third guardrail is separation between overview and diagnostics. `dashboard` should summarize and route. `services` should diagnose bundled services. `logs` should handle standardized runtime logs. The home page should surface risk and next action without absorbing those deeper responsibilities.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_overview.py` -- expected: overview summary and task-feedback aggregation tests pass
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/main.py src/api/v1/routers/overview.py src/services/overview_service.py` -- expected: added overview backend files compile successfully
- `cd /workspace/websoft9/console && npm run build` -- expected: overview page, task-feedback baseline, router wiring, and i18n updates compile successfully
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh` -- expected: updated overview assets deploy to the running product container for live validation
- `docker exec websoft9-product-current curl -sS http://127.0.0.1:9000/dashboard | head` -- expected: live product entry serves the updated dashboard bundle
- Browser validation on `/dashboard` after authenticated entry -- expected: the page shows overview cards, shortcuts, and recent-task feedback rather than the old placeholder copy

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Added a protected AppHub `/overview` API with stable overview schemas, additive aggregation logic, task-summary fallbacks, and focused overview tests.
- Replaced the `dashboard` placeholder route with a product-native overview page, reusable task-feedback component, and bilingual overview copy.
- Fixed runtime-only AppManager integration issues by supporting `AppResponse` models, preserving task timestamps, and validating the feature in the running `websoft9-product-current` container.
- Ran local backend tests, console production builds, live container sync, browser validation on `/dashboard`, and a clean follow-up code review with no material findings remaining.
- Narrowed the homepage information hierarchy so product info now owns current version, edition, installed-app count, and available-app count; removed the quick-path section and separate applications card.
- Added runtime resource health to the overview so the page now surfaces current CPU, memory, and disk pressure from the running single-container environment.

### File List

- _bmad-output/implementation-artifacts/4-1-build-the-home-overview-and-global-task-feedback-baseline.md
- _bmad-output/implementation-artifacts/4-1-build-the-home-overview-and-global-task-feedback-baseline_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/schemas/overview.py
- apphub/src/services/overview_service.py
- apphub/src/services/proxy_task_manager.py
- apphub/src/api/v1/routers/overview.py
- apphub/src/core/api_key_auth.py
- apphub/src/main.py
- apphub/tests/test_overview.py
- console/src/features/overview/overview-page.tsx
- console/src/features/tasks/task-feedback-list.tsx
- console/src/app/router/index.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-05-07: Created Epic 4 Story 4.1 implementation artifact and advanced sprint tracking to `ready-for-dev`.
- 2026-05-07: Implemented the overview backend/frontend baseline, fixed runtime AppResponse aggregation gaps, and validated the live dashboard inside `websoft9-product-current`.
- 2026-05-08: Simplified the overview layout by removing the quick-path strip and dedicated applications card, moved installability counts into product info, and added runtime resource health signals.
