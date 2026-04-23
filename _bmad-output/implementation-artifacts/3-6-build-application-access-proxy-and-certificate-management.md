# Story 3.6: Build application access, proxy, and certificate management

## Status

done

## Story

As an administrator managing application access,
I want to keep managing domains, proxy bindings, and basic certificate status inside My Apps,
so that the old NPM-backed access flow remains continuous in the new console.

## Acceptance Criteria

1. Given the user enters the application access area, when current access data loads, then the UI shows domain bindings, entry addresses, and basic certificate status sourced through the backend's Nginx Proxy Manager integration.
2. Given the user creates or updates application domain access, when the change is submitted, then the system executes the proxy change through the unified product API surface and returns refreshed access and certificate state.

## Dependencies

- Story 3.4 established the stable My Apps detail shell and access tab location.
- Story 3.5 established the native detail-header action baseline and refresh chain.
- AppHub already exposes proxy and certificate compatibility routes under `/proxys/*`.

## Current Slice Summary

- The native My Apps access tab is no longer placeholder-only.
- The console now loads proxy-host data from `GET /api/proxys/{app_id}` and certificate inventory from `GET /api/proxys/ssl/certificates`.
- Proxy reads now normalize response shape back to product-owned `proxy_id`, domain, and certificate fields instead of leaking NPM-native response shape directly into the UI.
- Access mutations now submit through AppHub-backed proxy tasks with explicit polling, and the UI refreshes both detail and access data after task completion.
- The access tab now supports app-scoped certificate selection or removal alongside domain binding updates.

## Implementation Tasks

- [x] Replace the access-tab placeholder with product-owned access data reads. (AC: 1)
- [x] Surface domain bindings and entry links from the current proxy/detail contract. (AC: 1)
- [x] Surface basic certificate availability from the backend NPM integration. (AC: 1)
- [x] Allow creating or updating domain bindings from the native detail view. (AC: 2)
- [x] Move proxy changes to the unified task model with explicit progress semantics. (AC: 2)
- [x] Add finer certificate binding semantics beyond global availability status. (AC: 1, 2)

## Validation Notes

- 2026-04-23: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `cd /workspace/websoft9/console && npm run build`
- 2026-04-23: `cd /workspace/websoft9/apphub && python3 -m py_compile src/api/v1/routers/proxy.py src/api/v1/routers/settings.py src/services/proxy_manager.py src/services/proxy_task_manager.py src/services/settings_manager.py src/services/app_manager.py src/schemas/proxyTask.py src/schemas/settingsSummary.py`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- My Apps detail access tab now reads proxy hosts and certificate inventory through AppHub-backed APIs instead of staying as shell text only.
- Domain bindings and certificate bindings can now be created or updated from the native access tab through explicit proxy-task acceptance and polling.
- AppHub now exposes a proxy-task status route and normalized proxy payload for the native console.
- Story 3.6 is complete for the current Epic 3 baseline, with multi-host editing intentionally still constrained to the first host as the documented compatibility posture.

### File List

- console/src/features/my-apps/my-app-access-panel.tsx
- console/src/features/my-apps/use-my-app-access.ts
- console/src/app/router/index.tsx
- console/src/features/settings/settings-page.tsx
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/proxy.py
- apphub/src/api/v1/routers/settings.py
- apphub/src/external/nginx_proxy_manager_api.py
- apphub/src/schemas/proxyHosts.py
- apphub/src/schemas/proxyTask.py
- apphub/src/schemas/settingsSummary.py
- apphub/src/services/app_manager.py
- apphub/src/services/proxy_manager.py
- apphub/src/services/proxy_task_manager.py
- apphub/src/services/settings_manager.py
- docs/api-contracts-apphub.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-04-23: Upgraded the native access tab to use AppHub-backed proxy tasks, normalized proxy payloads, and certificate binding selection, completing Story 3.6.