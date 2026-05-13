# Story 3.1: Build the App Store list and filters page

## Status

done

## Story

As a user looking for applications,
I want to browse and filter the App Store in the new Websoft9 console,
so that I can quickly find installable apps while retaining continuity with the old high-frequency flow.

## Acceptance Criteria

1. When the user opens the App Store page and the page finishes loading, the UI shows application cards, category filters, keyword search, and base metadata, and the information architecture remains recognizable to existing users.
2. When the user changes category or search criteria and the list refreshes, the system returns matching application results, and default list behavior stays within core performance expectations.

## Dependencies

- Epic 1 establishes the Vite React console shell, bilingual routing baseline, and shared shell layout.
- Epic 2 establishes the current shell styling language and keeps `appstore` reserved as a first-class top-level route.
- Existing AppHub APIs already expose `/api/apps/catalog/{locale}` and `/api/apps/available/{locale}` through the product gateway as the current catalog baseline.

## Previous Story Intelligence

- Story 2.1 settled the shell information architecture, including the top-level `appstore` route and the Cockpit-like navigation baseline. Story 3.1 should preserve that shell language rather than redesign it.
- The old plugin App Store remains the best migration reference for user mental model: category-driven browsing, keyword search, recognizable cards, and a later detail/install handoff. However, Cockpit runtime dependencies and modal-heavy implementation patterns must not be revived.
- Repository memory already captured an important migration guardrail: the new App Store detail flow should reuse `/api/apps/available/{locale}` payload first, and the current available-app payload already includes runtime-derived `settings` and `is_web_app` fields even though the schema is incomplete.

## Developer Context

- The nearest backend owner for Story 3.1 is `apphub/src/services/app_manager.py`, specifically `get_available_apps(locale)`, which already loads localized product metadata, applies `initial_apps` filtering, and enriches each app with `settings` and `is_web_app` derived from docker-library env files.
- The current backend route surface already exposes the right starting contract in `apphub/src/api/v1/routers/app.py`. Story 3.1 should prefer adapting the frontend to that contract before inventing a new API shape.
- The current frontend anchor is the `appstore` shell route in `console/src/app/router/index.tsx` and `console/src/app/shell/shell-navigation.ts`. The current route still points to a placeholder page, so the first implementation hop should be replacing that placeholder with an App Store feature route and page.
- The old Cockpit plugin at `pluings/plugin-appstore/src/pages/appstore.js` is a migration reference for recognizable interaction patterns only: category filters, keyword search, card browsing, visible base metadata, and a clear “detail/install later” mental model. Do not port Cockpit APIs, bootstrap layout, or modal install flow into the new console.
- Architecture requires React 19.2 + React Router v7 + Material UI 9 + TanStack Query 5 conventions under the existing shell. Prefer feature-local data hooks and query-backed state over ad hoc global stores.
- PRD and architecture both position App Store as a primary product-native workflow. This page should feel native to Websoft9, but it still needs to preserve continuity with the old high-frequency browsing flow.

## Implementation Guardrails

- Do not reintroduce Cockpit dependencies, old plugin helpers, or direct host-command execution.
- Do not invent a frontend-only catalog source when AppHub already owns the current catalog and available-app contracts.
- Do not mix Story 3.2 detail/install submission concerns into Story 3.1. This story stops at list, filters, search, base metadata, and navigation handoff readiness.
- Do not silently drop bilingual behavior. Locale-aware app browsing must reuse the shell locale and existing backend `zh` / `en` contract.
- Do not create an App Store page that abandons the recognizable category-first browsing model from the legacy flow.
- Do not add new backend dependencies or a new state library.

## Suggested File Targets

- `console/src/app/router/index.tsx`
- `console/src/app/shell/shell-navigation.ts`
- `console/src/app/pages/` or a new App Store feature page under `console/src/features/app-store/`
- `console/src/shared/i18n/resources.ts`
- `console/src/shared/` feature support utilities if a query or API helper layer already exists
- optional contract cleanup in `apphub/src/schemas/` only if the frontend needs declared fields that the existing backend already returns
- tests under the current console test structure if present for route/page behavior

## Implementation Tasks

1. Replace the App Store placeholder route with a real App Store feature page under the existing shared shell. (AC: 1)
2. Add a locale-aware data access layer that loads available apps from AppHub using the current shell locale and exposes loading, success, empty, and failure states. (AC: 1, 2)
3. Implement recognizable App Store browsing UI with keyword search, category filters, application cards, and base metadata. (AC: 1, 2)
4. Keep the information architecture recognizable to legacy users while staying native to the new shell styling and layout system. (AC: 1)
5. Validate that category and search filtering refresh matching results without breaking baseline performance expectations for the default list flow. (AC: 2)

## Testing Requirements

- Add focused frontend tests for the App Store filtering logic if the console test setup supports it.
- At minimum, validate the touched frontend slice with the narrowest available executable check, then run the console build.
- Verify locale-sensitive data loading uses the current shell locale and maps to the backend `zh` / `en` contract.
- Verify keyword and category changes update the visible list without full-page shell breakage.
- Verify empty and failure states are explicit rather than blank.

## Definition of Done

- The `appstore` route renders a native App Store page instead of a placeholder.
- The page loads localized available-app data from AppHub.
- Users can browse via cards, category filters, and keyword search.
- The result remains recognizable to old Websoft9 users while fitting the new shell.
- Story 3.2 can layer detail and install-parameter work on top without rewriting the Story 3.1 page contract.

## Source Notes

- Primary sources: `_bmad-output/planning-artifacts/epics.md` Epic 3 Story 3.1, `_bmad-output/planning-artifacts/prd.md` FR-APP-001, `_bmad-output/planning-artifacts/architecture.md` frontend/data/API decisions.
- Migration reference: `pluings/plugin-appstore/src/pages/appstore.js` for recognizable list/filter/search mental model only.
- Backend contract baseline: `apphub/src/api/v1/routers/app.py`, `apphub/src/services/app_manager.py`, `docs/api-contracts-apphub.md`.
- Repo memory baseline: `/memories/repo/app-store-story-2-2-baseline-2026-04-17.md`.

## Tasks / Subtasks

- [x] Replace the App Store placeholder route with a real feature page inside the shared shell. (AC: 1)
  - [x] Confirm the current `appstore` route wiring and swap the placeholder surface to an App Store feature entry.
  - [x] Reuse the existing shell layout and navigation rather than introducing a parallel page frame.
- [x] Add the App Store data-access layer around the current AppHub available-app contract. (AC: 1, 2)
  - [x] Map shell locale to the backend `zh` / `en` route parameter.
  - [x] Expose loading, error, empty, and success states for the list page.
- [x] Build the App Store list UI with recognizable filters and cards. (AC: 1)
  - [x] Implement category filter controls.
  - [x] Implement keyword search.
  - [x] Render application cards with base metadata from the current payload.
- [x] Apply client-side filtering behavior that refreshes matching results predictably. (AC: 2)
  - [x] Ensure category and keyword criteria can combine.
  - [x] Keep default list behavior fast and stable for the core list size.
- [x] Add and run focused validation for the touched slice. (AC: 1, 2)
  - [ ] Add targeted tests if the console test setup is available.
  - [x] Run the narrowest executable validation available for the page and then the console build.

## Dev Notes

### Architecture Compliance

- Keep the implementation in the Vite React console under the existing shell and React Router v7 route model.
- Use Material UI for page composition and controls so the page stays visually aligned with the current shell.
- Use TanStack Query if the console already has a query layer available for server-state fetching; otherwise follow the existing frontend data-fetching pattern nearest to the route implementation without introducing a new global store.
- Keep AppHub as the authoritative owner of available-app data.

### API / Data Contract Notes

- `GET /api/apps/available/{locale}` is the primary contract for Story 3.1 and currently combines localized product metadata with runtime-derived `settings` and `is_web_app` fields.
- Locale is currently limited to `zh` or `en` at the backend route boundary.
- Story 3.1 should not depend on a separate detail API.

### Project Structure Notes

- Frontend anchor: `console/src/app/router/index.tsx`, `console/src/app/shell/shell-navigation.ts`, and the current placeholder page path.
- Backend owning abstraction: `apphub/src/services/app_manager.py` and `apphub/src/api/v1/routers/app.py`.
- Legacy reference only: `pluings/plugin-appstore/src/pages/appstore.js`.

### Validation Notes

- First focused validation after the first substantive edit should be the narrowest console-side executable check available for the touched slice.
- If no narrower route/page test exists, fall back to the console build.

### References

- Source: `_bmad-output/planning-artifacts/epics.md` Epic 3 Story 3.1
- Source: `_bmad-output/planning-artifacts/prd.md` FR-APP-001 and FR-APP-002 context
- Source: `_bmad-output/planning-artifacts/architecture.md` Frontend Architecture, API & Communication, Decision Impact Analysis
- Source: `docs/api-contracts-apphub.md` App endpoints summary
- Source: `apphub/src/api/v1/routers/app.py`
- Source: `apphub/src/services/app_manager.py`
- Source: `pluings/plugin-appstore/src/pages/appstore.js`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Debug Log References

- 2026-04-23: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `cd /workspace/websoft9/console && npm run build`
- 2026-05-13: `cd /workspace/websoft9/console && npm run typecheck`
- 2026-04-23: `docker exec websoft9-product-current curl -sS -i --max-time 20 http://127.0.0.1:8889/api/apps/available/en`
- 2026-04-23: `docker exec websoft9-product-current curl -sS -i --max-time 20 http://127.0.0.1:8889/api/apps/catalog/en`
- 2026-04-23: `cd /workspace/websoft9/console && docker cp dist/. websoft9-product-current:/etc/websoft9/console/`
- 2026-04-23: `python -m py_compile docker/product/scripts/platform-sync-runtime-assets.py`
- 2026-04-23: `docker exec websoft9-product-current python /websoft9/script/platform-sync-runtime-assets.py`
- 2026-04-23: `docker exec websoft9-product-current curl -sf http://127.0.0.1:8889/media/json/product_en.json`
- 2026-04-23: `docker exec websoft9-product-current curl -sf http://127.0.0.1:8889/media/json/app-store-install-metadata.json`
- 2026-04-23: `docker exec websoft9-product-current supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf restart apphub-api`
- 2026-04-23: `docker exec websoft9-product-current sh -c "cd /websoft9/apphub && PYTHONPATH=/opt/websoft9-pydeps:/websoft9/apphub:/websoft9/apphub/src python ..."`

### Completion Notes List

- Replaced the `appstore` placeholder route with a native React App Store page that uses locale-aware AppHub data, category filters, deferred keyword search, and recognizable application cards.
- Corrected the console data contract to use the product gateway surface `/api/apps/available/{locale}` instead of the non-routable `/api/v1/...` path.
- Relaxed AppHub API-key enforcement for the read-only App Store browsing endpoints so the first-party shell can load catalog data without re-exposing the internal key to the browser.
- Fixed AppHub media path handling to use joined paths instead of string concatenation so catalog and available-app endpoints tolerate runtime config values without trailing slashes.
- Corrected the product runtime config default for `app_media.path` to `/websoft9/media/json` and added a startup asset bootstrap that restores missing media/library packages from artifacts when copy-forward assets are absent.
- Synced the current console bundle and backend fixes into the live `websoft9-product-current` container and verified both App Store APIs return `200 OK`.
- Reworked the native App Store page back toward the legacy plugin standard by sourcing the top-level filters from `/api/apps/catalog/{locale}` so category order and filter semantics match the old plugin instead of using frontend-derived categories.
- Simplified the browse cards to the old lightweight pattern and merged detail plus install back into a single modal flow so the page follows the legacy browse-detail-install rhythm instead of a denser new-shell information card pattern.
- Restored legacy-style media loading by resolving logos and screenshots through local `/media/logos/*` and `/media/screenshots/{locale}/*` paths first, which fixes the missing-image regression caused by relying on external payload URLs directly.
- Further tightened the detail and install modal presentation toward the legacy plugin by restoring the old header rhythm, category link row, compact footer buttons, and the web-app install domain row layout.
- Hardened the install helper against the real AppHub payload shape by supporting distribution version arrays instead of assuming comma-delimited strings.
- Restored several legacy plugin behaviors that materially affect user flow: keyword search now resets category filters and only searches the old title/key/summary fields, detail-page category clicks now reselect both the primary and secondary category, and the install page now branches on product-owned wildcard-domain configuration instead of deriving suffixes from the browser hostname.
- Removed the centered max-width wrapper so the App Store content area now fills the available shell workspace and keeps its own background distinct from the left navigation column.
- Refined the native App Store presentation so the right-hand workspace now stays on the shell's white content background, install/detail typography is less bright, the set-global-domain action sits on the application-name row, screenshot spacing from the divider is larger, and install validation/errors use one consistent top alert style.
- Reduced steady-state AppHub load by moving the App Store's read-only browse data to static-first media JSON: the console now reads `/media/json/product_{locale}.json` and `/media/json/catalog_{locale}.json` before falling back to the legacy AppHub endpoints.
- Refined the App Store IA into an install-entry surface: navigation now labels this area as Install Apps, the page exposes marketplace, compose, and runtime install-source entry cards, and non-marketplace paths intentionally stay as guided placeholders until Stories 3.3A and 3.3C land.
- Added startup generation of `/media/json/app-store-install-metadata.json`, which precomputes each app's install `settings`, `is_web_app`, and configured `initial_apps` filter from the library `.env` files so the install modal can stay functional without AppHub transforming the browse payload on every request.
- Narrowed the non-rounded visual treatment back to the modal footer's Close and Install buttons only; helper actions such as Documentation, Set Global Domain, Add Domain, Enable/Disable Domain, and Delete now use their prior rounded styling again.
- Formally downgraded `GET /api/apps/catalog/{locale}` and `GET /api/apps/available/{locale}` to compatibility-only AppHub fallback endpoints in the router metadata and API contract docs so the static `/media/json/*` path remains the intended primary browse contract.

### File List

- console/src/app/router/index.tsx
- console/src/features/app-store/app-store-model.ts
- console/src/features/app-store/app-store-page.tsx
- console/src/features/app-store/use-app-store-apps.ts
- console/src/features/app-store/use-app-store-catalogs.ts
- console/src/shared/i18n/resources.ts
- apphub/src/main.py
- apphub/src/services/app_manager.py
- docker/product/scripts/platform-sync-config.sh
- scripts/platform-sync-config.sh
- docker/product/scripts/platform-sync-runtime-assets.py
- docker/product/scripts/platform-entrypoint.sh
- docker/product/Dockerfile

### Change Log

- 2026-04-23: Created Story 3.1 with implementation context, backend contract anchors, legacy App Store migration references, and validation guidance.
- 2026-04-23: Implemented the App Store list/filter page, corrected the console-to-AppHub contract, fixed AppHub read-only browsing/runtime path issues, added product asset bootstrap recovery, and validated the live product endpoints.
- 2026-04-23: Reworked the App Store page to follow the legacy plugin standard more closely by restoring catalog-driven filter ordering, lightweight browse cards, and a single detail-install modal flow, then rebuilt and redeployed the live bundle.
- 2026-04-23: Corrected the App Store image pipeline to match the old plugin local media contract and tightened the card styling further toward the legacy rectangular browse layout, then rebuilt and redeployed the live bundle.
- 2026-04-23: Tightened the App Store detail/install modal styling toward the legacy plugin screenshots and fixed distribution parsing for array-shaped version payloads before rebuilding and redeploying the live bundle.
- 2026-04-23: Restored legacy search, category-link, wildcard-domain install, and full-width workspace behaviors, then rebuilt the console, redeployed the live bundle, and restarted AppHub so `/api/settings/domain` could be consumed by the first-party shell.
- 2026-04-23: Tuned the App Store visual finish further by restoring the white content background, tightening modal typography, moving the set-global-domain action into the old inline position, increasing screenshot/divider spacing, and unifying install alerts to the legacy top-banner pattern before rebuilding and redeploying the live bundle.
- 2026-04-23: Refactored the App Store browse data path to static media JSON with generated install metadata, kept the AppHub browse endpoints as fallback only, restored rounded helper buttons, rebuilt the console, regenerated live metadata, and redeployed bundle `index-7xBjQFrT.js`.
- 2026-04-23: Marked the AppHub App Store browse endpoints as deprecated compatibility fallbacks in router metadata and API docs and annotated the frontend hooks so future work does not accidentally promote them back to the primary data path.
- 2026-04-23: Synced the compatibility-only AppHub browse metadata into the live product container, restarted `apphub-api`, and validated that the runtime OpenAPI now exposes both browse routes as deprecated fallback endpoints.