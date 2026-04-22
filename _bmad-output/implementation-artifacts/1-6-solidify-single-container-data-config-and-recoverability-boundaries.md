# Story 1.6: Solidify Single-Container Data, Config, and Recoverability Boundaries

## Status

done

## Story

As an engineer responsible for delivery and recovery,
I want the data, configuration, logging, and recoverability boundaries of the one-container model to be explicit,
so that later backup, diagnostics, and migration work remain controlled.

## Acceptance Criteria

1. Key data, config, and log boundaries for AppHub, Portainer, Gitea, and NPM are explicitly identified.
2. The delivery model preserves stable mount or migration expectations.
3. Teams can tell which assets must be retained, moved, or restored.
4. One-container convergence does not block later backup, restore, or migration work.

## Dependencies

- Stories 1.3 through 1.5 should already define the runtime, startup behavior, and routing responsibilities.

## Previous Story Intelligence

- Earlier runtime stories define process ownership and platform routing boundaries; this story must now freeze the stateful asset boundaries.
- Upgrade and migration are intentionally last, so this story is the place to prevent later ambiguity.

## Developer Context

- Architecture requires a clean split between deployment-time immutable settings, secret mounts, and product-editable operational configuration.
- AppHub persistence remains the baseline; new durable state should be additive and compatibility-first.
- Structured logs, health signals, diagnostics, and upgrade supportability are explicit requirements.

## Implementation Guardrails

- Do not leave data ownership implicit per internal service.
- Do not mix mutable product settings, secrets, and runtime-generated data into one undifferentiated path.
- Do not define mounts in a way that blocks later backup or migration workflows.
- Keep the boundary understandable to operators, implementers, and future upgrade tooling.

## Suggested File Targets

- `docker/`
- `install/`
- `scripts/`
- container runtime configuration and mount definitions
- supporting delivery or migration notes under `_bmad-output/implementation-artifacts/` if needed

## Implementation Tasks

1. Identify per-service data, config, secret, and log boundaries.
2. Define the stable mount or copy-forward expectations for those assets.
3. Separate operator-editable config from immutable deployment settings and secrets.
4. Make recovery-critical assets explicit for later backup and migration stories.

## Testing Requirements

- Validate that each retained service has explicit state boundaries.
- Validate that backup or migration teams can identify required assets without guessing.
- Validate that logging and diagnostics paths are not co-mingled with unrelated mutable state.

## Definition of Done

- A clear asset-boundary model exists for AppHub, Portainer, Gitea, and NPM.
- Stable mount and migration expectations are explicit.
- Later stories for backup, logs, and upgrade can reuse this boundary without reopening the runtime baseline.

## Source Notes

- Primary sources: Epic 1 acceptance criteria, architecture data/config/logging/deployment rules, migration compatibility constraints.

## Dev Agent Record

### Debug Log

- Added `docker/product/runtime-asset-boundaries.yaml` as the machine-readable source of truth for immutable image assets, stable mounted service assets, copy-forward assets, secret-bearing paths, log paths, and ephemeral runtime state.
- Updated the converged product image so the asset-boundary manifest is copied into `/etc/websoft9/runtime-asset-boundaries.yaml` and can travel with the running image instead of remaining only in planning artifacts.
- Expanded the product image volume declarations to include the stable single-container service mounts `/data/gitea`, `/data/portainer`, `/data/nginx-proxy-manager`, `/etc/letsencrypt`, `/etc/modsec`, `/etc/custom`, and `/var/log/websoft9`.
- Explicitly kept `/websoft9/library` and `/websoft9/media` out of Docker volume declarations, documenting them as copy-forward assets so empty volumes do not shadow image-shipped baseline content.
- Validation exposed one inherited constraint from the upstream NPM base image: it still contributes a broad `/data` Docker volume. The boundary manifest and runtime README now mark that root as a compatibility umbrella only and direct backup or migration tooling to the service-owned subpaths instead.
- Rebuilt the product image and validated both the embedded volume declarations and the image-delivered asset-boundary manifest contents.

### Completion Notes

- Story 1.6 acceptance criteria are satisfied: AppHub, Gitea, Portainer, and NPM now have explicit data, config, log, secret, and ephemeral-state boundaries recorded in one machine-readable artifact.
- The delivery model now distinguishes stable mounted assets from copy-forward assets and non-backup runtime state, which gives later backup, restore, diagnostics, and migration work a concrete boundary contract instead of scattered path assumptions.
- The inherited `/data` base-image volume is now explicitly documented as legacy compatibility rather than the source of truth for recovery planning, preventing future stories from reopening the runtime baseline.
- Final validation succeeded by rebuilding `websoft9-product-story16:dev`, confirming the new volume declarations in image metadata, and confirming the boundary manifest is present inside the built image.

### File List

- docker/product/Dockerfile
- docker/product/README.md
- docker/product/runtime-asset-boundaries.yaml

### Change Log

- 2026-04-22: added an explicit single-container asset-boundary manifest for data, config, secrets, logs, and ephemeral runtime state.
- 2026-04-22: aligned the converged product image volume declarations with the stable service-owned mount expectations.
- 2026-04-22: documented the inherited legacy `/data` volume as compatibility-only and completed validation; story moved to done.
