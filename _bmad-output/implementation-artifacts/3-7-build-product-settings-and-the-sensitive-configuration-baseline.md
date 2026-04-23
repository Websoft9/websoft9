# Story 3.7: Build product settings and the sensitive configuration baseline

## Status

done

## Story

As a platform administrator,
I want Websoft9 product settings inside the new console,
so that core runtime configuration no longer depends on legacy plugins or direct host-file edits.

## Acceptance Criteria

1. Given the user enters the settings area, when the page loads, then the UI shows grouped settings for domain entry, certificate, mirror source, internal access, upgrade, and version, and the structure follows the shared shell contract.
2. Given some settings are sensitive, when current values are displayed, then those values are masked by default and the frontend does not become a long-lived plain-text secret surface.

## Dependencies

- Story 1.2 established the shared shell routing and bilingual resource contract.
- AppHub already exposes section-based config reads and writes through `/settings/*`.
- Epic 3 now owns the product-native management surface for store, My Apps, access, and settings flows.

## Current Slice Summary

- The old settings placeholder route is now replaced by a native settings page under the shared shell.
- AppHub now exposes `GET /api/settings/summary`, which groups product settings into domain, certificate, mirror, internal access, upgrade, and version sections.
- Sensitive values such as API keys and certificate key paths are masked server-side before being returned to the frontend.
- Editable baseline settings continue to update through the existing section/key write surface, while read-only sensitive fields remain visible only as masked summaries.

## Implementation Tasks

- [x] Replace the settings placeholder route with a native page inside the shared shell. (AC: 1)
- [x] Group settings into domain, certificate, mirror, internal access, upgrade, and version sections. (AC: 1)
- [x] Add a masked summary endpoint so the browser no longer receives long-lived plain-text values for sensitive fields by default. (AC: 2)
- [x] Keep the baseline editable path for safe settings via the existing section/key update contract. (AC: 1, 2)

## Validation Notes

- 2026-04-23: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `cd /workspace/websoft9/apphub && python3 -m py_compile src/api/v1/routers/proxy.py src/api/v1/routers/settings.py src/services/proxy_manager.py src/services/proxy_task_manager.py src/services/settings_manager.py src/services/app_manager.py src/schemas/proxyTask.py src/schemas/settingsSummary.py`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- The shared shell `settings` route now renders a native grouped settings page instead of a placeholder shell card.
- AppHub now emits a masked settings summary purpose-built for the native console.
- Domain, mirror, internal endpoints, upgrade metadata, and runtime version information are now visible in one product-owned surface.
- Sensitive values stay masked by default and are not shipped to the browser as long-lived plain text through the new summary path.

### File List

- console/src/app/router/index.tsx
- console/src/features/settings/settings-page.tsx
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/settings.py
- apphub/src/schemas/settingsSummary.py
- apphub/src/services/settings_manager.py
- docs/api-contracts-apphub.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-04-23: Implemented the native settings baseline and masked settings summary path for Epic 3 Story 3.7.