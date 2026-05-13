# Story 3.3B: Build backend validation and install execution for custom compose apps

## Status

ready-for-dev

## Story

As an operator deploying a custom stack,
I want Websoft9 to validate and normalize my compose deployment before execution,
so that unsafe or unsupported definitions fail early and valid definitions install through the standard task model.

## Acceptance Criteria

1. Given the user submits a custom compose installation request, when AppHub receives the request, then AppHub normalizes it into the shared installation domain model and applies product policy checks before creating deployment resources.
2. Given the compose request includes unsupported directives, when validation completes, then the install is rejected with actionable diagnostics, and no partial application resources are created.

## Dependencies

- Story 3.3 already established the first product-owned installation task loop and My Apps handoff contract.
- Story 3.3A defines the compose authoring entry and backend-driven validation UX, but Story 3.3B owns the real normalization, policy enforcement, and install execution path.
- PRD FR-APP-002A and security requirements explicitly require syntax validation, deployment normalization, policy validation, and rejection of unsafe directives before resources are created.
- Architecture now defines normalized installation objects: `installation_source`, `installation_spec`, `runtime_profile`, and `deployment_revision`.

## Previous Story Intelligence

- Existing installation logic already accepts marketplace installs, creates tracking identity, and surfaces in-progress state into My Apps. The compose path should extend that pipeline instead of adding a separate task subsystem.
- Current product work has repeatedly moved browser-owned logic back behind AppHub for security-sensitive flows. Compose validation is another case where backend ownership is mandatory.
- The new product direction is not “run arbitrary docker compose with best effort.” It is “accept compose as one install-source type, normalize it into a product-owned installation domain, then enforce policy before execution.”

## Developer Context

- Architecture requires flexible installation to be implemented as one normalized installation domain in AppHub rather than three disconnected install surfaces. Story 3.3B is the first backend story that operationalizes that architecture.
- The installation pipeline is explicitly defined as: accept source payload and install metadata, validate source-specific inputs, normalize to a shared install specification, apply policy checks, execute through the unified task model, then persist deployment summary for My Apps and lifecycle actions.
- Security requirements explicitly require rejection of unrestricted host-path mounts, privileged containers, and unsupported network modes unless later product policy introduces controlled exceptions.
- Phase 1 may start with single-file compose, but the backend model must leave room for env-file and later multi-file composition. Avoid designing DTOs or service boundaries that would force a breaking rewrite when additional compose artifacts are added.
- The current backend already owns install execution, task acceptance, and My Apps aggregation. Reuse those ownership boundaries and extend them rather than building a parallel compose executor with its own public API model.

## Implementation Guardrails

- AppHub is the only public contract boundary. If parsing, rendering, or execution helpers are introduced, they must remain internal dependencies.
- Validation must be deterministic and side-effect free until the request passes syntax checks, normalization, and product policy checks.
- No partial resource creation on validation failure. Container, network, volume, proxy, or My Apps records must not be left behind when a compose request is rejected.
- Diagnostics must be actionable. Backend errors should identify the affected field, service, or unsupported directive whenever practical.
- Keep the resulting deployment compatible with the existing task loop, install tracking, and My Apps classification path.
- Do not treat compose submission as a bypass around current product rules for access, proxy, or task ownership.

## Suggested File Targets

- apphub/src/api/v1/routers/app.py
- apphub/src/services/app_manager.py
- apphub/src/services/
- apphub/src/schemas/
- apphub/tests/
- docs/api-contracts-apphub.md

## Implementation Tasks

1. Define the compose-specific request and validation contracts that enter AppHub as `installation_source=compose`. (AC: 1, 2)
2. Implement syntax validation, normalization to a shared installation specification, and policy validation with side-effect-free failure behavior. (AC: 1, 2)
3. Extend the current install execution path so validated compose installs use the same task model and My Apps handoff as marketplace installs. (AC: 1)
4. Persist enough deployment-source metadata and revision summary for later redeploy, diagnosis, and lifecycle actions. (AC: 1)
5. Return actionable diagnostics for unsupported directives and validation failures without leaking raw internal implementation details. (AC: 2)

## Testing Requirements

- Add focused backend tests for compose request DTO validation, normalization, policy rejection, and no-partial-resource guarantees.
- Add backend tests for supported compose requests entering the existing task model and surfacing as custom compose deployments in My Apps.
- Run targeted pytest for touched compose-install slices.
- Run python compile validation for touched AppHub modules.
- Validate in the live product container that a rejected compose request leaves no orphaned resources and that an accepted request appears through the existing install feedback loop.

## Definition of Done

- AppHub accepts custom compose requests as a first-class install-source type.
- Compose requests are normalized into the shared installation domain before execution.
- Product policy validation rejects unsupported or unsafe directives before any deployment resources are created.
- Valid compose requests use the existing task loop and appear in My Apps as custom compose applications.
- Deployment metadata is durable enough to support later redeploy, diagnosis, and lifecycle operations.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/epics.md Story 3.3B, _bmad-output/planning-artifacts/prd.md FR-APP-002A and security requirements, _bmad-output/planning-artifacts/architecture.md Installation Domain Architecture, Data Architecture, Authentication & Security, and API Strategy sections.
- Continuity references: _bmad-output/implementation-artifacts/3-3-build-the-installation-task-loop.md, apphub/src/api/v1/routers/app.py, apphub/src/services/app_manager.py.

## Tasks / Subtasks

- [ ] Define transport and domain contracts for compose installs. (AC: 1, 2)
  - [ ] Add request DTOs that distinguish compose source payload from install metadata.
  - [ ] Keep the DTO shape extensible for later env-file and multi-file additions.
- [ ] Implement validation and normalization. (AC: 1, 2)
  - [ ] Validate compose syntax.
  - [ ] Normalize accepted input into a shared installation specification.
  - [ ] Apply product policy checks before any resource mutation.
- [ ] Integrate compose execution into the current install task model. (AC: 1)
  - [ ] Reuse existing task acceptance and tracking identity.
  - [ ] Classify successful installs as custom compose deployments in My Apps.
- [ ] Persist durable deployment metadata. (AC: 1)
  - [ ] Record installation source and deployment revision summary.
  - [ ] Leave room for later redeploy and diagnosis flows.
- [ ] Harden diagnostics and cleanup behavior. (AC: 2)
  - [ ] Return actionable validation failures.
  - [ ] Guarantee no partial resource creation on rejected requests.

## Dev Notes

### Architecture Compliance

- This story is the first backend implementation of the normalized installation domain. Avoid solving it as a compose-only special case with no path back into the shared install model.
- AppHub remains the only public API. Internal helper services are acceptable, but they cannot become a second product backend.
- Persistence should stay compatibility-first. Add only the minimal durable state needed for install-source metadata, deployment revision, and future lifecycle continuity.

### Security Notes

- Policy rejection is part of the core contract, not a best-effort warning. Unsafe directives must fail the request before any runtime mutation.
- Errors should remain actionable without exposing internal host paths, raw secrets, or irrelevant low-level traces.

### Execution Notes

- The fastest safe implementation path is likely to reuse the existing install manager and task identity while inserting a compose-source normalization layer ahead of execution.
- Preserve compatibility with future runtime-source deployment so that compose does not lock the installation domain into a two-track model.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-13: Story created to define the development-ready backend slice for compose normalization, policy validation, and install execution inside the unified installation domain.

### File List

- _bmad-output/implementation-artifacts/3-3b-build-backend-validation-and-install-execution-for-custom-compose-apps.md
- _bmad-output/implementation-artifacts/3-3b-build-backend-validation-and-install-execution-for-custom-compose-apps_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-05-13: Created Story 3.3B and advanced sprint tracking to ready-for-dev for the compose backend validation and execution slice.