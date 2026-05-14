# Story 3.3A: Build the custom compose upload and editing workspace

## Status

review

## Story

As an operator installing a non-catalog application,
I want to upload or edit Docker Compose content inside Websoft9,
so that I can deploy custom applications without leaving the product shell.

## Acceptance Criteria

1. Given the user selects custom compose installation, when the installation workspace opens, then the UI supports either uploading a compose file or editing compose content inline, and the flow clearly separates compose content, environment inputs, and install metadata.
2. Given the compose content changes, when the user requests validation, then the backend validates syntax and returns actionable errors, and the frontend does not attempt to parse or enforce Docker Compose policy on its own.

## Dependencies

- Story 3.2 already established the detail-first App Store install surface and the current installation parameter modal rhythm.
- Story 3.3 already established the installation task loop, accepted install-tracking identity, and the My Apps handoff expectation.
- PRD FR-APP-002 and FR-APP-002A now extend the install model from marketplace-only to a unified installation domain with custom compose as a first-class source.
- Architecture now requires AppHub to own one normalized installation surface and keep compose parsing or policy enforcement behind AppHub-owned APIs.

## Previous Story Intelligence

- The current install UX already routes accepted installs into My Apps instead of trapping success feedback inside the App Store. The custom compose workspace should plug into that same continuity model instead of inventing a one-off wizard disconnected from My Apps.
- Existing App Store work already preserves the legacy browse-detail-install rhythm. The compose workspace should feel like an extension of that product shell, not a raw Docker authoring tool.
- Story 3.3 intentionally kept long-running install feedback backend-owned. Story 3.3A must keep the same discipline: frontend owns authoring and validation request orchestration, not host execution or local compose interpretation.

## Developer Context

- Product sources now define three install-source types: marketplace template, custom compose, and runtime-source deployment. Story 3.3A is the first frontend slice for the second source type.
- The frontend stack remains React 19.2, React Router v7, Material UI 9.0.0, TanStack Query 5.99.2, and Zustand 5.0.12. Use the existing App Store feature structure and shared bilingual resource model instead of creating a parallel console surface.
- The install-domain architecture requires source-specific payloads to enter through AppHub-owned APIs, then normalize into one `installation_spec`. That means the UI may show source-specific forms, but it must not become the source of truth for compose semantics or policy rules.
- PRD scope explicitly allows Phase 1 to start with single-file compose while leaving room for future env-file and multi-file expansion. The first workspace should therefore keep its state model extensible even if the initial submit path only uses one compose document plus environment key/value input.
- Security requirements explicitly reject unrestricted host-path mounts, privileged mode, and unsupported network modes unless later product policy allows them. Story 3.3A must surface backend validation results clearly, but must not hardcode a partial policy copy in the browser.

## Implementation Guardrails

- Keep AppHub as the only public contract boundary. Frontend can upload compose content and request validation, but it must not run its own compose parser or try to implement authoritative policy logic.
- Preserve the existing App Store / My Apps continuity. Custom compose entry should still terminate in the same install task model and My Apps classification path used by marketplace installs.
- Separate authoring concerns in the UI: compose content, environment inputs, and install metadata such as app name, access domain, and install source label should not be mixed into one large freeform textarea.
- The first slice may use a textarea-based editor if needed, but the state model must leave room for future file upload, env-file attachment, and richer diagnostics anchoring.
- Bilingual resources belong in the existing shell resource bundle. Do not create a story-local translation island.
- Do not introduce browser-side file-system access, host command execution, or Docker daemon coupling.

## Suggested File Targets

- console/src/features/app-store/app-store-page.tsx
- console/src/features/app-store/
- console/src/shared/i18n/resources.ts
- console/src/shared/design-system/
- apphub/src/api/v1/routers/app.py
- apphub/src/schemas/
- docs/api-contracts-apphub.md

## Implementation Tasks

1. Add an install-source chooser or equivalent custom-compose entry within the existing App Store installation flow. (AC: 1)
2. Build the custom compose authoring workspace with compose upload or inline editing, install metadata, and environment input separation. (AC: 1)
3. Add backend-driven validation requests and actionable error rendering for compose syntax or source-shape problems. (AC: 2)
4. Keep successful validation and submission aligned with the existing install task loop and My Apps handoff instead of a one-off modal result. (AC: 1, 2)
5. Keep the authoring model extensible for future env-file and multi-file compose expansion without requiring a redesign of the visible UX contract. (AC: 1)

## Testing Requirements

- Run npm run typecheck in console after the frontend slice is added.
- Run npm run build in console to verify routing, resources, and App Store integration still compile.
- Add focused frontend tests or component-level validation for source-type switching, upload/edit toggles, and validation error rendering if the current test harness supports them.
- Validate in the live product container that the custom compose workspace opens inside the existing App Store install path and does not break marketplace installation.

## Definition of Done

- The product shell exposes a custom compose installation entry that feels native to the current App Store flow.
- Operators can either upload a compose file or edit compose content inline in the first-version workspace.
- Compose content, environment inputs, and install metadata are clearly separated in the UI.
- Validation is backend-driven and returns actionable errors without frontend-owned compose policy enforcement.
- The workspace hands off into the existing install task model rather than inventing a second install-feedback loop.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/epics.md Story 3.3A, _bmad-output/planning-artifacts/prd.md FR-APP-002 and FR-APP-002A, _bmad-output/planning-artifacts/architecture.md Installation Domain Architecture and API Strategy sections.
- Continuity references: _bmad-output/implementation-artifacts/3-3-build-the-installation-task-loop.md, console/src/features/app-store/app-store-page.tsx, console/src/features/my-apps/.

## Tasks / Subtasks

- [ ] Add the custom compose source entry to the current installation flow. (AC: 1)
  - [ ] Define where custom compose lives relative to the marketplace detail/install surface.
  - [ ] Keep the source-selection contract compatible with later runtime-source deployment.
- [ ] Build the authoring workspace. (AC: 1)
  - [ ] Support inline compose editing.
  - [ ] Support compose file upload.
  - [ ] Separate install metadata and environment input from compose body content.
- [ ] Add validation orchestration and error presentation. (AC: 2)
  - [ ] Send validation requests to AppHub-owned endpoints.
  - [ ] Render field-, service-, or directive-scoped feedback from backend diagnostics.
- [ ] Preserve install continuity. (AC: 1, 2)
  - [ ] Submit through the existing task-oriented install path.
  - [ ] Keep the My Apps handoff and install-source classification path intact.

## Dev Notes

### Architecture Compliance

- Flexible installation is one normalized installation domain, not three disconnected products. This story only adds the compose authoring surface for one source type.
- AppHub stays the only public API boundary. Compose parsing, normalization, and policy enforcement may use helper services internally, but the browser must only talk to AppHub.
- Frontend state should remain feature-local plus TanStack Query driven. Avoid new global stores unless the install-source switch truly needs cross-route coordination.

### UX Notes

- The first version should optimize operator clarity, not raw editor sophistication. A good textarea plus upload path and structured metadata will beat an over-engineered in-browser compose IDE.
- Actionable validation means the operator should be able to tell whether a problem belongs to syntax, a specific service block, or an unsupported directive.
- The workspace should look like an extension of the App Store and not like a detached Docker management page.

### API / Contract Notes

- The first frontend slice likely needs at least one validation endpoint and one install submission shape that carries `installation_source=compose`.
- Submission should remain compatible with the Story 3.3 task-loop contract so install progress can still be tracked through My Apps.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-13: Story created to define the development-ready frontend slice for custom compose authoring inside the unified installation model.
- 2026-05-13: Added a native App Store custom compose workspace with separated install metadata, environment rows, inline YAML authoring, and compose file upload.
- 2026-05-13: Added AppHub-owned compose validation schema, service, route, and focused unit tests; live product validation passed through the running product container.
- 2026-05-13: Install execution handoff remains intentionally deferred to Story 3.3B so this slice stays limited to authoring and backend validation.

### File List

- _bmad-output/implementation-artifacts/3-3a-build-the-custom-compose-upload-and-editing-workspace.md
- apphub/src/api/v1/routers/app.py
- apphub/src/schemas/appComposeInstall.py
- apphub/src/services/compose_install.py
- apphub/tests/test_app_compose_install.py
- console/src/features/app-store/app-store-page.tsx
- console/src/shared/i18n/resources.ts
- docs/api-contracts-apphub.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-05-13: Created Story 3.3A and advanced sprint tracking to ready-for-dev for the custom compose authoring workspace.
- 2026-05-13: Implemented the compose authoring workspace and AppHub validation endpoint, and advanced the story to review.