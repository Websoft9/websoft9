# Story 4.5: Build the controlled file-management workspace

## Status

ready-for-dev

## Story

As an operator maintaining current-host files and application-specific volumes,
I want Websoft9 to provide both a controlled current-host file workspace and preserved app-detail volume browsing,
so that I can manage real host files without exposing raw SSH/SFTP access to the browser while still browsing the current app's volumes from its detail page.

## Acceptance Criteria

1. Given the user opens host file management for the first time, when no current-host authorization is bound yet, then Websoft9 requests one current-host SSH authorization flow and reuses it for later file operations.
2. Given the user browses, uploads, downloads, creates, renames, edits, or deletes host files, when the action completes, then AppHub performs the operation through a product-owned SFTP bridge to the current host and the browser never receives direct SSH/SFTP connectivity.
3. Given the user opens file browsing from the current application's detail surface, when the target is one of that application's managed volumes, then Websoft9 preserves the existing volume-scoped file capability through AppHub-owned APIs instead of replacing it with unrestricted host browsing.

## Dependencies

- Story 4.3 already established the product-auth boundary that should protect host-sensitive capability.
- Story 4.6 will own the unified terminal-first host workspace shell, but Story 4.5 owns the current-host file bridge and must remain usable through the existing files menu until the shell consolidation is complete.
- My Apps and application-detail surfaces still need volume-scoped file browsing for the selected application, and Story 4.5 must preserve that capability instead of collapsing everything into host browsing.
- PRD FR-FILE-001 and FR-TERM-001 now align on one current-host SSH/SFTP bridge model where host permissions derive from the bound SSH user.
- Architecture now defines AppHub as the only public API boundary for both terminal and file bridges, with SSH PTY for terminal and short-lived SFTP sessions for file operations.

## Previous Story Intelligence

- The old Story 4.5 implementation targeted Docker-volume browsing through an in-container bridge. That implementation is no longer the accepted baseline for the next development slice.
- Product-auth already protects files and terminal. The new file bridge should extend that boundary instead of inventing another credential surface.
- The user direction is to keep the current files menu temporarily while terminal becomes the host-workspace design surface. Story 4.5 therefore focuses on the shared host bridge plus file capability, not on the final navigation cleanup.
- The already-implemented application-volume file capability remains valid for app detail views and should be reused rather than removed.

## Developer Context

- The target host is only the current Websoft9 host in this phase. Do not introduce a multi-server inventory model.
- Browser clients must never connect to SSH or SFTP directly. AppHub owns all public HTTP and WebSocket contracts.
- The shared host-access model is one bound SSH profile for the current host. Terminal and files reuse that profile.
- The host user may be non-root. Host permissions derive from the bound SSH account, and Websoft9 must not add a second shell/file permission model on top.
- The current files route remains in place as a compatibility entry during this slice. The host-workspace convergence lands gradually through the terminal route and Story 4.6.
- Application detail remains a second file-entry surface, but it is volume-scoped to the current app rather than host-scoped.

## Implementation Guardrails

- Keep FastAPI AppHub as the only public API boundary.
- Use SSH/SFTP to the current host; do not require an extra host agent installation.
- Do not expose browser-direct SSH/SFTP credentials, host sockets, or unrestricted host filesystem access.
- Keep the first-run authorization model shared with terminal so the operator authorizes once and reuses it across host-access features.
- Keep path handling explicit and safe. Even if the host file tree is broader than the old Docker-volume scope, AppHub still owns any locked-root or recommended-root policy.
- Do not regress the already-implemented application-volume browser in My Apps or application detail; preserve it as a volume-scoped capability with AppHub remaining the only public API boundary.
- The existing files menu may remain temporarily, but the story should avoid baking a second long-term UX model separate from the unified host workspace.

## Suggested File Targets

- console/src/features/files/
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/
- apphub/src/services/
- apphub/src/schemas/
- apphub/tests/
- scripts/sync_websoft9_product_current.sh

## Implementation Tasks

1. Define and persist the current-host SSH authorization contract that file management reuses with terminal. (AC: 1)
2. Implement AppHub-owned SFTP file operations for the current host, including list, read, write, upload, download, create, rename, and delete. (AC: 2)
3. Preserve and adapt the existing application-detail volume file capability so operators can still browse the current app's managed volumes through AppHub-owned APIs. (AC: 3)
4. Replace the files route's Docker-volume-specific assumptions with current-host bridge behavior while preserving product-auth protection. (AC: 1, 2)
5. Keep the current files route usable as a temporary compatibility entry until the unified host workspace cleanup lands. (AC: 1, 2)
6. Record enough bridge and file-operation metadata for later diagnostics and audit continuity. (AC: 2, 3)

## Testing Requirements

- Add focused backend tests for SSH authorization validation, SFTP connection failure handling, file operation success/failure cases, browser-hidden credential behavior, and preserved app-volume file browsing behavior.
- Add tests for non-root SSH users so host permissions clearly derive from the bound SSH account.
- Run targeted pytest and Python compile validation for touched AppHub modules.
- Run console typecheck/build validation for the touched host-file UI slice.
- Validate in the live product container that the browser talks only to AppHub while AppHub performs SFTP operations against the current host.

## Definition of Done

- Websoft9 can bind one current-host SSH authorization profile for file access.
- Host file operations execute through AppHub-owned SFTP calls rather than browser-direct SSH/SFTP.
- The current files route remains usable as a compatibility entry during the convergence period.
- My Apps or application-detail surfaces still expose volume-scoped file browsing for the selected application.
- Host permissions for file actions derive from the bound SSH user.
- The story leaves a clean handoff into the unified host workspace shell owned by Story 4.6.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/epics.md Story 4.5, _bmad-output/planning-artifacts/prd.md FR-FILE-001 and FR-TERM-001, _bmad-output/planning-artifacts/architecture.md Authentication & Security, API & Communication, and Implementation Sequence sections.
- Reference pattern: Websoft9/AppOS current-host access model, where terminal uses SSH PTY and files use SFTP behind backend-owned routes.

## Tasks / Subtasks

- [ ] Define shared current-host authorization for file access. (AC: 1)
  - [ ] Add DTOs and storage for the current-host SSH profile.
  - [ ] Reuse the same authorization surface planned for terminal.
- [ ] Implement current-host SFTP file operations in AppHub. (AC: 2)
  - [ ] List and inspect host paths.
  - [ ] Read and write text files.
  - [ ] Upload, download, create, rename, and delete files.
- [ ] Preserve application-detail volume file browsing. (AC: 3)
  - [ ] Reuse the existing volume-scoped file APIs and UI where practical.
  - [ ] Keep the scope limited to the selected application's managed volumes.
- [ ] Reframe the existing files route around the host bridge. (AC: 1, 2)
  - [ ] Remove Docker-volume-specific assumptions from the next implementation slice.
  - [ ] Preserve product-auth and compatibility entry behavior.
- [ ] Add audit and diagnostics continuity. (AC: 2)
  - [ ] Record host file action metadata.
  - [ ] Return stable errors for SSH/SFTP failures and permission denials.

## Dev Notes

### Architecture Compliance

- AppHub owns the only public API. SSH and SFTP remain backend transport details.
- This story is intentionally current-host-only. Do not widen it into a generic multi-server file manager.
- The accepted direction is SSH/SFTP reuse for current-host browsing, while application-detail volume browsing remains a product-owned volume-scoped capability.

### UX Notes

- The current files menu remains temporarily, but the UX copy should acknowledge the current host and the shared authorization state.
- The final menu convergence is not blocked on this story. Avoid coupling the file bridge to the final navigation cleanup.

### Security Notes

- SSH credentials must stay server-side only.
- Host permissions derive from the bound SSH user, including non-root users.
- Browsers must not receive a reusable SFTP endpoint, host socket, or raw secret material.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-18: Story 4.5 was reframed from Docker-volume file management to current-host SSH/SFTP-backed file management and moved back to ready-for-dev.

### File List

- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace.md
- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace_cn.md
- _bmad-output/implementation-artifacts/4-6-build-the-controlled-terminal-bridge-and-session-audit.md
- _bmad-output/implementation-artifacts/4-6-build-the-controlled-terminal-bridge-and-session-audit_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-05-18: Reframed Story 4.5 around current-host SSH/SFTP host access and returned the story to ready-for-dev.
