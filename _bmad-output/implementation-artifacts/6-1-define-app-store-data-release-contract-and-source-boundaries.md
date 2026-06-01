# Story 6.1: Define the App Store Data Release Contract and Source Boundaries

## Status

ready-for-dev

## Story

As a platform architecture owner,
I want the App Store data source boundaries, version structure, and manifest contract to be defined,
so that the publishing pipeline and runtime logic can share one authoritative rule set.

## Acceptance Criteria

1. When the App Store data release contract is defined, `catalog_{locale}.json`, `product_{locale}.json`, and docker library data are explicitly treated as source release data, while `app-store-install-metadata.json` is explicitly treated as runtime-derived install data and not as authoritative published metadata.
2. When the contract is completed, the documentation clearly defines the semantics of `platform_version`, `asset_schema_version`, and `app_store_data_version`, and how compatibility ranges are declared by both the platform and the data release.
3. When the manifest contract is completed, it defines at least the required fields and ownership boundaries for `latest.json`, `release.json`, file inventory, delta inventory, and pack inventory.

## Dependencies

- The feature PRD and architecture docs already exclude `media` and require `app-store-install-metadata.json` to be recalculated after upgrade.
- The current runtime script already proves that `app-store-install-metadata.json` is derived from docker library data and local configuration instead of being a directly published upstream source artifact.

## Development Context

- This is the foundation story for the entire feature slice. Publishing, runtime sync, status APIs, and platform-upgrade reconcile all depend on this contract.
- Without this story, later implementation will keep drifting on the boundary between source data and derived data.
- The current product already exposes `/media/json/app-store-install-metadata.json` to Console, so this story must preserve read-path continuity while correcting the data definition.

## Guardrails

- Do not redefine `app-store-install-metadata.json` as authoritative publishing metadata.
- Compatibility must remain a bidirectional contract instead of a one-sided declaration.
- Manifest field definitions should leave enough room for later code implementation without introducing unrelated complexity.

## Suggested Files

- _bmad-output/planning-artifacts/app-store-static-assets-sync-prd.md
- _bmad-output/planning-artifacts/app-store-static-assets-sync-architecture.md
- docs/api-contracts-apphub.md
- docker/product/scripts/platform-sync-runtime-assets.py

## Implementation Tasks

1. Define source-data, derived-data, and consumer-path boundaries for App Store data. (AC: 1)
2. Define version axes and compatibility expression. (AC: 2)
3. Define baseline fields for `latest.json`, `release.json`, file inventory, delta inventory, and pack inventory. (AC: 3)
4. Document ownership boundaries between publishing and runtime. (AC: 1, 2, 3)

## Test Requirements

- Cross-check the documentation against the current runtime generation logic.
- Cross-check current Console and AppHub consumer paths to preserve continuity.

## Definition of Done

- Source-data and derived-data boundaries are explicit.
- Version and compatibility model is explicit.
- Manifest contract baseline is explicit.
- Later stories no longer need to re-argue the identity of `app-store-install-metadata.json`.

## Source Notes

- Primary sources: _bmad-output/planning-artifacts/app-store-static-assets-sync-prd.md, _bmad-output/planning-artifacts/app-store-static-assets-sync-architecture.md, docker/product/scripts/platform-sync-runtime-assets.py.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- 2026-06-01: Created Story 6.1 as the contract-baseline story for App Store data online update.

### File List

- _bmad-output/implementation-artifacts/6-1-define-app-store-data-release-contract-and-source-boundaries.md
- _bmad-output/implementation-artifacts/6-1-define-app-store-data-release-contract-and-source-boundaries_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-06-01: Added Story 6.1 and marked it ready-for-dev.
