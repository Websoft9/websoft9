---
title: 'Story 5.1: Build the upgrade precheck and migration summary'
type: 'feature'
created: '2026-05-06'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The native `settings` page still exposes product-owned internal endpoints that operators should not know or edit in the single-container runtime. At the same time, the page needs a stable place to show version inventory and the future upgrade flow, but the current upgrade block is only a set of plain read-only values and does not read like an actionable upgrade surface.

**Approach:** Treat the settings page as the staging surface for Epic 5, but simplify it back into a single operator-facing form instead of multiple grouped cards. Remove internal access addresses from the native summary, keep only the current product version visible from runtime metadata, reshape the upgrade area into a compact row of planned actions, and replace certificate-path exposure with a single HTTPS switch that automatically applies the platform default certificate behavior.

## Boundaries & Constraints

**Always:** Keep FastAPI AppHub as the only public API layer; keep the `settings` route behind the existing product-auth boundary; do not expose internal default URLs, hostnames, or compatibility credentials in the native settings summary; keep version inventory sourced from runtime metadata rather than hand-maintained UI constants; keep bilingual shell-resource patterns; keep the upgrade area honest about current capability.

**Ask First:** Introducing a full upgrade executor in this slice; exposing host package-manager actions; surfacing raw migration internals before the backend summary is ready; removing compatibility config keys that are still required by legacy paths without tracing all consumers.

**Never:** Ask the operator to edit `portainer.base_url`, `gitea.base_url`, `nginx_proxy_manager.base_url`, or similar single-container internal defaults from the native settings UI; present placeholder upgrade values as if upgrade execution already exists; hide version information that operators need to judge upgrade readiness.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOAD_SETTINGS_PAGE | Authenticated operator opens `settings` | Page shows one compact settings form with domain, HTTPS, upgrade entry points, and current product version without exposing internal access defaults or unrelated internal mirror metadata | Missing data degrades per row instead of breaking the whole page |
| VERSION_METADATA_AVAILABLE | `version.json` exists in runtime | Current product version renders in the footer-style version area | Missing plugin keys do not affect this slice because plugin versions are intentionally hidden |
| VERSION_METADATA_MISSING | Runtime metadata file absent | Version block stays visible and falls back to `-` or empty-safe values | UI remains stable and upgrade card still renders |
| INTERNAL_ACCESS_COMPAT_FIELDS_EXIST | Backend config still contains compatibility keys | Native summary omits those fields from operator-visible settings | Compatibility readers continue to function through the config layer |
| UPGRADE_NOT_IMPLEMENTED_YET | Upgrade backend not ready | UI reserves clear precheck and start-upgrade buttons as disabled or planned entry points with explanatory copy | No fake success path or broken action handler is shown |

</frozen-after-approval>

## Code Map

- `apphub/src/services/settings_manager.py` -- native settings summary shaping point; remove operator-facing internal access fields here and keep version inventory emitted from runtime metadata.
- `apphub/src/schemas/settingsSummary.py` -- summary contract for grouped settings UI.
- `console/src/features/settings/settings-page.tsx` -- native settings UI; version block and upgrade action layout should live here.
- `console/src/shared/i18n/resources.ts` -- bilingual copy for revised settings, version inventory, and upgrade staging area.
- `scripts/sync_websoft9_product_current.sh` -- live-runtime sync path; must also keep `version.json` aligned in the running container so version inventory is truthful during validation.
- `version.json` -- runtime metadata source for product version and plugin versions.

## Tasks & Acceptance

**Execution:**
- [x] Remove internal access endpoints and compatibility secrets from the native settings summary shown to operators.
- [x] Keep only the current product version visible in the native settings page.
- [x] Reshape the upgrade section into a compact action row with explicit precheck and execution entry placeholders.
- [x] Replace certificate-path exposure with a single platform HTTPS switch that automatically applies the platform default certificate behavior.
- [x] Ensure hot-sync validation also updates runtime version metadata so the live page does not show stale or missing version data.
- [ ] Implement the actual upgrade precheck backend contract and connect the upgrade buttons to real flows.
- [ ] Add migration summary data that explains what will change before upgrade execution begins.

**Acceptance Criteria:**
- Given the operator opens `settings`, when the page loads, then internal single-container access defaults are not shown or editable in the native settings surface.
- Given runtime version metadata exists, when the page renders, then the current product version is clearly visible in the settings page without extra plugin version noise.
- Given the upgrade flow is not implemented yet, when the page renders, then the upgrade area still has intentional row layout and explicit planned actions instead of ambiguous static values.
- Given the operator toggles platform HTTPS, when the setting is saved, then the platform gateway reloads and the 8890 HTTPS listener follows the saved setting.
- Given the product is hot-synced for live validation, when the running container refreshes, then the settings page reads the same runtime version metadata as the workspace source.

## Spec Change Log

- 2026-05-06: Story created to move the settings page toward an upgrade-ready surface by removing internal defaults, preserving runtime version visibility, and reserving explicit upgrade actions.

## Design Notes

This story starts by tightening the operator contract. Internal service URLs are implementation details of the single-container runtime, not operator-managed settings. Keeping them visible makes the settings page noisier and encourages unsafe mental models about what the operator is expected to configure.

Version visibility is the minimum trustworthy baseline for upgrade readiness. Before precheck logic exists, the operator still needs to know what product build and plugin inventory are currently running.

The upgrade area should therefore become a deliberate staging card rather than a list of static values. Even if the real actions remain disabled in this slice, the layout should already communicate where precheck and execution will live when Epic 5 continues.

## Verification

**Commands:**
- `cd /workspace/websoft9/console && npm run build` -- expected: revised settings UI compiles successfully.
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh` -- expected: updated settings UI, summary shaping, and version metadata are deployed into the running product container.
- `docker exec websoft9-product-current curl -sS http://127.0.0.1:8889/api/settings/summary` -- expected: summary groups no longer include `internal_access`, and `version` plus `upgrade` remain present.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Removed the `internal_access` group from the native settings summary so operators no longer see single-container internal defaults and compatibility credentials.
- Redesigned the native settings page into a single old-style row layout instead of grouped cards.
- Reduced version display to the current product version only.
- Removed the incorrect mirror row from the operator-facing settings UI because `docker_mirror` is internal mirror metadata, not the host Docker registry acceleration setting.
- Replaced certificate-path exposure with a real HTTPS switch that restarts the platform gateway and toggles the 8890 HTTPS listener.
- Migrated platform HTTPS control and certificate ownership off `nginx_proxy_manager` onto a dedicated `platform_gateway` config section and platform-owned TLS files so the gateway no longer depends on NPM SSL assets.
- Extended the live hot-sync path to copy `version.json` into the running product container, which restores truthful version rendering during runtime validation.
- Left actual upgrade precheck and migration summary actions for the next Epic 5 implementation slice.

### File List

- _bmad-output/implementation-artifacts/5-1-build-the-upgrade-precheck-and-migration-summary.md
- _bmad-output/implementation-artifacts/5-1-build-the-upgrade-precheck-and-migration-summary_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/services/settings_manager.py
- console/src/features/settings/settings-page.tsx
- console/src/shared/i18n/resources.ts
- scripts/sync_websoft9_product_current.sh

### Change Log

- 2026-05-06: Created the Epic 5 Story 5.1 implementation artifact and started the upgrade-surface preparation slice inside the native settings page.
- 2026-05-06: Removed operator-facing internal defaults, promoted runtime version inventory, staged upgrade actions in the UI, and fixed live hot-sync to include `version.json`.
