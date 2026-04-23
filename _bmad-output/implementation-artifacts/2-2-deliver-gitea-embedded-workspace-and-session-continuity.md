# Story 2.2: Deliver Gitea Embedded Workspace and Session Continuity

## Status

in-progress

## Story

As an operator who needs repository access,
I want to enter Gitea from within Websoft9 without breaking context,
so that repository operations remain continuous inside the new shell.

## Acceptance Criteria

1. When Gitea is reachable, Websoft9 provides embedded full-UI access under a product-owned workspace.
2. Default entry does not force the user through a raw external login screen.
3. When session continuity cannot be established, the UI shows a clear failure state and reason summary.
4. Workspace failure does not degrade into a blank, silent, or contextless surface.

## Dependencies

- Story 2.1 establishes the integrations landing surface and route mount points.
- Epic 1 runtime work provides the product gateway and internal Gitea service placement.

## Previous Story Intelligence

- The current product runtime already exposes Gitea through the platform gateway on a reserved product-origin path.
- Existing AppHub and CLI flows already rely on Gitea integration data, so this story should preserve continuity rather than invent a second repository-access model.
- Migration notes indicate Gitea continuity should initially favor workspace bridging and session continuity before native replacement of high-frequency actions.

## Developer Context

- The product gateway currently proxies Gitea through a product-owned prefix, which is the correct architectural anchor for this workspace.
- Architecture requires product-owned workspaces with backend session brokerage or delegated auto-login, not raw deep links to standalone login pages.
- UX requires the first third-party entry to feel continuous and recoverable, especially for existing users coming from the old shell.
- Gitea remains a third-party full-UI integration in this phase; this story is about entry continuity and stable embedding, not native repository feature replacement.

## Implementation Guardrails

- Do not make the default Gitea entry bounce the user to a naked external login page.
- Do not hardcode internal hostnames or ports into frontend code.
- Do not treat a failed embed as a generic blank iframe; expose an explicit state and recovery path.
- Preserve product-origin ownership for the workspace route even if Gitea itself remains proxied.
- Keep the Gitea workspace implementation aligned with the shared state and route conventions introduced by Story 2.1.

## Suggested File Targets

- `console/src/features/integrations/`
- `console/src/app/router/`
- `console/src/shared/i18n/`
- `docker/product/gateway/platform-gateway-routes.conf`
- `apphub/src/` routes or service adapters if server-side session establishment needs an explicit contract

## Implementation Tasks

1. Define the Gitea workspace route under the integrations cluster.
2. Decide and document the controlled session-continuity mechanism for Gitea entry.
3. Implement the embedded workspace container and state transitions for loading, success, and failure.
4. Define failure summaries and a recovery entry that are visible inside the workspace.
5. Verify the workspace still feels product-owned even though it renders third-party UI.

## Testing Requirements

- Verify a healthy Gitea path can be opened from inside the shared shell.
- Verify default entry does not require the user to manually restart authentication on a raw login page.
- Verify failed or unavailable Gitea access shows an explicit reason summary and stable fallback UI.
- Verify English and Chinese copy covers the Gitea workspace title, loading, and failure states.

## Definition of Done

- A stable Gitea workspace route exists under the product shell.
- The team has one explicit session-continuity strategy for Gitea entry.
- Gitea loading, success, and failure states are visible and recoverable.
- Story 2.5 can later standardize failure handling without rewriting the Gitea workspace contract.

## Source Notes

- Primary sources: Epic 2 Gitea acceptance criteria, architecture integration workspace strategy, UX continuity requirements, current product gateway reserved-path model.

## Tasks / Subtasks

- [x] Define the Gitea workspace route under the integrations cluster.
- [x] Document and encode the controlled Gitea session-continuity detection strategy around the product-owned route.
- [x] Implement the embedded workspace container and state transitions for loading, success, and failure.
- [x] Define failure summaries and a recovery entry visible inside the workspace.
- [x] Verify the workspace remains product-owned even though it renders third-party UI.

## Dev Agent Record

### Debug Log References

- Added the Gitea child route under `/integrations/:integrationKey` and mapped it to the product-owned `/w9git/` workspace path.
- Added the primary shell-level repository route and mapped it to the same product-owned `/w9git/` workspace path.
- Extended integration probing so authentication-like responses resolve to a dedicated `session-error` state instead of being misreported as healthy.
- Added workspace-level recovery actions and diagnostics metadata for the resolved Gitea route path.
- Validated the shared implementation through `npm run build` and `npm run lint`.

### Completion Notes List

- Gitea now has an embedded repository workspace entry under the Websoft9 shell.
- The default path stays product-owned, and raw external login is no longer the default entry pattern.
- When continuity falls back to a login/bootstrap surface, the UI now reports a dedicated session-continuity failure instead of dropping into a blank or silent state.

### File List

- console/src/app/router/index.tsx
- console/src/features/integrations/integration-model.ts
- console/src/features/integrations/use-integration-status.ts
- console/src/features/integrations/integrations-page.tsx
- console/src/features/integrations/integration-workspace-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: Implemented the Gitea embedded workspace path, session-continuity detection, and recovery UX for Story 2.2.
- 2026-04-22: Promoted the Gitea workspace to the primary repository navigation entry while retaining the shared compatibility route.