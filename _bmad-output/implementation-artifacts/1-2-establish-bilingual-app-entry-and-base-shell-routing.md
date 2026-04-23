# Story 1.2: Establish Bilingual App Entry and Base Shell Routing

## Status

done

## Story

As a platform operator,
I want the new console to have a stable bilingual entry, provider stack, and shell-level routing baseline,
so that later features can land under one consistent application boundary.

## Acceptance Criteria

1. Base providers, route composition, and shell-level structure exist in the new console workspace.
2. The implementation does not depend on `cockpit.locale` or `po.js`.
3. Locale resources and i18n structure exist for both Chinese and English.
4. Future shared shell strings and navigation can reuse the same i18n mechanism.

## Dependencies

- Story 1.1 should have created the `console/` workspace and baseline dependencies.

## Previous Story Intelligence

- Story 1.1 establishes a fresh Vite-based workspace with no legacy Cockpit packaging assumptions.
- Keep the shell composition inside `console/src/app`; do not scatter shell logic across feature folders.

## Developer Context

- Architecture assigns `console/src/app` to providers, shell, and router ownership.
- Architecture assigns `console/src/shared/i18n` to internationalization ownership.
- UX requires continuity for existing users and explicitly bilingual operation.
- The new console must replace Cockpit-provided locale plumbing with product-owned i18n resources.
- This story establishes only the reusable shell baseline. Feature-specific information architecture, entry-page layout, and service-facing visual alignment belong to the downstream feature stories rather than this baseline story.

## Implementation Guardrails

- Do not read language state from Cockpit globals.
- Do not hardcode shell strings directly into route modules.
- Keep shell routing product-oriented: app store, my apps, operations, integrations, settings.
- Use a provider stack that can host router, query client, theme, and i18n without later inversion.

## Suggested File Targets

- `console/src/main.tsx`
- `console/src/app/App.tsx`
- `console/src/app/providers/`
- `console/src/app/router/`
- `console/src/app/shell/`
- `console/src/shared/i18n/`
- `console/public/locales/`

## Implementation Tasks

1. Establish the application root and provider composition.
2. Add shell-level routing with placeholder routes aligned to the target product information architecture.
3. Create English and Chinese locale resources for the shell baseline.
4. Wire an i18n bootstrap path that future features can extend.
5. Prove the shell renders and route transitions work without Cockpit runtime coupling.

## Testing Requirements

- Verify app startup with both supported locales.
- Verify route composition renders through the shared shell.
- Verify no dependency remains on `cockpit.locale`, `po.js`, or Cockpit-only globals.
- Add at least one focused test or smoke check for provider wiring if the workspace test baseline already exists.

## Definition of Done

- A reusable provider stack exists.
- A shell route baseline exists.
- English and Chinese shell resource files exist.
- The next frontend stories can add feature pages without rebuilding the app entry.
- The visual layout and styling of a concrete feature surface is intentionally deferred to the owning feature story.

## Source Notes

- Primary sources: Epic 1, architecture shell and i18n boundaries, UX continuity and bilingual requirements.

## Dev Agent Record

### Debug Log

- Replaced the Story 1.1 bootstrap route with a shared shell route tree aligned to the product IA: app store, my apps, operations, integrations, and settings.
- Added product-owned i18n bootstrap wiring with `i18next`, `react-i18next`, and bundled locale resources under `src/shared/i18n`.
- Extended the provider stack to host theme, query client, and i18n together while preserving the route boundary pattern from Story 1.1.
- Validated the implementation with `npm install`, `npm run build`, `npm run lint`, and `npm run dev -- --host 0.0.0.0`.
- Verified the console source tree contains no dependency on `cockpit.locale`, `po.js`, or Cockpit globals.
- Followed up review findings by folding router into the provider stack, persisting locale preference, and removing the duplicate locale source so the shell has a single i18n truth source.

### Completion Notes

- Story 1.2 acceptance criteria are satisfied: the console now has a reusable bilingual provider stack, a shell-level route baseline, and locale resources for English and Chinese.
- Shared shell strings and route placeholders now resolve through the same i18n mechanism, giving later stories a stable application boundary for feature pages.
- Locale preference is now product-owned and persisted, and the shell renders from bundled resources without waiting on external locale fetches.
- Final re-review returned no blocking findings. The remaining gap is the lack of an automated smoke test for locale switching and shell render continuity.

### File List

- console/README.md
- console/index.html
- console/package-lock.json
- console/package.json
- console/src/app/App.tsx
- console/src/app/pages/shell-placeholder-page.tsx
- console/src/app/providers/app-providers.tsx
- console/src/app/router/index.tsx
- console/src/app/shell/app-shell.tsx
- console/src/app/shell/shell-navigation.ts
- console/src/main.tsx
- console/src/shared/i18n/i18n.ts
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: established bilingual app entry, product shell routing, and shared locale resources for Story 1.2.
- 2026-04-22: resolved review follow-ups for provider composition, locale persistence, and single-source i18n resources.
- 2026-04-22: completed final validation and re-review with no findings; story moved to done.
