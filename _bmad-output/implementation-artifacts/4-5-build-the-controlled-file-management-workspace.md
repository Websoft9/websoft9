---
title: 'Story 4.5: Build the controlled file-management workspace'
type: 'feature'
created: '2026-04-29'
status: 'review'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `files` module is still a protected shell placeholder. Operators need day-to-day file management for Docker volumes, but they should not have to understand host mount configuration, Docker data-root layout, or manual authorization steps just to upload, download, create, delete, or open files.

**Approach:** Replace the `files` placeholder with a product-native workspace that behaves like a standard file manager while using Docker volumes as the logical root. Reuse the existing product-auth boundary and AppHub Docker access, keep host paths hidden from the browser, and execute volume file operations through a long-lived internal `files-agent` process inside the single product container. Before approving any full rewrite, explicitly assess whether Cockpit file-management assets or a scoped third-party React file manager can be reused behind a product-owned API boundary.

## Boundaries & Constraints

**Always:** Present the UI as a standard file manager rooted at logical Docker volumes instead of the full host tree; preserve the existing product-auth route and session boundary for the `files` module; keep FastAPI AppHub as the only backend API surface; hide host absolute paths from the browser; support browse, upload, download, create, rename, delete, and basic text editing inside approved volume scopes; keep bilingual shell-resource patterns.

**Ask First:** Expanding to arbitrary host-path browsing; adding archive extraction, permission editors, binary diff tools, or full IDE behavior; introducing a second auth model; letting the browser connect directly to Docker, Portainer, or the host filesystem; shipping a third-party component that cannot be constrained to the approved volume-root model.

**Never:** Expose the full host file tree; bypass product-auth for file actions; let client-provided paths escape the approved root by `..`, symlink traversal, or mount aliasing; require operators to hand-configure host bind mounts or direct `/var/lib/docker/volumes` access; couple file access to Cockpit sessions or Linux accounts; make Portainer or Cockpit the new long-term file API of record.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LIST_VOLUME_ROOT | Authenticated operator opens `files` route | UI shows a standard file-manager root populated with approved Docker volumes instead of host directories | Return stable auth/config errors if no approved volume root can be resolved |
| BROWSE_DIRECTORY | Operator selects an approved volume or subdirectory | Directory contents load with path breadcrumbs that never leave the approved boundary | Reject escaped or unknown paths with stable 4xx response |
| FILE_MUTATION | Operator creates, renames, edits, or deletes an item inside an approved directory | Mutation succeeds and refreshed listing reflects the authoritative backend state | Reject name collisions, invalid names, protected paths, and write attempts outside allowed roots |
| FILE_TRANSFER | Operator uploads or downloads a file within an approved scope | Transfer completes inside the selected boundary and UI shows success feedback | Reject oversize, disallowed target, and incomplete transfer states with explicit reason |
| TEXT_EDIT | Operator opens a supported text file for inline editing | Workspace loads text content, saves changes through AppHub, and does not treat binary files as editable text | Reject unsupported encodings, large text payloads, or binary content with clear fallback messaging |
| FILE_AGENT_EXECUTION | AppHub needs to act on a target volume | Backend delegates the file operation to a long-lived internal `files-agent` process scoped to approved volume roots inside the single product container | Surface stable backend errors if the in-container process is unavailable, the delegated operation fails, or the internal channel breaks |
| SYMLINK_ESCAPE_GUARD | Listed item is a symlink or path alias that points outside approved roots | API refuses traversal beyond the canonical approved root and surfaces boundary violation | Return stable 4xx error and keep current directory state unchanged |
| DOCKER_ROOT_CHANGED | Host Docker data-root is not `/var/lib/docker/volumes` | Backend still resolves the volume through Docker metadata and helper-container mount wiring | Do not rely on hard-coded Docker root paths; return infrastructure error only if Docker cannot resolve the volume |
| CONCURRENT_CHANGE | Another process mutates the same file between list and save | UI refreshes authoritative state and surfaces conflict or missing-target result | Avoid silent overwrite if backend can detect stale metadata; otherwise return latest-state failure |

</frozen-after-approval>

## Code Map

- `console/src/app/router/index.tsx` -- current `files` route now points to the native workspace and remains the switching point for any follow-on in-container file-agent refactor.
- `console/src/app/shell/shell-navigation.ts` -- shell navigation already reserves `files` as a top-level product module.
- `console/src/shared/i18n/resources.ts` -- current shell copy already contains the native file-workspace strings and remains the place to evolve file-agent status, errors, and feedback text.
- `console/src/features/product-auth/product-auth-route-guard.tsx` -- existing protection boundary that must remain in front of the file workspace.
- `console/src/features/users/users-page.tsx` -- current native protected-module pattern for request helpers, dialogs, feedback, and list refresh.
- `apphub/src/services/app_manager.py` -- existing Docker SDK access and app/volume metadata helpers that can seed approved volume enumeration.
- `apphub/src/services/back_manager.py` -- existing helper-container style Docker execution patterns that can inform volume file-operation execution.
- `apphub/src/services/product_auth.py` -- current product-owned auth/session boundary and protected-module policy that the files API must reuse.
- `apphub/src/api/v1/routers/backup.py` -- current focused router pattern for mount-related operations; useful baseline for a new file-management router.
- `apphub/src/main.py` -- router registration point for any new file-management API surface.

## Tasks & Acceptance

**Execution:**
- [x] Brownfield reuse assessment -- documented prior reuse findings from Cockpit asset exploration and third-party React file-manager evaluation; final implementation keeps the API/product boundary native and leaves any future widget reuse replaceable.
- [x] `apphub/src/schemas/` -- add file-management DTOs for volume listing, directory listing, file metadata, upload/download descriptors, text-edit payloads, and mutation responses.
- [x] `apphub/src/services/` -- implement a product-owned file-management service that enumerates approved Docker volumes, canonicalizes relative paths, blocks escape attempts, and performs the required file actions.
- [x] `apphub/src/services/` -- implement the initial helper-container execution layer that mounts the selected target volume into a temporary workspace path for file operations, then tears the helper down.
- [x] `apphub/src/services/` -- replace the ephemeral helper-container execution layer with a long-lived internal `files-agent` process inside the single product container while preserving AppHub as the only public API and auth boundary.
- [x] `apphub/src/api/v1/routers/` and `apphub/src/main.py` -- expose authenticated endpoints for volume-root list, directory list, upload, download, create, rename, delete, and basic text edit/save flows under AppHub; frontend contracts must use `volumeId` + relative path instead of host absolute paths.
- [x] `apphub/tests/` -- add focused regression coverage for approved-volume resolution, path canonicalization, escaped-path rejection, helper-container execution failure handling, text-vs-binary edit rules, and mutation success cases.
- [x] `console/src/features/files/` -- create a native file-management page that behaves like a standard file manager rooted at logical Docker volumes, with directory contents, action toolbar, and inline text editing for supported files.
- [x] `console/src/app/router/index.tsx` -- route `files` to the native page while preserving `ProductAuthRouteGuard` behavior.
- [x] `console/src/shared/i18n/resources.ts` -- replace placeholder copy with bilingual file-workspace labels, empty states, errors, dialogs, and action feedback.

**Acceptance Criteria:**
- Given the user opens file management, when the page loads, then the UI behaves like a standard file manager rooted at approved Docker volumes instead of the full host tree.
- Given the user uploads, downloads, creates, renames, edits, or deletes files, when the action completes, then the operation stays inside the selected volume boundary and the system does not expose host absolute paths or require manual mount authorization.
- Given a file path, symlink, or alias would resolve outside the approved root, when AppHub validates the request, then the action is rejected with a stable client-facing error instead of traversing outside the boundary.
- Given the backend needs to operate on a selected volume, when AppHub performs the action, then the actual file operation is executed through a long-lived internal `files-agent` process inside the single product container rather than by exposing `/var/lib/docker/volumes` directly to the browser or launching an ephemeral helper container per request.
- Given the selected file is not a supported text-edit target, when the user attempts inline editing, then the UI does not treat it as editable text and instead offers an appropriate non-edit fallback such as metadata-only display or download.

## Spec Change Log

- 2026-04-29: Story context updated to a standard file-manager UX rooted at logical Docker volumes, with AppHub and helper containers hiding host mount and authorization complexity from the user.
- 2026-04-30: Correct-course update approved. Story 4.5 is reopened so the helper-container execution layer can be replaced with a long-lived internal `files-agent` execution layer.
- 2026-04-30: Implemented the internal `files-agent` migration. AppHub now calls a localhost files agent instead of launching one helper container per request.
- 2026-04-30: Final runtime alignment completed. The `files-agent` now runs as a supervisor-managed process inside `websoft9-product-current`, and the temporary extra files-agent container has been removed.
- 2026-04-30: Runtime mount handling was aligned with Docker metadata instead of a fixed host path. The sync/recreate flow now detects the current Docker data-root dynamically, binds the resolved volumes root into the product container, passes it to `files-agent` through environment configuration, and keeps the browser-facing workspace rooted at the virtual `/volumes` path instead of exposing host absolute paths or `_data` segments.

## Design Notes

The hard problem in this story is still boundary enforcement, not the tree widget. Frontend reuse is acceptable only if the component can consume a product-owned API that already resolved approved volumes and canonical paths. Prefer a thin FastAPI service over a separate public file server. The implementation split should be: AppHub owns approved-volume discovery, authentication, canonical path policy, and audit; the internal `files-agent` process owns low-level file operations inside approved roots; the console owns browsing and action UX; any third-party file-manager widget remains replaceable infrastructure rather than the authority on security rules.

This story intentionally avoids forcing an app-first navigation model. Users should be able to manage files through a familiar file-manager surface, while the backend still filters which volumes are visible and keeps host paths hidden. Text editing should remain intentionally basic and exclude large or binary payloads. The in-container `files-agent` is an internal execution dependency only; it must not become a second user-facing backend or bypass AppHub policy enforcement.

The current runtime still requires the product container to have access to the host Docker volumes root because `files-agent` performs real filesystem operations inside approved volume roots. The difference is operational ownership: operators should not hand-configure that bind or assume `/var/lib/docker/volumes`; the product sync/recreate flow should discover Docker's active root path and inject the matching bind automatically.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_product_auth.py` -- reference auth boundary baseline that the files module must preserve when implemented
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_file_manager.py` -- validate the backend file-management routes, auth boundary, path-escape guard, and core mutations
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/main.py src/api/v1/routers/files.py src/services/file_manager.py src/schemas/fileManager.py` -- compile-check the touched AppHub file-management slice
- `cd /workspace/websoft9/console && npm run typecheck` -- validate the native files page, route wiring, and i18n resources
- `cd /workspace/websoft9/console && npm run build` -- validate the files page through the production frontend build pipeline
- After the in-container `files-agent` migration: rerun the file-management slice validation against the new internal execution path and refresh any tests that currently assume ephemeral helper-container startup.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Created and refined the Story 4.5 implementation artifact for a product-native files module that uses a standard file-manager UX over logical Docker volumes.
- Captured the key guardrails: product-auth reuse, AppHub as the single backend, host paths hidden from the browser, helper-container execution for volume operations, and mandatory brownfield reuse assessment before a full rewrite.
- Anchored the story to existing console and AppHub implementation surfaces so the next dev pass can start from concrete code paths instead of placeholders.
- Moved Story 4.5 to `ready-for-dev` in sprint tracking.
- Implemented the AppHub file-management backend, including volume enumeration, canonical path enforcement, the initial helper-container-based file operations, and product-auth-protected routes.
- Replaced the protected `files` placeholder with a native console file manager that supports volume switching, directory browsing, inline text editing, and core file actions.
- Updated the main AppHub auth gate so `/api/files/*` remains protected by product-auth rather than the x-api-key flow.
- Validated the slice with focused backend tests, Python compile checks, console typecheck, and a production frontend build.
- Reopened Story 4.5 after architecture correction selected a long-lived internal `files-agent` execution layer as the accepted target.
- Replaced the helper-container execution path with an internal `files-agent` client and service contract while preserving the existing AppHub `/api/files/*` surface.
- Finalized the runtime as a single product container by adding the Docker volumes bind to `websoft9-product-current`, starting `files-agent` under supervisor, and deleting the temporary extra files-agent container.
- Revalidated the backend slice with `pytest -q -o addopts='' tests/test_file_manager.py`, rebuilt and synced the live product, and confirmed the in-container root browse path in the running container with root-directory latency around 17-24 ms.
- Updated the files workspace presentation to use the virtual `/volumes` root in the browser so the UI no longer exposes host Docker paths or `_data` implementation details.
- Left the story in `review` because authenticated end-to-end browser validation of the protected files UI still requires an operator login session in the live environment.

### File List

- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace.md
- _bmad-output/implementation-artifacts/4-5-build-the-controlled-file-management-workspace_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/main.py
- apphub/src/api/v1/routers/files.py
- apphub/src/files_agent.py
- apphub/src/schemas/fileManager.py
- apphub/src/services/file_manager.py
- apphub/tests/test_file_manager.py
- console/src/app/router/index.tsx
- console/src/features/files/files-page.css
- console/src/features/files/files-page.tsx
- console/src/shared/i18n/resources.ts
- scripts/sync_websoft9_product_current.sh

### Change Log

- 2026-04-29: Created the Epic 4 Story 4.5 BMAD artifact and advanced sprint tracking to ready-for-dev.
- 2026-04-29: Implemented the initial Story 4.5 backend and frontend file-management slice, completed automated review/fix validation, and recorded focused validation coverage.
- 2026-04-30: Reopened Story 4.5 through Correct Course after accepting the internal `files-agent` runtime direction as the new execution-layer target.
- 2026-04-30: Replaced the helper-container execution layer with the internal `files-agent` path, then finalized the live runtime as a single-container supervisor-managed process model and advanced the story to review.
- 2026-04-30: Replaced the fixed `/var/lib/docker/volumes` runtime assumption with dynamic DockerRootDir detection during product-container recreation, and aligned the browser-visible root label to `/volumes`.