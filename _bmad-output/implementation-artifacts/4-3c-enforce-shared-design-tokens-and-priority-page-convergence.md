---
title: 'Story 4.3C: Enforce shared design tokens and priority-page convergence'
type: 'feature'
created: '2026-05-21'
status: 'review'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 4.3A established the design-system foundation and Story 4.3B established the product visual system direction, but the console still drifts because those decisions are not enforced in implementation. Priority native pages still rely on duplicated page-local tokens, duplicated field styling, and inconsistent panel geometry.

**Approach:** Create one enforcement slice that centralizes shared console tokens, introduces a reusable shared surface field-style helper, and migrates the highest-visibility native pages to the same token and surface contract. This story is not another redesign concept pass. It is the implementation bridge that prevents further page-level drift.

## Boundaries & Constraints

**Always:** Keep React + Vite + Material UI as the existing frontend stack; preserve the current shell, routing, and feature ownership; centralize tokens in shared frontend layers; use shared field styling for product-native forms; migrate the first-wave priority pages without rewriting their core business logic; preserve bilingual product support.

**Ask First:** Replacing Material UI; rewriting every console page in one pass; introducing a second parallel theme system; changing backend contracts for purely visual reasons; turning priority-page convergence into a full information-architecture rewrite.

**Never:** Continue adding new page-local token namespaces for first-wave product-native pages; keep copying near-identical TextField styling into features that already share the same visual grammar; let sprint tracking hide active redesign work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOAD_PRIORITY_PAGE | User opens overview, App Store, My Apps, settings, services, or logs | Page surfaces inherit the same shared token contract for borders, surfaces, shadows, and text hierarchy | One page may still carry local accents, but it must not break the shared base surface grammar |
| RENDER_SHARED_FORM_FIELD | A product-native form field renders in settings or install surfaces | Field inherits shared background, border, focus, disabled, helper, and placeholder semantics | Page-local overrides may extend behavior, but should not replace the base contract |
| TOGGLE_COLOR_MODE | Shell switches between light and dark mode | Shared token layer updates priority pages consistently without per-page mode forks | Local page accents must continue to degrade gracefully through shared tokens |
| ADD_FUTURE_PAGE | A new UI-heavy story adds another native surface | Shared tokens and field helper provide the default implementation path | Missing design-system primitives should be added to shared layers instead of copied into the feature |

</frozen-after-approval>

## Code Map

- `console/src/shared/theme/design-tokens.css` -- authoritative shared token layer for page surfaces, borders, spacing, field geometry, and badge semantics.
- `console/src/shared/design-system/form-field-sx.ts` -- shared helper for product-native form fields so feature pages stop copying near-identical MUI field overrides.
- `console/src/shared/design-system/page-shell.css` -- canonical page-shell surfaces should now inherit shared tokens rather than hardcoded values.
- `console/src/features/overview/overview-page.css` -- first-wave overview adoption of shared tokens.
- `console/src/features/app-store/app-store-page.tsx` -- App Store install workspace adoption of the shared field helper.
- `console/src/features/my-apps/my-apps-page.css` -- My Apps adoption of shared surface and badge tokens.
- `console/src/features/settings/settings-page.tsx` and `console/src/features/settings/settings-page.css` -- settings adoption of shared field helper and shared surface tokens.
- `console/src/features/services/services-page.css` -- services surface convergence.
- `console/src/features/logs/logs-page.css` -- logs surface convergence.
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-21.md` -- planning correction that formalizes why this enforcement story exists.

## Tasks & Acceptance

**Execution:**
- [x] Create a shared console token layer that centralizes base surface, border, spacing, radius, and badge semantics.
- [x] Add a reusable shared field-style helper for product-native MUI form fields.
- [x] Migrate page-shell surfaces and first-wave native page CSS to the shared token contract.
- [x] Adopt the shared field helper in high-visibility product-native form surfaces.
- [x] Update planning and sprint-tracking artifacts so the redesign track explicitly includes the enforcement slice.

**Acceptance Criteria:**
- Given priority native pages still drift visually, when this story lands, then overview, App Store, My Apps, settings, services, and logs inherit one shared token layer for their base surface grammar.
- Given product-native forms still duplicate field styling, when this story lands, then settings and App Store install surfaces reuse one shared field-style helper instead of separate copied implementations.
- Given the console supports light and dark mode, when the operator switches mode, then the first-wave pages continue to converge through shared token mappings rather than per-page hardcoded forks.
- Given redesign progress must stay auditable, when sprint tracking is reviewed, then Stories 4.3A, 4.3B, and 4.3C all appear in `sprint-status.yaml`.

## Spec Change Log

- 2026-05-21: Created Story 4.3C to turn 4.3A foundation and 4.3B visual direction into an enforced implementation slice.
- 2026-05-21: Centralized shared console tokens, added the shared field-style helper, and converged the first-wave native page surfaces.

## Verification

**Commands:**
- `cd /workspace/websoft9/console && ./node_modules/.bin/tsc -b --noEmit` -- expected: no TypeScript errors after shared-token and shared-field adoption.
- `cd /workspace/websoft9/console && npm run build` -- expected: the Vite production build succeeds with the new shared token import and updated page surfaces.
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh websoft9-product-current` -- expected: the updated console assets are deployed into the running product container for live validation.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-21: Created Story 4.3C to formalize the enforcement gap between 4.3A/4.3B and current console implementation drift.
- 2026-05-21: Added `design-tokens.css` as the shared console token layer and updated canonical page-shell surfaces to consume it.
- 2026-05-21: Added `form-field-sx.ts` and migrated settings plus App Store install surfaces to the same field contract.
- 2026-05-21: Converged overview, My Apps, settings, services, and logs base surfaces onto the shared token layer.

### File List

- _bmad-output/implementation-artifacts/4-3c-enforce-shared-design-tokens-and-priority-page-convergence.md
- _bmad-output/implementation-artifacts/4-3c-enforce-shared-design-tokens-and-priority-page-convergence_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-21.md
- _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-21_cn.md
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/epics_cn.md
- console/src/index.css
- console/src/shared/theme/design-tokens.css
- console/src/shared/design-system/form-field-sx.ts
- console/src/shared/design-system/page-shell.css
- console/src/features/overview/overview-page.css
- console/src/features/app-store/app-store-page.tsx
- console/src/features/my-apps/my-apps-page.css
- console/src/features/settings/settings-page.tsx
- console/src/features/settings/settings-page.css
- console/src/features/services/services-page.css
- console/src/features/logs/logs-page.css

### Change Log

- 2026-05-21: Added the planning correction and created Story 4.3C for design-system enforcement.
- 2026-05-21: Implemented the shared token and shared field-style convergence slice across the first-wave priority pages and advanced Story 4.3C to review.