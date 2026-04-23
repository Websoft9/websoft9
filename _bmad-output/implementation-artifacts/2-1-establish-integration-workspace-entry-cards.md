# Story 2.1: Establish Integration Workspace Entry Cards

## Status

done

## Story

As an operator who uses integrated services,
I want Websoft9 to expose stable integration entry cards and routes,
so that third-party service access is carried by the new product shell rather than scattered legacy links.

## Acceptance Criteria

1. The integrations area shows stable entry cards for Gitea, Portainer, and NPM.
2. Each card can express available, loading, unavailable, and configuration-error states.
3. The integrations route and container structure exists even when one or more integrations are not yet fully connected.
4. Later stories can extend the workspace containers without replacing the shared shell model.

## Dependencies

- Story 1.2 establishes the shared shell, bilingual navigation, and the `/integrations` route placeholder.
- Story 1.5 establishes the product-owned gateway boundary and reserved product-origin prefixes.

## Previous Story Intelligence

- The console route tree already includes an `integrations` segment under the shared application shell.
- Epic 1 intentionally reserved the integrations route so Epic 2 can attach product-owned workspaces without rebuilding providers, navigation, or i18n.
- Previous migration notes require preserving user mental models while cleaning up legacy plugin fragmentation.

## Developer Context

- Architecture requires third-party full-UI access to live under product-owned integration workspaces on the Websoft9 origin, not as raw deep links.
- UX requires the integrations surface to communicate stable state and continuity early in the migration so the new shell does not feel incomplete.
- The existing shell already exposes a top-level integrations navigation entry, so this story should turn that placeholder into a real route cluster rather than inventing a second shell pattern.
- This story defines the common entry-card contract that Stories 2.2 through 2.5 will reuse.
- This story is also the correct owner for the integration-surface layout and styling decision inside the shared shell: entry grouping, left-navigation presentation for repository/containers/gateway, and the feature-level visual alignment with the legacy Cockpit mental model belong here.
- Stories 2.2 through 2.4 should refine each workspace's continuity and embedded behavior, not redefine the shared integration-surface layout language.

## Implementation Guardrails

- Do not make direct ports or external URLs the default primary UX for entering integrations.
- Do not hardcode service availability assumptions into the shell navigation itself; card state must be data-driven.
- Do not create service-specific card patterns that will force later visual divergence.
- Keep the state vocabulary stable across cards: available, loading, unavailable, configuration-error.
- Keep the route structure extensible so each integration can own a workspace page under the same route cluster.

## Suggested File Targets

- `console/src/app/router/`
- `console/src/app/shell/`
- `console/src/features/integrations/`
- `console/src/shared/i18n/`
- optional supporting API contract additions in `apphub/src/api/` if state data is not already available

## Implementation Tasks

1. Replace the integrations placeholder with a dedicated integrations route cluster inside the shared shell.
2. Define a shared integration-card view model for Gitea, Portainer, and NPM.
3. Add bilingual labels, descriptions, and state copy for the integrations landing surface.
4. Define the minimal backend or gateway-fed availability contract needed to populate card states.
5. Reserve stable child-route mount points for the individual integration workspaces.

## Testing Requirements

- Verify the integrations landing route renders through the existing shared shell.
- Verify all three integrations can render cards even if only placeholder state data is available.
- Verify unavailable or misconfigured integrations do not break the overall integrations page.
- Verify English and Chinese shell text cover the card labels and state copy.

## Definition of Done

- A product-owned integrations landing surface exists inside the console shell.
- Gitea, Portainer, and NPM each have a stable entry card and route mount point.
- The shared card state model is defined and reusable by later Epic 2 stories.
- Later integration work can extend the route cluster without reworking shell architecture.
- The shell-facing layout and styling for the integration entry surface are settled enough that later per-service stories do not need to redesign the integration information architecture.

## Source Notes

- Primary sources: Epic 2 acceptance criteria, architecture integration workspace strategy, UX continuity and degraded-state requirements, Epic 1 shell-routing baseline.

## Tasks / Subtasks

- [x] Replace the integrations placeholder with a dedicated integrations route cluster inside the shared shell.
- [x] Define a shared integration-card view model for Gitea, Portainer, and NPM.
- [x] Add bilingual labels, descriptions, and state copy for the integrations landing surface.
- [x] Define the minimal product-origin availability contract used to populate card states.
- [x] Reserve stable child-route mount points for the individual integration workspaces.

## Dev Agent Record

### Debug Log References

- Replaced the generic `/integrations` placeholder route with a dedicated route cluster and landing page.
- Added a shared integration model, shared product-origin probe hook, and reusable status vocabulary for Gitea, Portainer, and NPM.
- Added bilingual landing-surface copy and shared card rendering under the existing shell.
- Promoted the three integration surfaces into first-class shell navigation entries for repository, containers, and gateway while retaining `/integrations` as a compatibility catalog.
- Validated the console changes with `npm run build` and `npm run lint`.
- Ran an automated self-review and fixed the follow-up gaps around session-continuity detection, duplicate probes, bilingual diagnostics, and actionable recovery entry points.

### Completion Notes List

- The shared Epic 2 integration framework now backs both the compatibility catalog and the primary shell entries for repository, containers, and gateway.
- Gitea, Portainer, and NPM each have a stable entry card and reusable route mount point.
- The card state model is shared and ready for the deeper workspace stories that follow.
- The shell and integration surfaces were later tightened from a landing-page style into a denser admin-console layout so the repository, containers, and gateway entry experience aligns better with the legacy Cockpit mental model.
- The sidebar was further normalized toward a standard backend menu by removing per-item descriptions and replacing the generic operations bucket with dedicated services, logs, and users entries.
- The shared shell then added a top-level dashboard entry and converted the left menu from a standalone card into a full-height sidebar column so the menu owns the full left rail like a conventional backend console.
- The shared shell now uses a standalone top header, a softer grouped sidebar, and a flat right-side workspace surface; the dashboard remains a reserved top-level menu route rather than a finished homepage implementation.
- Shell route segments were also normalized to backend-style names without hyphens, including /appstore and /myapps.
- The top header now reserves a logo slot, simplifies the product title to Websoft9, and exposes both locale switching and user actions through backend-style dropdown controls instead of inline buttons.
- The sidebar menu was then tightened again by reducing width, compressing section spacing, and lowering item font/padding so the navigation reads more like a conventional management console and less like stacked cards.
- The sidebar selection style was then rolled back toward the earlier Cockpit-like treatment: a lighter white active block, looser spacing, and less compressed item typography.
- The sidebar was then aligned more closely to the Cockpit reference by matching section-header size to menu items with bold weight, shifting the whole menu inward, and increasing spacing between items.

### File List

- console/src/app/shell/app-shell.tsx
- console/src/app/router/index.tsx
- console/src/app/pages/shell-placeholder-page.tsx
- console/src/features/integrations/integration-model.ts
- console/src/features/integrations/use-integration-status.ts
- console/src/features/integrations/integrations-page.tsx
- console/src/features/integrations/integration-workspace-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: Implemented the product-owned integrations landing surface, reusable card model, and route cluster for Story 2.1.
- 2026-04-22: Promoted Epic 2 workspaces into top-level repository, containers, and gateway navigation while retaining the shared compatibility catalog.
- 2026-04-23: Refined the shell-facing integration layout from a hero-heavy landing page into a tighter admin-console presentation and deployed the rebuilt console assets to the running product container.
- 2026-04-23: Removed sidebar item descriptions, replaced operations with services/logs/users, rebuilt the console, and deployed the updated assets to the running product container.
- 2026-04-23: Added a dashboard/overview entry above App Store, removed the separate navigation card treatment, rebuilt the console, and deployed the updated shell assets to the running product container.
- 2026-04-23: Reworked the shell toward a Cockpit-like grouped sidebar with search, added a dedicated dashboard page, rebuilt the console, and verified the deployed product bundle at /dashboard via the live asset hash.
- 2026-04-23: Removed the temporary dashboard implementation, split the top header out from the content area, softened sidebar interaction styling, normalized shell routes to /appstore and /myapps, rebuilt the console, and verified the live product bundle on /dashboard, /appstore, and /myapps.
- 2026-04-23: Simplified the brand area to Websoft9, reserved a logo slot, converted locale switching and user actions into dropdown menus, rebuilt the console, and verified the live product bundle on /dashboard and /appstore.
- 2026-04-23: Tightened sidebar menu spacing and typography, rebuilt the console, and verified the live product bundle on /dashboard.
- 2026-04-23: Rolled the sidebar active state back to a lighter white block with looser spacing, rebuilt the console, and verified the live product bundle on /dashboard.
- 2026-04-23: Increased sidebar indentation and item spacing, raised section headers to the same size as menu items with bold weight, rebuilt the console, and verified the live product bundle on /dashboard.