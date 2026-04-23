# Story 2.3: Deliver Portainer Embedded Workspace and Session Continuity

## Status

in-progress

## Story

As an operator who needs container-management access,
I want to enter Portainer from within Websoft9 without repeated login interruption,
so that container operations stay continuous inside the new shell.

## Acceptance Criteria

1. When Portainer is reachable, Websoft9 provides embedded full-UI access under a product-owned workspace.
2. Default entry does not force the user to restart the session from an external login page.
3. If Portainer access continuity fails, the workspace shows an explicit degraded or failed state.
4. The reason for failure is exposed instead of being hidden behind a silent iframe or blank surface.

## Dependencies

- Story 2.1 establishes the integrations route cluster and shared entry-card model.
- Epic 1 runtime work provides the platform gateway and internal Portainer placement.

## Previous Story Intelligence

- The current product gateway already exposes a Portainer-related reserved path and a dedicated Portainer UI serving path in the converged runtime.
- Existing backend integration already communicates with Portainer over its internal HTTPS surface, so continuity work should build around server-side control rather than client-side certificate workarounds.
- Migration notes define Portainer as a continuity-first embedded workspace before any deeper native replacement of container-management actions.

## Developer Context

- Architecture requires Portainer to remain accessible through a product-owned workspace under the Websoft9 origin.
- UX explicitly rejects blank or silent embedded failures; degraded and failed states must be named and recoverable.
- Current runtime already proves Portainer can be surfaced from inside the product container, which lowers infrastructure risk for this story.
- This story should standardize the Portainer workspace contract but leave full cross-integration failure unification to Story 2.5.

## Implementation Guardrails

- Do not expose raw direct-port access as the default primary Portainer UX inside the console.
- Do not move certificate or internal HTTPS complexity into frontend-only hacks.
- Do not let Portainer-specific failure handling diverge from the shared integration-state model.
- Do not accept a workspace implementation that becomes an unlabelled blank frame when Portainer bootstrap fails.
- Preserve product-origin ownership and shell continuity even if the actual Portainer UI remains proxied.

## Suggested File Targets

- `console/src/features/integrations/`
- `console/src/app/router/`
- `console/src/shared/i18n/`
- `docker/product/gateway/platform-gateway-routes.conf`
- `docker/product/gateway/portainer-ui.conf`
- `apphub/src/external/portainer_api.py` or adjacent backend integration surfaces if session bootstrap requires explicit support

## Implementation Tasks

1. Define the Portainer workspace route under the integrations cluster.
2. Document the controlled entry and session-continuity strategy for Portainer.
3. Implement the embedded workspace shell with loading, healthy, degraded, and failed states.
4. Surface actionable reason summaries and recovery directions when Portainer bootstrap fails.
5. Keep the Portainer workspace aligned with the shared integration-card and route conventions.

## Testing Requirements

- Verify a healthy Portainer workspace can be opened from inside the shared shell.
- Verify default entry does not force repeated manual login through a raw external page.
- Verify degraded or failed Portainer access produces explicit, non-blank UI states.
- Verify bilingual state copy covers loading, degraded, failure, and recovery guidance.

## Definition of Done

- A stable Portainer workspace route exists under the product shell.
- The Portainer entry strategy preserves session continuity inside the Websoft9 origin.
- Portainer degraded and failure states are visible and recoverable.
- The resulting workspace can later adopt Story 2.5 shared failure components without route redesign.

## Source Notes

- Primary sources: Epic 2 Portainer acceptance criteria, architecture integration workspace strategy, UX degraded-state requirements, current product runtime Portainer gateway surface.

## Tasks / Subtasks

- [x] Define the Portainer workspace route under the integrations cluster.
- [x] Document and encode the controlled Portainer entry and continuity detection strategy.
- [x] Implement the embedded workspace shell with loading, healthy, degraded, and failed states.
- [x] Surface actionable reason summaries and recovery directions when Portainer bootstrap fails.
- [x] Keep the Portainer workspace aligned with the shared integration-card and route conventions.

## Dev Agent Record

### Debug Log References

- Mapped the Portainer workspace to the product-owned `/w9deployment/` route inside the shared integrations cluster.
- Added the primary shell-level containers route and mapped it to the same product-owned `/w9deployment/` workspace path.
- Added probe heuristics and status rendering so Portainer bootstrap/auth surfaces no longer look like healthy embedded workspaces.
- Added retry and diagnostics entry points so Portainer failures remain actionable from inside the shell.
- Reused the shared route, card, and state model rather than creating Portainer-specific UI conventions.

### Completion Notes List

- Portainer now has a dedicated containers workspace route under the Websoft9 shell.
- Failure and degraded states are explicit and routed through the same product-owned recovery surface.
- The resulting workspace remains compatible with later shared-failure normalization without route redesign.

### File List

- console/src/app/router/index.tsx
- console/src/features/integrations/integration-model.ts
- console/src/features/integrations/use-integration-status.ts
- console/src/features/integrations/integrations-page.tsx
- console/src/features/integrations/integration-workspace-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: Implemented the Portainer embedded workspace, continuity detection, and recovery UX for Story 2.3.
- 2026-04-22: Promoted the Portainer workspace to the primary containers navigation entry while retaining the shared compatibility route.