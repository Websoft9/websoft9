# Story 1.4: Start Core Services Inside One Product Container

## Status

done

## Story

As a platform operator,
I want AppHub, Portainer, Gitea, and NPM to start inside one product container,
so that Websoft9 runs on the converged deployment topology without rewriting service responsibilities.

## Acceptance Criteria

1. AppHub, Portainer, Gitea, and NPM start inside the same product container using their native runtimes.
2. The managed runtime can start, stop, and restart them.
3. Startup failures produce a clear degraded-state signal.
4. The system does not fail silently during bootstrap.

## Dependencies

- Story 1.3 should have defined the runtime skeleton, service order, and health expectations.

## Previous Story Intelligence

- Story 1.3 should freeze the process supervision pattern and the startup contract.
- If Story 1.3 leaves supervision ambiguous, fix that before implementation rather than improvising here.

## Developer Context

- The target is one product container with multiple internal processes, not one rewritten service.
- The runtime must be able to manage lifecycle operations for the four core services.
- Failures must be visible to operators and later task/diagnostic surfaces.

## Implementation Guardrails

- Do not silently background processes without supervision.
- Do not treat “container started” as equal to “all internal services healthy.”
- Keep service-specific runtime ownership intact; convergence is about packaging and orchestration.
- Preserve the ability to inspect and restart individual internal services.

## Suggested File Targets

- product container build assets under `docker/`
- startup scripts under `scripts/` or container entrypoint locations
- runtime configuration under `docker/apphub/` or other converged image paths
- health and status integration hooks in AppHub only if strictly needed for visibility

## Implementation Tasks

1. Build the product container startup path for the four retained services.
2. Implement service start, stop, and restart coordination.
3. Add clear degraded-state signaling for partial startup failure.
4. Ensure the bootstrap path can differentiate ready, degraded, and failed states.

## Testing Requirements

- Smoke test full container startup.
- Simulate one internal service failure and verify degraded-state signaling.
- Verify restart behavior for at least one managed internal service.
- Verify no silent-success path exists when a required service fails.

## Definition of Done

- The four core services can run inside one product container.
- Managed lifecycle behavior exists.
- Partial failures are surfaced clearly.
- Story 1.5 can build routing boundaries against a real converged runtime.

## Source Notes

- Primary sources: Epic 1 acceptance criteria, architecture deployment model, runtime supervision expectations.

## Dev Agent Record

### Debug Log

- Added the converged product image under `docker/product/` so Nginx Proxy Manager remains PID 1 while an embedded supervisord layer owns AppHub API, AppHub media, Gitea, Portainer, and cron.
- Implemented the single-container bootstrap, health, service-control, and config-sync scripts so the runtime can differentiate `ready`, `degraded`, and `failed` states instead of treating container start as success.
- Added AppHub health endpoints for both API and media, then aligned runtime probes and status-file updates around those local loopback checks.
- Corrected Portainer bootstrap and health assumptions from `http://127.0.0.1:9000/api` to the real internal control plane at `https://127.0.0.1:9443/api`, including local self-signed TLS handling in shell scripts, the Go initializer, and the AppHub Portainer client.
- Fixed Gitea runtime packaging by copying both the real `/app/gitea/gitea` binary and its musl loader dependencies into the converged image so the native web process can execute inside the final product container.
- Rebuilt and smoke-tested the product container until strict and readiness health both returned `status=ready`, with Gitea, Portainer, NPM, AppHub API, and AppHub media all reachable on loopback.

### Completion Notes

- Story 1.4 acceptance criteria are satisfied: AppHub, Portainer, Gitea, and NPM now start inside one product container using their native runtimes, under a managed supervision model that also exposes per-service control hooks.
- The runtime now surfaces degraded versus failed startup explicitly through `platform-healthcheck.sh`, `platform-entrypoint.sh`, and the runtime status file instead of allowing silent bootstrap success.
- Final smoke validation reached green readiness and strict health, and the Portainer and NPM bootstrap markers were both created in their converged single-container paths.
- Final re-review on the implementation slice found no remaining blocking issues for Story 1.4. Story 1.5 can now build routing and gateway boundaries on top of a real converged runtime.

### File List

- apphub/src/core/apiHelper.py
- apphub/src/external/portainer_api.py
- apphub/src/main.py
- apphub/src/media.py
- docker/deployment/init_portainer.go
- docker/product/Dockerfile
- docker/product/README.md
- docker/product/s6/user-contents/websoft9-supervisor
- docker/product/s6/websoft9-supervisor/dependencies.d/prepare
- docker/product/s6/websoft9-supervisor/run
- docker/product/s6/websoft9-supervisor/type
- docker/product/supervisord.conf
- docker/proxy/init_nginx.sh
- scripts/platform-entrypoint.sh
- scripts/platform-healthcheck.sh
- scripts/platform-service-control.sh
- scripts/platform-start-gitea.sh
- scripts/platform-sync-config.sh

### Change Log

- 2026-04-22: implemented the converged product container image, supervision layer, lifecycle control scripts, and runtime health contract for Story 1.4.
- 2026-04-22: resolved runtime blockers for AppHub health wiring, Portainer internal HTTPS bootstrap, and Gitea native binary packaging inside the final image.
- 2026-04-22: completed smoke validation with strict and readiness health green; story moved to done.
