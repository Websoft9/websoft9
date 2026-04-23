# Story 2.5: Handle Integration Failures and Degraded States Consistently

## Status

in-progress

## Story

As an operator relying on embedded integrations,
I want failure and degraded integration states to be explicit,
so that I understand whether the problem is availability, configuration, or session continuity.

## Acceptance Criteria

1. Any failed, degraded, or misconfigured integration clearly labels the state and cause summary on the card or workspace surface.
2. Each failure surface provides a stable recovery or diagnostics entry point.
3. If one integration fails while others remain healthy, unaffected workspaces remain usable.
4. One broken integration does not collapse the full integrations surface.

## Dependencies

- Stories 2.2, 2.3, and 2.4 define the per-integration workspace contracts.
- Story 2.1 defines the landing cards and initial shared state model.

## Previous Story Intelligence

- UX explicitly requires degraded and failure states to be clear, recoverable, and non-silent across third-party workspaces.
- Architecture favors product-owned workspaces and controlled integration boundaries, which implies Websoft9 must own state explanation rather than delegating all failure behavior to upstream UIs.
- Earlier migration notes warn against allowing one broken bridge to redefine the overall product experience.

## Developer Context

- This story is the normalization layer for Epic 2. It should consolidate state naming, diagnostics entry, and recovery affordances across Gitea, Portainer, and NPM.
- The existing shell and integrations landing route provide the correct surface for card-level and workspace-level consistency.
- The backend and gateway already expose multiple health and routing boundaries; this story should define how those signals become user-facing state rather than inventing a second observability model.
- The result should stay compatible with Epic 4 observability stories without waiting for them.

## Implementation Guardrails

- Do not let each integration invent its own unrelated error semantics.
- Do not rely on blank frames, browser console errors, or raw upstream pages as the primary failure explanation.
- Do not force a full integrations-page outage when only one workspace is unhealthy.
- Keep state and recovery affordances simple enough to reuse in cards and workspace shells.
- Preserve the separation between session failure, configuration failure, and service availability failure.

## Suggested File Targets

- `console/src/features/integrations/`
- `console/src/shared/components/`
- `console/src/shared/i18n/`
- `apphub/src/api/`
- `docker/product/gateway/`

## Implementation Tasks

1. Define the canonical integration-state taxonomy used across cards and workspace pages.
2. Create shared UI patterns for degraded, failed, unavailable, and misconfigured states.
3. Define a common diagnostics and retry-entry contract that each integration can supply.
4. Ensure partial failure isolation so one broken integration does not collapse healthy ones.
5. Align user-facing copy and state semantics across English and Chinese.

## Testing Requirements

- Verify each supported integration can show explicit degraded or failed state copy.
- Verify one failing integration does not block access to healthy integration workspaces.
- Verify the shared diagnostics or retry surface can be invoked from both card and workspace contexts.
- Verify the failure taxonomy distinguishes service availability, configuration, and session continuity problems.

## Definition of Done

- Epic 2 has one shared failure and degraded-state contract across all integrations.
- Cards and workspace pages use the same state vocabulary and recovery pattern.
- Partial failures are isolated so healthy integrations remain usable.
- Later observability work can extend diagnostics without replacing the Epic 2 failure contract.

## Source Notes

- Primary sources: Epic 2 failure-handling acceptance criteria, architecture integration-boundary strategy, UX degraded-state and recoverability requirements.

## Tasks / Subtasks

- [x] Define the canonical integration-state taxonomy used across cards and workspace pages.
- [x] Create shared UI patterns for degraded, failed, unavailable, misconfigured, and session-continuity states.
- [x] Define a common diagnostics and retry-entry contract that each integration can supply.
- [x] Ensure partial failure isolation so one broken integration does not collapse healthy ones.
- [x] Align user-facing copy and state semantics across English and Chinese.

## Dev Agent Record

### Debug Log References

- Centralized the integration-state taxonomy in a shared model and probe hook.
- Added shared card and workspace state rendering for loading, available, unavailable, configuration-error, and session-error outcomes.
- Added shared retry and diagnostics entry points so recovery is actionable from inside the shell.
- Reused the same shared failure contract after promoting repository, containers, and gateway to first-class shell navigation entries.
- Kept healthy integrations independently usable because each workspace route and card renders from its own snapshot rather than a global failure gate.

### Completion Notes List

- Epic 2 now has one shared integration-state contract across cards and embedded workspaces.
- Session continuity, configuration failure, and service availability failures are no longer collapsed into one generic state.
- The same failure contract now survives both the compatibility catalog and the new first-class repository, containers, and gateway shell entries.
- Partial failures remain isolated, so one broken integration does not take down the entire integrations surface.

### File List

- console/src/app/router/index.tsx
- console/src/features/integrations/integration-model.ts
- console/src/features/integrations/use-integration-status.ts
- console/src/features/integrations/integrations-page.tsx
- console/src/features/integrations/integration-workspace-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-22: Implemented the shared integration failure taxonomy, diagnostics entry points, and bilingual recovery UX for Story 2.5.
- 2026-04-22: Confirmed the shared failure contract remains intact after promoting Epic 2 workspaces to first-class shell navigation entries.