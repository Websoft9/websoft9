---
title: 'Story 4.7: Build the core services view and log drilldown'
type: 'feature'
created: '2026-05-06'
status: 'review'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `services` module is still a protected shell placeholder. Operators can open dedicated integration workspaces for gateway, repository, and containers, but there is no product-owned page that summarizes the state of bundled third-party services and provides a stable path into the raw logs that actually explain service-side failures.

**Approach:** Replace the `services` placeholder with a native product-auth-protected services page focused on bundled third-party operational services. The first version should cover Nginx Proxy Manager, Gitea, and Portainer as the primary rows, show runtime state plus health state from existing runtime checks, expose a small set of service indicators that help operators judge whether the issue is availability, bootstrap, or credential continuity, and provide raw-log drilldown that stays inside the `services` module. The `logs` module remains reserved for standardized Websoft9 platform runtime logs.

## Boundaries & Constraints

**Always:** Keep FastAPI AppHub as the only public API layer; keep the `services` route behind the existing product-auth boundary; scope the first version to bundled third-party services that Websoft9 depends on operationally; reuse existing runtime sources such as supervisor status, health checks, bootstrap markers, and service log directories before inventing new probes; keep service raw logs owned by `services`; preserve bilingual shell-resource patterns; keep the page lightweight enough to load quickly inside the current shared shell.

**Ask First:** Expanding the page into a full infrastructure dashboard; adding arbitrary host-service inspection or unrestricted `docker logs` browsing; exposing secret material, full credential files, or host paths; treating every user workload container as a first-version service row; rebuilding Portainer, Gitea, or NPM management UIs natively; introducing a metrics database or always-on timeseries collector.

**Never:** Collapse `services` and `logs` into one mixed observability page; redefine product-auth or add a second permission system; make the operator SSH into the host to inspect bundled service failures; expose raw `docker inspect` or full filesystem details directly to the browser; require the first version to replace the dedicated `gateway`, `repository`, or `containers` workspaces.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOAD_SERVICES_PAGE | Authenticated operator opens `services` route | Page renders bundled service rows for Nginx Proxy Manager, Gitea, and Portainer with runtime state, health state, and last update time | Page shows a stable empty or partial-degradation state instead of failing whole-page render |
| SUPERVISOR_RUNNING_HEALTHY | Service process is running and health endpoint responds | Row shows `running` plus `healthy`, with recent check time and quick actions for logs and workspace entry | Health probe failures do not erase runtime state |
| PROCESS_RUNNING_HEALTH_DEGRADED | Supervisor reports running but health check or bootstrap marker is degraded | Row shows explicit degraded health and highlights the affected indicator | Service remains inspectable and log drilldown stays available |
| PROCESS_DOWN | Supervisor or runtime source reports service missing, exited, or unavailable | Row shows unavailable or stopped state and preserves diagnostic affordances | Backend returns stable state object instead of low-level supervisor tracebacks |
| OPEN_SERVICE_LOGS | User drills into one service's logs | UI loads recent raw lines only for that service from its owned source and keeps service context visible | Missing log file returns a stable no-logs-yet or unavailable state |
| JUMP_TO_WORKSPACE | User wants to continue inside the dedicated third-party UI | Page exposes a controlled link into the existing `gateway`, `repository`, or `containers` workspace for that service | Unsupported mappings are omitted rather than linking to the wrong workspace |
| CORRELATE_PLATFORM_RUNTIME | User suspects a platform-side cause for a service issue | Services page can deep-link into `logs` with seeded context, while raw third-party logs stay in `services` | Unknown deep-link params are ignored safely |
| HEALTH_SOURCE_PARTIAL_FAILURE | One endpoint or marker cannot be read while others succeed | API still returns the rest of the service inventory with per-service error metadata | One bad source must not break all rows |

</frozen-after-approval>

## Code Map

- `console/src/app/router/index.tsx` -- current `services` route still falls through to `ShellPlaceholderPage`; replace it with a native page under `ProductAuthRouteGuard`.
- `console/src/app/pages/shell-placeholder-page.tsx` -- current placeholder that should stop owning the `services` route once this story lands.
- `console/src/app/shell/shell-navigation.ts` -- shell navigation already reserves `services` as a first-class protected product module.
- `console/src/shared/i18n/resources.ts` -- current bilingual copy still describes `services` as a placeholder; add service inventory, state labels, health copy, indicators, and log-drilldown strings here.
- `console/src/features/product-auth/product-auth-route-guard.tsx` -- existing protected-module gate that must remain in front of the services page.
- `apphub/src/main.py` -- router registration point and public API-key bypass rules for the new `services` API surface.
- `apphub/src/services/product_auth.py` -- current protected-module registry already includes `services`; reuse this boundary.
- `apphub/src/api/v1/routers/integrations.py` and `apphub/src/services/integration_session_bridge.py` -- existing integration-to-workspace mapping and bootstrap logic that the services page can link toward without reimplementing third-party login flows.
- `scripts/platform-healthcheck.sh` -- existing runtime health signals for AppHub, Gitea, Portainer, and Nginx Proxy Manager; first-version service health should reuse this logic or its equivalent semantics.
- `docker/product/supervisord.conf` -- current runtime process inventory for bundled services and product processes; use it as the source of truth for first-version service naming and state semantics.
- `docker/product/runtime-asset-boundaries.yaml` -- existing machine-readable boundary file listing service-owned log directories and runtime paths such as `/var/log/websoft9/gitea`, `/var/log/websoft9/portainer`, and `/var/log/websoft9/nginx-proxy-manager`.
- `docs/api-contracts-apphub.md` -- current boundary statement that `logs` consumes standardized platform runtime logs while `services` consumes third-party service raw logs.
- `scripts/sync_websoft9_product_current.sh` -- live-runtime sync path used for validating the updated services slice inside `websoft9-product-current`.

## Tasks & Acceptance

**Execution:**
- [x] `apphub/src/schemas/` -- add service inventory and service-log request/response DTOs that separate service summary state from raw log lines; keep the contract scoped to bundled third-party services.
- [x] `apphub/src/services/` -- implement a focused services domain service that aggregates runtime state, health state, indicator snapshots, workspace mappings, and raw-log access for Nginx Proxy Manager, Gitea, and Portainer by reusing existing runtime signals before adding any new ones.
- [x] `apphub/src/api/v1/routers/` and `apphub/src/main.py` -- expose authenticated `services` endpoints for inventory and per-service log drilldown; keep the public contract additive and aligned with current AppHub response conventions.
- [x] `apphub/tests/` -- add focused regression coverage for protected access rejection, per-service state aggregation, partial health-source failure, unsupported service rejection, and raw-log fallback behavior.
- [x] `console/src/features/services/` -- create a native services page that shows service cards or rows, health/state badges, updated time, compact indicators, workspace-entry affordances, and in-module raw-log drilldown.
- [x] `console/src/app/router/index.tsx` -- route `services` to the native page while preserving `ProductAuthRouteGuard` behavior.
- [x] `console/src/shared/i18n/resources.ts` -- replace placeholder copy with bilingual services-page strings and explicitly distinguish service raw logs from platform runtime logs.
- [x] Runtime glue only if truly necessary -- if one or more bundled services do not already emit accessible raw logs under the declared runtime boundaries, add the minimum runtime wiring needed to make those owned log sources readable without redesigning the broader logging system.

**Acceptance Criteria:**
- Given the user opens the `services` route, when the page loads, then it renders a native services page instead of a shell placeholder and shows bundled service rows with service name, runtime state, health state, and update time.
- Given one bundled service is degraded, when the operator inspects it, then the page surfaces the relevant indicator context and offers a stable raw-log drilldown without sending the user to host tooling.
- Given the operator wants to continue into the dedicated third-party UI, when the page offers a workspace entry, then the mapping stays aligned with the existing `gateway`, `repository`, and `containers` workspaces instead of inventing duplicate surfaces.
- Given the operator needs platform-side correlation, when they jump from a service row toward runtime diagnostics, then the handoff can seed the `logs` page context while service raw logs remain owned by the `services` module.
- Given one health source, log source, or bootstrap marker is unavailable, when the services API responds, then unaffected services still render and the failure degrades per row instead of breaking the full inventory.

## Spec Change Log

- 2026-05-06: Story created to replace the protected `services` placeholder with a product-native bundled-services view and raw-log drilldown.
- 2026-05-06: Scope aligned with the hardened observability boundary established during Story 4.8: `services` owns third-party service raw logs, while `logs` owns standardized Websoft9 platform runtime logs.

## Design Notes

This story should prioritize diagnostic continuity over breadth. Operators already have dedicated workspaces for gateway, repository, and containers, but those workspaces are still third-party-first surfaces. The native `services` module should become the product-owned overview that answers a narrower operational question quickly: which bundled service is failing, how bad is it, and where is the next best drilldown path.

The first version should not promise perfect observability or deep service administration. Existing runtime evidence is already enough to build a credible baseline: supervisor state, health endpoints, bootstrap markers, runtime asset boundaries, and service-owned log directories. Reusing that evidence is safer than introducing new daemons, new databases, or a generic metrics platform.

The most important architecture guardrail is the logs split. The `logs` module is now explicitly the home of standardized Websoft9 platform runtime logs. The `services` module should therefore keep raw Gitea, Portainer, and Nginx Proxy Manager logs inside its own surface, and only hand off to `logs` when the operator is correlating service symptoms with platform-runtime events.

The story should also preserve information architecture discipline. A native services page is not a replacement for the dedicated integration workspaces. It is the summary and triage layer above them.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_services_runtime.py` -- expected: service aggregation, auth, partial failure, and raw-log drilldown tests pass
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/main.py src/api/v1/routers/services.py src/services/core_services.py src/schemas/coreServices.py` -- expected: touched backend files compile cleanly
- `cd /workspace/websoft9/console && npm run build` -- expected: native services page and route wiring compile successfully
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh` -- expected: updated services slice is deployed into the running single-container target for live validation
- `docker exec websoft9-product-current supervisorctl status` -- expected: live service inventory can be reconciled against the new bundled-services view
- `docker exec websoft9-product-current sh -lc 'for path in /var/log/websoft9/gitea /var/log/websoft9/portainer /var/log/websoft9/nginx-proxy-manager; do ls -ld "$path"; done'` -- expected: declared service-owned log roots exist or fail in a controlled, diagnosable way for first-version runtime validation

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Implemented the AppHub services schema, aggregation service, and authenticated router for bundled third-party service inventory plus per-service raw-log drilldown.
- Added focused backend regression coverage for protected access, per-row degradation, unsupported service rejection, raw-log filtering, and unavailable-log fallback.
- Replaced the protected `services` placeholder with a native console page that shows bundled service state, health, indicators, workspace handoff, and in-module raw-log drilldown.
- Added query-seeded handoff into the `logs` page and kept the observability boundary intact: `services` owns third-party raw logs while `logs` owns standardized platform runtime logs.
- Added the minimum runtime glue needed to expose service-owned raw logs in the live single-container product: Gitea and Portainer supervisor output now write to dedicated service log roots, and Nginx Proxy Manager fallback logs are surfaced through the declared runtime boundary.
- Completed a post-implementation code-review/fix pass to remove browser-facing runtime path leakage, keep in-app navigation client-side, and bound service log scanning to recent files.

### File List

- _bmad-output/implementation-artifacts/4-7-build-the-core-services-view-and-log-drilldown.md
- _bmad-output/implementation-artifacts/4-7-build-the-core-services-view-and-log-drilldown_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/main.py
- apphub/src/api/v1/routers/services.py
- apphub/src/schemas/coreServices.py
- apphub/src/services/core_services.py
- apphub/tests/test_core_services.py
- console/src/app/router/index.tsx
- console/src/features/logs/logs-page.tsx
- console/src/features/services/services-page.tsx
- console/src/features/services/services-page.css
- console/src/shared/i18n/resources.ts
- docker/product/supervisord.conf
- docker/product/scripts/platform-entrypoint.sh
- scripts/sync_websoft9_product_current.sh

### Change Log

- 2026-05-06: Created the Epic 4 Story 4.7 BMAD implementation artifact and advanced sprint tracking to ready-for-dev.
- 2026-05-06: Implemented the bundled-services inventory API, raw-log drilldown API, native services page, logs handoff, focused regression tests, and the minimum runtime glue needed to surface service-owned logs in the live single-container product.
- 2026-05-06: Completed a post-implementation review/fix pass that removed browser-facing runtime path leakage, switched services-page handoff links to client-side routing, and bounded recent log-file scanning.