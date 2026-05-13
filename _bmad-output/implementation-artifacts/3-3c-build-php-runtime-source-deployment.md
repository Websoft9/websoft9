# Story 3.3C: Build PHP runtime-source deployment

## Status

ready-for-dev

## Story

As an operator deploying a PHP project,
I want to upload project code and select a curated PHP runtime profile,
so that Websoft9 can provision and run the application without requiring me to hand-author the full deployment stack.

## Acceptance Criteria

1. Given the user selects runtime-source deployment, when the PHP deployment flow opens, then the UI supports source-bundle upload plus runtime configuration such as PHP version, public directory, entry path, and environment variables.
2. Given the user submits a valid PHP runtime deployment request, when AppHub accepts it, then AppHub renders a normalized installation specification and executes it through the same task model used by other install flows, and the resulting application is classified as a runtime-based deployment in My Apps.

## Dependencies

- Story 3.3 already established the common install task loop and My Apps handoff.
- Story 3.3A and 3.3B define the general flexible-installation pattern for source-specific UI plus AppHub-owned normalization and policy enforcement.
- PRD FR-APP-002B explicitly limits Phase 1 runtime-source deployment to curated PHP support and requires source bundle upload, runtime parameters, normalized execution, and My Apps metadata continuity.
- Architecture explicitly defines `runtime_profile` as a normalized installation-domain object and defers broader multi-runtime rollout beyond the initial PHP slice.

## Previous Story Intelligence

- Existing install work already proved that accepted installs should converge into one task-feedback model and My Apps continuity. PHP runtime-source deployment must extend that path instead of becoming a separate deployment console.
- The user request was not for generic PaaS behavior or CI/CD. The product direction is a curated runtime profile, starting with PHP, under tight product-owned boundaries.
- Recent settings, files, and services work has repeatedly reinforced a product principle: Websoft9 should expose controlled operational workflows, not raw infrastructure surfaces. PHP runtime deployment must follow that same philosophy.

## Developer Context

- Phase 1 runtime-source deployment starts with PHP only. The backend and frontend must leave room for later runtime families, but this story must not expand scope into generic buildpacks, arbitrary language support, or CI pipelines.
- The normalized installation-domain architecture requires uploaded source bundles plus runtime profile selection to become one `installation_spec` that enters the same task model as marketplace and compose installs.
- The data architecture expects new durable state around installation-source metadata, deployment revisions, runtime-profile references, and source-bundle artifact locations.
- Security and API strategy still place AppHub at the center: upload handling, validation, runtime rendering, and deployment execution must all remain behind AppHub-owned APIs and policy checks.
- My Apps and lifecycle flows must be able to distinguish runtime-based deployments from marketplace and compose installs, and expose runtime-profile metadata in a stable way.

## Implementation Guardrails

- Treat PHP deployment as a curated runtime profile, not a generic code execution surface.
- Do not expand into git-driven deployment, build farm orchestration, arbitrary package managers, or broad multi-language runtime support.
- Uploaded source bundles, runtime parameters, and rendered deployment artifacts must stay behind AppHub-owned validation and task orchestration.
- Keep the runtime-source flow compatible with the same task loop, failure diagnostics, and My Apps continuity used by other install-source types.
- Runtime configuration inputs should remain explicit and structured: PHP version, public directory, entry path, port, and environment variables should not be hidden inside a freeform textarea.
- Persist enough metadata so later lifecycle actions and diagnostics can understand which runtime profile and source artifact produced the deployment.

## Suggested File Targets

- console/src/features/app-store/app-store-page.tsx
- console/src/shared/i18n/resources.ts
- apphub/src/api/v1/routers/app.py
- apphub/src/services/app_manager.py
- apphub/src/services/
- apphub/src/schemas/
- apphub/tests/
- docs/api-contracts-apphub.md

## Implementation Tasks

1. Add the PHP runtime-source deployment entry and structured parameter capture to the unified install flow. (AC: 1)
2. Define upload, runtime-profile, and normalized install contracts in AppHub for `installation_source=runtime`. (AC: 1, 2)
3. Implement AppHub-side source bundle validation, PHP runtime rendering, and execution through the existing task loop. (AC: 2)
4. Persist runtime-source metadata so My Apps can classify, display, and later operate on PHP deployments consistently. (AC: 2)
5. Keep the resulting slice extensible for later runtime families without widening Phase 1 scope. (AC: 1, 2)

## Testing Requirements

- Add focused backend tests for source-bundle upload constraints, runtime-profile validation, normalized install-spec generation, and My Apps classification.
- Add focused frontend validation for runtime parameter capture and upload-state handling if supported by the current test harness.
- Run npm run typecheck and npm run build for console.
- Run targeted pytest and python compile validation for touched AppHub modules.
- Validate in the live product container that a PHP runtime deployment enters the same install-feedback loop and is distinguishable in My Apps as a runtime-based deployment.

## Definition of Done

- The unified install flow exposes a PHP runtime-source deployment path.
- Operators can upload a PHP project bundle and configure the required runtime parameters through structured fields.
- AppHub renders that request into a normalized installation specification and executes it through the common task model.
- My Apps classifies the result as a runtime-based deployment and exposes runtime-profile metadata.
- The implementation remains clearly bounded to curated PHP support in Phase 1 while leaving room for later runtime families.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/epics.md Story 3.3C, _bmad-output/planning-artifacts/prd.md FR-APP-002B, _bmad-output/planning-artifacts/architecture.md Installation Domain Architecture, Data Architecture, and API Strategy sections.
- Continuity references: _bmad-output/implementation-artifacts/3-3-build-the-installation-task-loop.md, _bmad-output/planning-artifacts/prd.md FR-APP-003 and FR-APP-004.

## Tasks / Subtasks

- [ ] Add the PHP runtime-source entry to the unified install flow. (AC: 1)
  - [ ] Expose source-bundle upload.
  - [ ] Capture structured runtime parameters.
  - [ ] Keep the entry compatible with future runtime families.
- [ ] Define backend contracts for runtime-source deployment. (AC: 1, 2)
  - [ ] Model upload and runtime-profile inputs.
  - [ ] Normalize accepted input into the shared installation specification.
- [ ] Implement PHP runtime rendering and task execution. (AC: 2)
  - [ ] Validate source bundle and runtime inputs.
  - [ ] Render the PHP runtime deployment spec.
  - [ ] Execute through the same task loop used by other install types.
- [ ] Persist and expose runtime-source metadata. (AC: 2)
  - [ ] Classify the app correctly in My Apps.
  - [ ] Surface runtime profile and deployment summary metadata.

## Dev Notes

### Architecture Compliance

- This story must preserve the single installation-domain model. Runtime-source deployment is a source type inside the same install contract, not a new platform beside App Store and My Apps.
- `runtime_profile` is a first-class normalized object in the architecture. Treat it as the stable abstraction boundary rather than hardcoding PHP-only conditionals everywhere.
- Persistence additions should remain minimal and compatibility-first: artifact locations, runtime-profile reference, installation source, and deployment revision summary are the expected center of gravity.

### Scope Discipline

- The product requirement is curated PHP deployment, not arbitrary language deployment and not generic build automation.
- If a requirement smells like CI/CD, git push deploy, buildpack automation, or broad multi-runtime abstraction, it belongs outside this story.

### UX / Data Notes

- Runtime parameters should be explicit, visible, and bilingual.
- My Apps must be able to distinguish runtime deployments clearly from marketplace and compose installs so later lifecycle behavior can expose any source-specific limitations.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-05-13: Story created to define the development-ready PHP runtime-source deployment slice inside the unified installation model.

### File List

- _bmad-output/implementation-artifacts/3-3c-build-php-runtime-source-deployment.md
- _bmad-output/implementation-artifacts/3-3c-build-php-runtime-source-deployment_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-05-13: Created Story 3.3C and advanced sprint tracking to ready-for-dev for the Phase 1 PHP runtime-source deployment slice.