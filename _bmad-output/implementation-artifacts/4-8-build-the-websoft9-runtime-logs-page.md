---
title: 'Story 4.8: Build the Websoft9 runtime logs page'
type: 'feature'
created: '2026-04-30'
status: 'review'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `logs` module is still a shell placeholder. In the current single-container product runtime, operators can inspect `docker logs websoft9-product-current`, but that output is noisy, format-inconsistent, and not shaped for product diagnostics. At the same time, service-specific raw logs should not be mixed into the product logs module because those belong in the `services` module and later service drilldown flows.

**Approach:** Replace the `logs` placeholder with a native product-auth-protected runtime logs page that reads a curated `runtime-console` source from the current product container output. Keep the first version intentionally narrow: AppHub exposes a focused API that reads the product container console stream, normalizes each line into a lightweight log record, applies time-range, severity, keyword, and line-limit filters, and returns only Websoft9 product runtime diagnostics. Raw service logs for Nginx Proxy Manager, Gitea, Portainer, or later per-service drilldown remain out of scope for this story and stay owned by the `services` module.

## Boundaries & Constraints

**Always:** Keep FastAPI AppHub as the only public API layer; keep the `logs` route behind the existing product-auth boundary; scope the first version of the logs page to a single curated `runtime-console` source backed by the product container console output; support time-range, severity, keyword, and recent-line filters; normalize returned entries into a stable frontend shape even if the raw source lines are mixed or partially unstructured; keep bilingual shell-resource patterns; keep service-specific raw logs out of the logs module.

**Ask First:** Expanding the logs module into a generic Docker log browser; exposing arbitrary container selection or host log file browsing; adding Elasticsearch/Loki/Fluent Bit style infrastructure; pulling full Portainer, Gitea, or Nginx Proxy Manager raw logs into the default logs page; turning the first version into a metrics dashboard.

**Never:** Treat `docker logs` as the permanent definition of all platform observability; bypass product-auth for log access; expose user application container logs from the `logs` page; collapse the `services` module and `logs` module into one generic troubleshooting surface; require operators to SSH into the host or understand container internals just to inspect Websoft9 runtime problems.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOAD_RUNTIME_LOGS | Authenticated operator opens `logs` route | Page loads recent `runtime-console` entries from the current product container and shows filter controls | Return stable empty/error state if no entries are currently available |
| FILTER_BY_LEVEL | Operator selects `error`, `warning`, or `info` | UI shows only normalized entries matching the requested severity | Unknown or unmapped lines fall back to `info` instead of failing the query |
| FILTER_BY_KEYWORD | Operator enters a keyword | Backend applies substring filtering and returns matching runtime entries in stable order | Empty keyword returns the unfiltered result for the chosen window |
| FILTER_BY_TIME_RANGE | Operator narrows to a recent window such as 15m, 1h, or 24h | Backend returns only entries whose parsed timestamps fall inside the requested range | Lines without parseable timestamp remain visible only when no time-range filter is active, or are safely excluded with explicit parser behavior |
| LIMIT_RECENT_LINES | Operator requests a bounded tail size | Backend returns the latest matching entries up to the requested limit | Reject invalid or oversized limits with stable 4xx validation response |
| DEEP_LINK_CONTEXT | User enters logs from alert cards, tasks, or later service drilldown navigation | Initial filter state is seeded from query params without making the logs page depend on service-specific raw logs | Unknown context keys are ignored rather than breaking page load |
| CONTAINER_UNAVAILABLE | Product runtime container cannot be resolved or Docker access fails | Page shows explicit runtime-log-unavailable state with retry affordance | Return stable infrastructure error instead of hanging or exposing Docker tracebacks |
| MIXED_UNSTRUCTURED_LINES | Raw console output mixes bootstrap text, AppHub lines, and supervisor text | Backend preserves the original line in `raw`, emits a best-effort timestamp/level, and keeps a stable `runtime-console` source label | Parser failures degrade gracefully without dropping the whole result set |

</frozen-after-approval>

## Code Map

- `console/src/app/router/index.tsx` -- current `logs` route still falls through to `ShellPlaceholderPage`; replace it with a native logs page under `ProductAuthRouteGuard`.
- `console/src/app/pages/shell-placeholder-page.tsx` -- current placeholder implementation that should stop owning the `logs` route once the native page lands.
- `console/src/app/shell/shell-navigation.ts` -- shell navigation already reserves `logs` as a first-class product module.
- `console/src/shared/i18n/resources.ts` -- current bilingual shell copy still describes `logs` as a placeholder; add runtime-log labels, filter copy, empty/error states, and runtime-console terminology here.
- `console/src/features/product-auth/product-auth-route-guard.tsx` -- existing protected-module boundary that must remain in front of the logs page.
- `apphub/src/main.py` -- router registration point for the new logs API surface.
- `apphub/src/services/product_auth.py` -- current protected-module registry already includes `logs`; reuse this boundary rather than introducing separate log auth.
- `apphub/src/services/app_manager.py` and `apphub/src/services/app_status.py` -- existing background-task patterns and in-memory progress logs that inform how task-related runtime lines should remain discoverable without becoming a separate first-version source.
- `docker/product/scripts/platform-entrypoint.sh` -- current bootstrap/runtime console writer; one of the main sources that should remain visible through the curated runtime-console view.
- `docker/product/supervisord.conf` -- current single-container supervisor setup where many child-process stdout/stderr streams are still mixed; this story may tighten console output enough to make runtime-console more product-focused without redesigning the whole logging stack.
- `docker/product/apphub/logging_config.yaml` -- current AppHub stdout logging format used by the product container runtime.
- `docker/product/runtime-asset-boundaries.yaml` -- current machine-readable runtime log boundary reference for platform-gateway and supervisor log files; useful guardrail even though this story reads the curated runtime console rather than every file-backed source.
- `scripts/sync_websoft9_product_current.sh` -- current live-runtime sync path used when validating updated single-container behavior inside `websoft9-product-current`.

## Tasks & Acceptance

**Execution:**
- [ ] `apphub/src/schemas/` -- add runtime-log request/response DTOs for query filters and normalized log entries -- keep the first version limited to the curated `runtime-console` source and a lightweight stable record shape.
- [ ] `apphub/src/services/` -- implement a focused runtime-log service that resolves the current product container, reads recent console output through Docker access, best-effort parses timestamps and severity, applies time-range/level/keyword/limit filters, and preserves `raw` lines for display -- do not expose arbitrary container selection.
- [ ] `apphub/src/api/v1/routers/` and `apphub/src/main.py` -- expose authenticated logs endpoints for the runtime-console view and optional source metadata -- keep contracts additive and aligned with the current AppHub response conventions.
- [ ] `apphub/tests/` -- add focused regression coverage for filter validation, parser fallback behavior, unavailable-container handling, and protected access rejection -- lock the narrowed runtime-console scope into executable checks.
- [ ] `console/src/features/logs/` -- create a native runtime logs page with recent-line display, keyword search, severity filter, time-range filter, limit selector, refresh action, and clear empty/error states -- keep the UX intentionally lighter than a full observability suite.
- [ ] `console/src/app/router/index.tsx` -- route `logs` to the native page while preserving `ProductAuthRouteGuard` behavior -- remove the placeholder from the live route without changing surrounding shell structure.
- [ ] `console/src/shared/i18n/resources.ts` -- replace placeholder copy with bilingual runtime-log strings and explicitly position the page as Websoft9 runtime logs rather than a service-log browser.
- [ ] `docker/product/scripts/platform-entrypoint.sh`, `docker/product/supervisord.conf`, and related runtime output glue if needed -- reduce avoidable console noise and keep runtime-console focused on product-relevant events without attempting a full logging-system redesign in this story.

**Acceptance Criteria:**
- Given the user opens the `logs` route, when the page loads, then it renders a native runtime logs page instead of a shell placeholder and shows a recent runtime-console view sourced from the current Websoft9 product container.
- Given the user filters by time range, severity, keyword, or recent-line limit, when the query runs, then the page updates with normalized runtime entries and does not require the operator to inspect raw `docker logs` manually.
- Given the current runtime line belongs to Websoft9 bootstrap, AppHub runtime, or supervisor-managed product execution, when it is returned through the logs API, then the frontend can display it through one stable record shape even if the raw line format varies.
- Given the user is looking for Nginx Proxy Manager, Gitea, Portainer, or other service-specific raw logs, when they open the runtime logs page, then those logs are not treated as the primary logs-module scope and remain owned by the `services` module or later service drilldown flows.
- Given Docker access or product-container resolution fails, when the logs page requests runtime-console data, then the user sees a stable product-facing failure state instead of low-level Docker internals or a hung page.

## Spec Change Log

- 2026-04-30: Story created with the narrowed logs-module scope agreed during implementation planning: service-specific raw logs remain in the `services` module, while the `logs` module first ships a curated `runtime-console` view backed by the single product container output.
- 2026-05-06: Architecture boundary reaffirmed by product direction: the `logs` module is the home of standardized Websoft9 platform runtime logs, while the `services` module is the home of third-party service raw logs; future implementation should evolve sources toward that split instead of broadening `runtime-console` into a mixed container-log browser.

## Design Notes

This story is intentionally narrower than a full observability redesign. The product needs a useful logs page now, not a perfect multi-source logging platform. The first version should therefore treat the current single-container console output as a curated runtime source, normalize it lightly, and expose only the filters operators need most often. The backend should prefer best-effort parsing and stable UI semantics over brittle source-specific perfection.

The main boundary to preserve is product meaning. The logs module is for Websoft9 runtime diagnosis, not for browsing every bundled service or every user workload. Service-specific drilldown belongs in Story 4.7 and later services work. This story should leave a clean path for future expansion by accepting source metadata and query-state deep links, but it should not block on those later surfaces being finished first.

Because the current runtime is still a single product container, `docker logs` is an acceptable first-version implementation source for the native logs module. It should be treated as a product runtime console view, not as the long-term authoritative definition of all platform logs.

The target end state is explicit: `logs` should present standardized platform runtime logs, and `services` should present third-party service raw logs. Any later refactor of collection, formatting, or storage should strengthen that separation rather than collapse both concerns into one shared log surface.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_runtime_logs.py` -- expected: runtime-log parsing, filtering, and auth tests pass
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/main.py src/api/v1/routers/logs.py src/services/runtime_logs.py src/schemas/runtimeLogs.py` -- expected: touched backend files compile cleanly
- `cd /workspace/websoft9/console && npm run build` -- expected: native logs page and route wiring compile successfully
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh` -- expected: updated product runtime is deployed into the running single-container target for live validation
- `docker logs --tail 200 websoft9-product-current` -- expected: runtime-console source still contains the operator-relevant bootstrap/AppHub/runtime events that the native logs page is designed to surface

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Implemented the AppHub runtime logs schema, service, router, and focused regression tests for parsing, filtering, unauthenticated access, and unavailable-container handling.
- Replaced the `logs` shell placeholder with a native protected console page that supports time range, severity, keyword, recent-line filters, manual refresh, and optional auto refresh.
- Added bilingual runtime logs copy, kept the narrowed `runtime-console` scope intact, and avoided pulling raw bundled-service logs into the `logs` module.
- Added a follow-up source-curation guard that excludes Nginx Proxy Manager console lines from `runtime-console`, locked that behavior with regression coverage, and merged refresh plus auto-refresh controls into the filter row for the live page.
- Refined the post-review log curation after live restart validation: `runtime-console` now keeps a narrowed Websoft9 runtime allowlist centered on `platform-entrypoint` and AppHub runtime markers, which removes NPM bootstrap text while preserving meaningful startup events.
- Replaced the mixed-container `docker logs` reader with a standardized platform runtime log source at `/var/log/websoft9/platform-runtime.log`, wired `platform-entrypoint` and AppHub logging into that JSONL contract, and kept third-party raw logs outside the `logs` module boundary.
- Revalidated the slice with focused backend tests, backend compile checks, console typecheck/build, live hot-sync into `websoft9-product-current`, live product-auth status probing, protected API probing, and browser route confirmation.
- Live validation confirmed the standardized runtime log file is being written inside the product container; a full restart also exposed an existing startup blocker where product readiness can stall while library assets sync from the artifact service, so the standardized source was verified directly in-container even though `/api/auth/status` did not become ready within the bounded wait window.
- Completed a post-implementation review pass with no new actionable findings for the touched runtime logs files.

### File List

- _bmad-output/implementation-artifacts/4-8-build-the-websoft9-runtime-logs-page.md
- _bmad-output/implementation-artifacts/4-8-build-the-websoft9-runtime-logs-page_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/api/v1/routers/logs.py
- apphub/src/main.py
- apphub/src/schemas/runtimeLogs.py
- apphub/src/services/runtime_logs.py
- apphub/tests/test_runtime_logs.py
- console/src/app/router/index.tsx
- console/src/features/logs/logs-page.css
- console/src/features/logs/logs-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-30: Created the Epic 4 Story 4.8 BMAD implementation artifact and advanced sprint tracking to ready-for-dev.
- 2026-05-06: Implemented the narrowed runtime-console logs backend and native console logs page, completed focused verification, hot-synced the live single-container runtime, and advanced the story to review.
- 2026-05-06: Added a post-review runtime-console curation fix so Nginx Proxy Manager console output no longer leaks into the logs module, merged refresh controls into the filter row, reran focused validation, and re-synced the live runtime.
- 2026-05-06: Re-ran validation with a full product-container restart, confirmed NPM bootstrap text was still leaking, tightened runtime-console curation to a Websoft9 runtime allowlist, reran backend tests, and verified the preserved startup sequence inside the live container.
- 2026-05-06: Implemented the standardized platform runtime log source at `/var/log/websoft9/platform-runtime.log`, migrated the runtime logs service off mixed `docker logs`, added structured writers for `platform-entrypoint` and AppHub, reran focused backend validation, and verified live file writes while noting that full post-restart readiness remained blocked by library asset sync timing.