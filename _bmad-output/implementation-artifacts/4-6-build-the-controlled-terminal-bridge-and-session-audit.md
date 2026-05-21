# Story 4.6: Build the controlled terminal bridge and session audit

## Status

ready-for-dev

## Story

As an operator performing advanced diagnostics on the current host,
I want a controlled terminal workspace with shared current-host authorization and session records,
so that I can access the host shell through Websoft9 while preparing the product to converge terminal and file access under one menu.

## Acceptance Criteria

1. Given the user opens the terminal workspace and no current-host authorization has been bound yet, when the authorization succeeds, then Websoft9 stores one current-host SSH authorization profile under the product-auth boundary and reuses it for later terminal and file access.
2. Given a terminal session starts, resizes, exits, or fails, when Websoft9 establishes the PTY session through the SSH bridge, then the browser talks only to an AppHub-owned WebSocket endpoint and the system records at least user, source, start time, and result.

## Dependencies

- Story 4.3 already established the product-auth boundary for protected modules such as terminal and files.
- Story 4.5 owns the current-host file bridge that will reuse the same host authorization profile.
- PRD FR-TERM-001 and FR-FILE-001 now explicitly allow one shared current-host SSH authorization model where host permissions derive from the bound SSH user.
- Architecture defines AppHub as the only public boundary, with terminal on SSH PTY over WebSocket and files on SFTP over REST.

## Previous Story Intelligence

- The existing terminal route is still a placeholder, so this story owns the first real host-workspace shell on that route.
- The user direction is to keep the current files menu temporarily and do the new host-workspace UI design in terminal first.
- Product-auth already protects terminal access. The new bridge should extend that protection rather than inventing a second login surface.

## Developer Context

- The target host is the current Websoft9 host only. Do not widen this story into a multi-host terminal broker.
- The host login user may be non-root. Shell permissions derive from the bound SSH account.
- Browser clients must never receive raw SSH credentials or direct SSH connectivity.
- The terminal route becomes the first host-workspace shell and should be designed to accommodate future file convergence without forcing an immediate navigation merge.
- Session audit in this slice is metadata-first: creation, disconnect, failure, and cleanup continuity matter more than deep command transcript capture.

## Implementation Guardrails

- Keep AppHub as the only public API and WebSocket boundary.
- Use SSH-backed PTY bridging for the current host; do not require an extra host agent installation.
- Reuse one current-host authorization profile across terminal and file capabilities.
- Keep the current files menu temporarily instead of forcing a same-story navigation migration.
- Record enough session metadata for audit and supportability without turning this slice into a full privileged session-recording platform.
- Handle resize, disconnect, idle cleanup, and failure paths explicitly.

## Suggested File Targets

- console/src/app/router/index.tsx
- console/src/app/shell/shell-navigation.ts
- console/src/features/terminal/
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/
- apphub/src/services/
- apphub/src/schemas/
- apphub/tests/

## Implementation Tasks

1. Define and persist the shared current-host SSH authorization profile under the product-auth boundary. (AC: 1)
2. Implement the AppHub-owned SSH PTY session bridge and WebSocket lifecycle for the current host. (AC: 2)
3. Replace the terminal placeholder with a terminal-first host workspace shell that can later converge with file access under one menu. (AC: 1, 2)
4. Record terminal session metadata for creation, resize, disconnect, failure, and cleanup outcomes. (AC: 2)
5. Expose enough authorization-state UX so the terminal workspace can guide first-run authorization without changing the existing files menu yet. (AC: 1)

## Testing Requirements

- Add focused backend tests for current-host authorization validation, SSH PTY connection handling, resize/disconnect behavior, and session metadata persistence.
- Add focused frontend tests if supported for terminal authorization states and workspace-shell rendering.
- Run targeted pytest and Python compile validation for touched AppHub modules.
- Run console typecheck/build validation for the terminal workspace slice.
- Validate in the live product container that terminal traffic flows through AppHub-owned WebSocket endpoints and that session metadata is recorded on start and close paths.

## Definition of Done

- Websoft9 can bind and reuse one current-host SSH authorization profile for terminal access.
- The terminal route no longer uses a placeholder and instead exposes a terminal-first host workspace shell.
- Terminal sessions run through AppHub-owned SSH PTY bridging over WebSocket.
- Session metadata is recorded for start, failure, disconnect, and cleanup outcomes.
- The resulting shell leaves a clean UX path for later menu convergence with host file access.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/epics.md Story 4.6, _bmad-output/planning-artifacts/prd.md FR-TERM-001 and FR-FILE-001, _bmad-output/planning-artifacts/architecture.md Authentication & Security and API & Communication sections.
- Continuity references: console/src/app/router/index.tsx, console/src/app/shell/shell-navigation.ts, apphub/src/services/product_auth.py.

## Tasks / Subtasks

- [ ] Define shared current-host authorization for terminal access. (AC: 1)
  - [ ] Add DTOs and persistence for the current-host SSH profile.
  - [ ] Reuse the same profile planned for host file access.
- [ ] Implement SSH PTY session bridging in AppHub. (AC: 2)
  - [ ] Establish the PTY-backed WebSocket session.
  - [ ] Handle resize, disconnect, and cleanup.
  - [ ] Return stable errors for SSH failures and permission denials.
- [ ] Replace the terminal placeholder with the host-workspace shell. (AC: 1, 2)
  - [ ] Add first-run authorization UX in terminal.
  - [ ] Keep room for future file convergence without forcing immediate menu removal.
- [ ] Record session audit metadata. (AC: 2)
  - [ ] Persist start and end outcomes.
  - [ ] Capture source and operator identity.

## Dev Notes

### Architecture Compliance

- AppHub owns the only public API. SSH PTY remains an internal transport detail.
- This story is current-host-only and should not widen into a generic remote-terminal product.
- The accepted direction is shared SSH authorization plus AppHub-owned bridging, not browser-direct shell access.

### UX Notes

- The terminal route is the first place to express the new host-workspace shell.
- The current files menu intentionally stays in place during this story, so the shell should acknowledge that convergence is staged.

### Security Notes

- Host shell permissions derive from the bound SSH user, including non-root users.
- Browser clients must not receive reusable SSH secrets.
- Audit scope in this story is session metadata, not a full keystroke-recording system.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-18: Created Story 4.6 as the ready-for-dev terminal-first host workspace slice with shared current-host authorization and session audit.

### File List

- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace.md
- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace_cn.md
- _bmad-output/implementation-artifacts/4-6-build-the-controlled-terminal-bridge-and-session-audit.md
- _bmad-output/implementation-artifacts/4-6-build-the-controlled-terminal-bridge-and-session-audit_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-05-18: Created Story 4.6 and advanced sprint tracking to ready-for-dev for the current-host terminal bridge and session audit slice.
