# Story 1.3: Define the Single-Container Multi-Process Runtime Skeleton

## Status

done

## Story

As a platform engineer,
I want Websoft9 to define a clear single-container multi-process runtime skeleton,
so that the refactored platform can be delivered as one managed product unit.

## Acceptance Criteria

1. The delivery model clearly shows how AppHub, Portainer, Gitea, and NPM coexist inside one product container.
2. The runtime skeleton identifies process management, service start order, and health-entry expectations.
3. Engineers can distinguish platform processes, configuration locations, data locations, and log locations.
4. The model does not require converting all services into one binary.

## Dependencies

- Stories 1.1 and 1.2 establish the frontend baseline, but this runtime story primarily anchors the delivery topology for the rest of the program.

## Developer Context

- Current brownfield runtime still uses multiple containers.
- Architecture requires topology convergence into one product container while preserving service responsibilities.
- AppHub remains the primary business orchestration layer and unified API surface.
- A product-managed process supervision layer is required, but the services keep their native runtimes.

## Implementation Guardrails

- Do not redesign this story into a backend rewrite.
- Do not collapse AppHub, Portainer, Gitea, and NPM into one executable.
- Do not leave process supervision implicit; the runtime owner, process contracts, and health expectations must be explicit.
- Keep the resulting model compatible with later backup, upgrade, and migration stories.

## Suggested File Targets

- `docker/`
- `docker/apphub/`
- `docker/deployment/`
- `install/`
- `scripts/`
- supporting runtime design notes under `_bmad-output/implementation-artifacts/` if needed

## Implementation Tasks

1. Define the process supervision approach for the single product container.
2. Document or codify service startup order and failure behavior.
3. Identify the canonical health entry or readiness checks for the converged runtime.
4. Record the boundaries for processes, config, data, and logs so later stories can build against them.
5. Keep the runtime contract minimal, explicit, and implementation-oriented.

## Testing Requirements

- Validate that the runtime model is unambiguous enough for container startup implementation.
- Validate that startup order and degraded-state signaling are explicit.
- Validate that the runtime boundary can be reviewed without assuming a binary merge.

## Definition of Done

- A clear single-container runtime skeleton exists.
- Service order, supervision, and health expectations are explicit.
- Data, config, and log boundaries are identified at a skeleton level.
- Story 1.4 can implement startup behavior without reopening the topology decision.

## Source Notes

- Primary sources: Epic 1 acceptance criteria, architecture deployment model, process and boundary constraints.

## Dev Agent Record

### Debug Log

- Anchored the runtime work on the current multi-container topology in `docker/docker-compose.yml`, the AppHub container supervisor contract, and existing install/deployment notes.
- Added `docker/deployment/single-container-runtime-skeleton.yaml` as the explicit runtime contract for the converged product container, covering supervision ownership, startup order, readiness, degraded-state rules, and process/data/config/log boundaries.
- Added `scripts/platform-entrypoint.sh` and `scripts/platform-healthcheck.sh` as the bootstrap and health-entry skeletons that distinguish required readiness failures from degraded supporting services.
- Updated `docker/README.md`, `docker/deployment/README.md`, and `install/README.md` so the repository now distinguishes the current multi-container delivery from the Story 1.3 single-container target contract.
- Validated the shell healthcheck skeleton with `bash -n` and verified the new contract/documentation files are editor-clean.
- During Epic 1 closeout, aligned the Story 1.3 skeleton contract with the final Story 1.4 runtime truth for AppHub health endpoints, Portainer's internal HTTPS control plane, and converged bootstrap marker paths.

### Completion Notes

- Story 1.3 acceptance criteria are satisfied at the skeleton level: the target single-container delivery model, process supervision, startup order, health-entry expectations, and filesystem boundaries are now explicit.
- The runtime contract keeps native service runtimes intact and gives Story 1.4 a concrete convergence target without forcing a premature backend rewrite.
- Epic 1 closeout reconciled the original skeleton wording with the final implemented runtime so the contract no longer points at superseded Portainer or healthcheck paths.
- Final re-review returned no blocking findings. The remaining gap is that real single-container smoke validation must wait for Story 1.4 to implement the startup behavior behind these contracts.

### File List

- docker/README.md
- docker/deployment/README.md
- docker/deployment/single-container-runtime-skeleton.yaml
- install/README.md
- scripts/platform-entrypoint.sh
- scripts/platform-healthcheck.sh

### Change Log

- 2026-04-22: defined the single-container multi-process runtime skeleton and canonical healthcheck contract for Story 1.3.
- 2026-04-22: resolved review follow-ups for health contract realism, bootstrap assets, and target path boundaries; story moved to done.
- 2026-04-22: aligned the Story 1.3 skeleton contract with the final Epic 1 runtime implementation during epic closeout.
