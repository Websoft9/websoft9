---
title: 'Align My Apps with legacy plugin layout and refactor its UI logic'
type: 'feature'
created: '2026-04-24'
status: 'draft'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/3-4-build-the-my-apps-list-and-detail-shell.md'
  - '{project-root}/_bmad-output/implementation-artifacts/3-5-build-lifecycle-actions-and-the-application-detail-header.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The current native My Apps implementation is functionally present, but its list and detail pages still feel like generic shell cards instead of the dense, action-first plugin-myapps management surface that existing Websoft9 users recognize. That mismatch also leaves UI state, list formatting, and detail rendering logic too scattered to evolve cleanly.

**Approach:** Rework the native My Apps list and detail views so their information architecture, layout density, status emphasis, and action rhythm follow the legacy plugin-myapps baseline while staying inside the current React plus AppHub contract. During that UI realignment, refactor page-local formatting, filtering, and action wiring so the new layout is driven by clearer view models instead of ad hoc render helpers.

## Boundaries & Constraints

**Always:** Preserve the current AppHub-backed APIs and route structure; use legacy plugin-myapps as layout and interaction baseline rather than copying Cockpit-specific implementation; keep install tracking, logs, lifecycle actions, and access management working after the layout change; keep mobile and desktop rendering usable.

**Ask First:** Any change that requires altering AppHub response contracts, removing an already shipped user action, or expanding scope into unrelated modules outside My Apps.

**Never:** Reintroduce cockpit.js dependencies, host-command execution, or Bootstrap-era plugin packaging; replace current lifecycle or access APIs with new backend surfaces as part of this pass; do a cosmetic-only reskin that keeps the current fragmented UI state model untouched.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Legacy-style list load | `/api/apps` returns mixed active, inactive, installing, and error apps | My Apps renders a denser management-first list patterned after plugin-myapps, with clearer status grouping, direct actions, and visible install/error feedback | N/A |
| Tracked install handoff | URL contains `trackedAppId` or `trackingId` and `/api/apps` still returns transient install rows | The list highlights the tracked item and keeps log/error affordances visible in the legacy-style layout | If the tracked row is not yet present, show a waiting state instead of breaking the page |
| Detail continuity | User opens a resolvable installed app | Detail page uses legacy plugin-myapps structure cues for header, summary, and tab rhythm while retaining current native actions and access panel | If detail fetch fails, show a stable error state without collapsing the surrounding page frame |
| Runtime action in dense layout | User triggers start, stop, restart, redeploy, uninstall, or log viewing from the new layout | Actions still target current APIs and refresh the list/detail state consistently after completion or acceptance | Keep existing error dialogs, snackbar feedback, or task/log views intact and visible |

</frozen-after-approval>

## Code Map

- `console/src/features/my-apps/my-apps-page.tsx` -- list-page owner; should stop being a generic MUI card grid and become the native equivalent of the legacy app gallery, including status sections, card actions, search row, and install or error dialogs.
- `console/src/features/my-apps/my-app-detail-page.tsx` -- detail-page owner; should be rebuilt around the legacy modal-width shell, header rhythm, left-side pills, and tab panels instead of incremental MUI approximation.
- `console/src/features/my-apps/my-app-access-panel.tsx` -- current native access editor; must inherit the rebuilt detail panel shell cleanly so Access does not look like a foreign subtree.
- `console/src/features/my-apps/use-my-apps.ts` -- list data boundary; should expose normalized status, access, and card-ready fields so legacy-style rendering does not keep re-deriving raw API data in JSX.
- `console/src/features/my-apps/use-my-app-detail.ts` -- detail data boundary; should expose detail-ready derived state for overview rows, dynamic tabs, and container or volume summaries.
- `console/src/features/my-apps/my-app-media.tsx` -- legacy-compatible logo resolver; remains the bridge between native console and old plugin media naming rules.
- `console/src/features/my-apps/*.css` -- target location for native legacy-style structure layers that translate old class semantics into the current console instead of scattering one-off sx fragments.
- `console/src/shared/i18n/resources.ts` -- bilingual labels for rebuilt list and detail wording, including tab titles, action copy, and empty or error states.
- `pluings/plugin-myapps/src/pages/myapps.js` -- authoritative legacy list behavior and management rhythm reference.
- `pluings/plugin-myapps/src/pages/appdetail.js` -- authoritative legacy detail shell, dynamic tab order, and action affordance reference.
- `pluings/plugin-myapps/src/pages/appdetailtabs/*.js` -- legacy tab content references for Overview, Container, Compose, Access, Volumes, PHP, Database, Monitor, and Uninstall slices.
- `pluings/plugin-myapps/src/assets/scss/custom/structure/_topbar.scss` -- source of `appstore-item-content`, `appstore-item-content-icon`, `col-same-height`, `app-icon`, and title truncation behavior.
- `pluings/plugin-myapps/src/assets/scss/custom/components/_modal.scss` and `pluings/plugin-myapps/src/assets/scss/custom/components/_nav.scss` -- source of modal width, colored header, left nav-pills behavior, and shared spacing rules.
- `pluings/plugin-myapps/src/assets/scss/config/*/_light-mode.scss` and `pluings/plugin-myapps/src/assets/scss/config/*/_custom-variables.scss` -- theme token source for nav-pills backgrounds and shared light-mode visual values.

## Tasks & Acceptance

**Execution:**
- [ ] `console/src/features/my-apps/my-apps-page.tsx` -- rebuild the list page around the legacy plugin information architecture, including the top filter row, official versus other grouping, dense card body rhythm, and inline inactive or error actions -- this replaces approximation with a structure-first native rebuild.
- [ ] `console/src/features/my-apps/my-app-detail-page.tsx` -- rebuild the detail page shell from the legacy baseline, including a modal-width white frame, icon plus status header, action button strip, left vertical pills, and tab-panel composition -- this is the main corrective step for the current visual mismatch.
- [ ] `console/src/features/my-apps/my-app-access-panel.tsx` and `console/src/features/my-apps/*.css` -- create a dedicated legacy-style structure layer for Access and shared detail panel styling so native React can reproduce old class semantics without dragging Bootstrap into the console -- this addresses the root styling gap.
- [ ] `console/src/features/my-apps/use-my-apps.ts` and `console/src/features/my-apps/use-my-app-detail.ts` -- centralize status mapping, card models, overview rows, tab selection rules, access entries, and other derived display fields into stable view-model helpers -- this prevents the rebuilt pages from becoming another large JSX-only port.
- [ ] `console/src/shared/i18n/resources.ts` -- align labels and empty or error copy with the rebuilt list/detail structure while keeping bilingual coverage intact -- this avoids mixed metaphors from the current shell wording.
- [ ] `console/src/features/my-apps/my-app-media.tsx` and any touched asset references -- preserve old logo fallback behavior, including base-name fallback and locale default images, while the surrounding layout is rebuilt -- this keeps media continuity intact during the visual reset.

**Acceptance Criteria:**
- Given the user opens My Apps, when installed apps render, then the page follows the legacy plugin grouping, card density, status badges, search row, and action placement closely enough that it reads as the same product surface rather than a modernized reinterpretation.
- Given the user opens a supported app detail page, when the page renders, then the shell uses the legacy modal-width frame, header hierarchy, left-side pills, and tab-panel rhythm while still calling the current native React and AppHub APIs.
- Given old plugin styling depended on shared class names and theme tokens instead of one page stylesheet, when the native rebuild is inspected, then equivalent structure styles exist in dedicated My Apps CSS layers rather than being scattered as page-local MUI `sx` approximations.
- Given the user triggers install-log, lifecycle, access, redeploy, or uninstall flows from the rebuilt list or detail views, when those flows complete or fail, then the current feedback behavior remains reachable and no action becomes visually orphaned by the new structure.
- Given the rebuilt pages are compared against the legacy plugin source, when the code is reviewed, then legacy-specific concerns that cannot be migrated directly, such as cockpit runtime helpers or bootstrap modal internals, are intentionally replaced by native console equivalents instead of silently dropped.

## Spec Change Log

## Design Notes

The current gap is structural before it is cosmetic. In the plugin, the visible result comes from three layers acting together: the page DOM, shared class names such as `appstore-item-content` and `col-same-height`, and theme tokens like `nav-pills-bg`. Reaching parity in the console means rebuilding those structural layers natively instead of continuing to tune isolated `sx` fragments.

The legacy plugin is still the UX authority, but not the implementation authority. Cockpit navigation, bootstrap modal internals, and plugin-era helper wiring should be translated into current React router, query hooks, dialogs, and fetch-based actions. The rebuild should preserve old information architecture while swapping in native console primitives deliberately.

The refactor should center on view-model helpers and dedicated legacy-style CSS layers. If a layout detail only exists because one component computed it inline, the next pass will drift again. Derived status, access, and overview rows should therefore move toward helpers, while spacing, framing, truncation, and pill states move into reusable My Apps CSS.

## Verification

**Commands:**
- `cd /workspace/websoft9/console && npm run typecheck` -- expected: passes with no TypeScript errors in My Apps files
- `cd /workspace/websoft9/console && npm run build` -- expected: console production build succeeds after the layout and refactor changes

**Manual checks:**
- Compare the rebuilt list page against `pluings/plugin-myapps/src/pages/myapps.js` and confirm the page grouping, card density, top controls, status styling, and inactive or error action placement now follow the legacy baseline closely.
- Compare the rebuilt detail page against `pluings/plugin-myapps/src/pages/appdetail.js` and confirm the white modal-width shell, icon plus status header, left pills, and tab panel framing read as the same management surface.
- Verify Access still feels embedded inside the rebuilt detail shell rather than a generic MUI form panel dropped into one tab.