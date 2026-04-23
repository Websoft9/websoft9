# Story 2.4: Deliver NPM Embedded Workspace and Session Continuity

## Status

done

## Story

As an operator who needs proxy-management access,
I want to enter Nginx Proxy Manager from within Websoft9 with session continuity,
so that proxy operations remain available inside the new shell while native flows are still being migrated.

## Acceptance Criteria

1. When NPM is reachable, Websoft9 provides embedded full-UI access inside a product-owned workspace.
2. Default access preserves controlled session continuity.
3. If NPM integration fails or becomes unavailable, the workspace presents a clear state, reason summary, and recovery direction.
4. The experience does not degrade into a hidden iframe failure.

## Dependencies

- Story 2.1 establishes the integrations route cluster and shared state model.
- Epic 1 runtime and gateway work keep product-origin and app-access proxy responsibilities separate.

## Previous Story Intelligence

- The platform gateway already proxies NPM through a reserved product-origin path, and runtime work preserves a separate responsibility boundary between platform ingress and app-domain proxying.
- Existing AppHub services already integrate with NPM APIs for proxy and certificate operations, so this story should extend continuity rather than bypassing that integration layer.
- Migration notes define NPM as an early embedded workspace priority while native proxy-management flows are still pending in Epic 3.

## Developer Context

- Architecture requires NPM full-UI continuity inside a product-owned workspace, not a detached raw login surface.
- UX requires explicit state, reason, and recovery guidance for failed embedded integrations.
- This story bridges current operational continuity until later native proxy-management stories land.
- The runtime split from Epic 1 means this workspace must respect the distinction between Websoft9 platform routing and NPM-owned application access logic.

## Implementation Guardrails

- Do not make the standalone NPM direct port the primary console-entry pattern.
- Do not collapse product-origin routing and app-domain proxy ownership back into one frontend abstraction.
- Do not duplicate proxy-management business logic in the frontend when existing AppHub integration contracts already exist.
- Do not allow hidden iframe errors, silent token problems, or blank shells to represent failure.
- Keep NPM workspace entry aligned with the shared integration state vocabulary and recovery pattern.

## Suggested File Targets

- `console/src/features/integrations/`
- `console/src/app/router/`
- `console/src/shared/i18n/`
- `docker/product/gateway/platform-gateway-routes.conf`
- `apphub/src/api/`
- `apphub/src/services/proxy_manager.py`

## Implementation Tasks

1. Define the NPM workspace route under the integrations cluster.
2. Record the controlled session-continuity mechanism used for NPM entry.
3. Implement the embedded workspace container with loading, success, failure, and recovery states.
4. Reuse or extend existing NPM integration contracts instead of inventing a parallel frontend-only access path.
5. Keep the workspace contract compatible with later Epic 3 native proxy-management migration.

## Testing Requirements

- Verify a healthy NPM workspace can be opened from within the shared shell.
- Verify default entry preserves controlled continuity rather than forcing a raw login restart.
- Verify failed or unavailable NPM access shows explicit state and recovery guidance.
- Verify the workspace remains compatible with bilingual shell conventions and the product-owned route boundary.

## Definition of Done

- A stable NPM workspace route exists under the product shell.
- NPM session continuity is defined through one explicit controlled-entry mechanism.
- NPM failure states are visible, diagnosable, and recoverable.
- The workspace contract does not block later native proxy and certificate stories in Epic 3.

## Source Notes

- Primary sources: Epic 2 NPM acceptance criteria, architecture proxy-boundary and integration workspace strategy, UX failure-state requirements, existing AppHub proxy-management integration surface.

## Tasks / Subtasks

- [x] Define the NPM workspace route under the integrations cluster.
- [x] Record and encode the controlled session-continuity mechanism used for NPM entry.
- [x] Implement the embedded workspace container with loading, success, failure, and recovery states.
- [x] Reuse the existing product-origin path instead of inventing a parallel frontend-only access path.
- [x] Keep the workspace contract compatible with later native proxy-management migration.

## Dev Agent Record

### Debug Log References

- Mapped the NPM workspace to the product-owned `/w9proxy/` route inside the integrations cluster.
- Added the primary shell-level gateway route and mapped it to the same product-owned `/w9proxy/` workspace path.
- Kept the shell entry product-owned and avoided a default direct-port workflow.
- Added shared failure, session-error, retry, and diagnostics handling to the NPM workspace without duplicating proxy-management business logic in the frontend.
- Revalidated the full console change set with `npm run build` and `npm run lint`.

### Completion Notes List

- NPM now has a stable gateway workspace route under the Websoft9 shell.
- Session-continuity and failure states are handled through the shared integration contract instead of ad hoc iframe behavior.
- The route remains aligned with the existing platform-origin versus app-access boundary.
- The primary gateway entry now follows the same direct-workspace UX as Gitea: minimal bootstrap state first, then a direct embed of the NPM management surface instead of the generic status wrapper.
- The default embedded landing page now opens the proxy-hosts management view at `/w9proxy/nginx/proxy-hosts` rather than the broader root shell.

### File List

- console/src/app/router/index.tsx
- console/src/features/integrations/integration-model.ts
- console/src/features/integrations/use-integration-status.ts
- console/src/features/integrations/integrations-page.tsx
- console/src/features/integrations/integration-workspace-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: Implemented the NPM embedded workspace, continuity detection, and shared recovery UX for Story 2.4.
- 2026-04-22: Promoted the NPM workspace to the primary gateway navigation entry while retaining the shared compatibility route.
- 2026-04-23: Aligned the gateway route with the Gitea-style direct workspace experience and changed the default embedded landing page to `/w9proxy/nginx/proxy-hosts`, then rebuilt and redeployed the live console bundle.
- 2026-04-23: Story status moved to done after live validation confirmed the direct embedded gateway route and session continuity remain stable.