# Story 2.2: Deliver Gitea Embedded Workspace and Session Continuity

## Status

done

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
- Tightened the Gitea auth markers so public Explore content is no longer misclassified as a session failure.
- Restored the healthy Gitea workspace to a direct iframe embed without the extra shell-level status panel above it.
- Simplified the repository refresh transition so Gitea no longer falls back to the generic diagnostics-and-recovery panel during normal bootstrap.
- Reconciled the live Gitea runtime to use the product-owned `/w9git/` root URL and static asset prefix so the embedded UI can render under the product origin instead of behaving like a raw `:3001` root deployment.
- Updated the AppHub Gitea session bridge to log in directly against the local Gitea service on `:3001`, then seed the browser with normalized `/w9git` cookies, bypassing the internal proxy hop that was corrupting the cookie path for auto-login.
- Extended the session bootstrap contract so the console now passes its active locale to AppHub and AppHub rewrites the Gitea `lang` cookie to the matching `/w9git` locale, keeping the embedded workspace language aligned with the product shell.

### Completion Notes List

- Gitea now has an embedded repository workspace entry under the Websoft9 shell.
- The default path stays product-owned, and raw external login is no longer the default entry pattern.
- When continuity falls back to a login/bootstrap surface, the UI now reports a dedicated session-continuity failure instead of dropping into a blank or silent state.
- When continuity is healthy, the repository entry now opens straight into the embedded Gitea workspace again instead of forcing the user through an extra workspace status header first.
- The repository route now uses only a minimal bootstrap transition instead of the shared recovery panel during normal refresh.
- The running product Gitea UI now resolves under `/w9git/` with product-origin asset paths, which removes the most severe embedded-style and navigation breakage from the previous root-path configuration.
- Browser-like validation now confirms `POST /api/integrations/gitea/session` returns `/w9git` cookies and that a fresh client can reach `/w9git/user/settings` and `/w9git/explore/repos` in an authenticated state.
- Browser-like validation with `X-Websoft9-Locale: zh-CN` now confirms the bootstrap response emits `lang=zh-CN` and the embedded Gitea UI renders Chinese labels such as `登录`, `探索`, and `帮助`.

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
- 2026-04-23: Narrowed Gitea login-page detection and restored the healthy repository route to direct embedded rendering, then rebuilt and redeployed the console assets to the running product container.
- 2026-04-23: Simplified the repository refresh transition, corrected the running Gitea subpath runtime configuration to `/w9git/`, and revalidated the embedded route against the live product container.
- 2026-04-23: Fixed Gitea auto-login by bypassing the cookie-path-mangling internal proxy during session bootstrap and revalidated the flow with browser-like `Origin` and `Referer` headers against the live product container.
- 2026-04-23: Story status moved to done after live validation confirmed embedded repository continuity, auto-login, and locale synchronization remain stable.