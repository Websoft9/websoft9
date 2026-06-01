# Story 6.2: Build the App Store Data Publishing Pipeline and Sharded Artifacts

## Status

ready-for-dev

## Story

As a release engineer,
I want the App Store data pipeline to produce versioned manifests, delta inventories, and reusable packs,
so that runtime can do incremental update instead of full overwrite.

## Acceptance Criteria

1. When an App Store data release completes, the pipeline produces `latest.json`, `release.json`, file inventory, delta inventory, and pack artifacts instead of only one large compressed package.
2. When a release changes only part of the indexes or part of the library app directories, only the corresponding packs change while unchanged packs remain reusable.
3. When release artifacts are published to object storage, runtime can resolve target versions and packs through a stable directory layout.

## Dependencies

- Story 6.1 has already defined the manifest contract, version axes, and source-data boundaries.

## Development Context

- This is the first DevOps-side implementation story and makes incremental update technically possible.
- The key problem with the current full-zip model is not just bandwidth. Runtime also has no way to know what actually changed.

## Guardrails

- Do not ship `app-store-install-metadata.json` as a published pack.
- In the first phase, prefer stable and explainable pack boundaries over ultra-fine granularity.
- The publishing layout must serve runtime consumption instead of only optimizing CI convenience.

## Suggested Files

- scripts/
- docker/product/
- docs/
- artifact publishing scripts or CI configuration

## Implementation Tasks

1. Implement App Store data version generation and release-manifest generation. (AC: 1)
2. Generate file inventory and delta inventory. (AC: 1, 2)
3. Establish stable sharding rules for indexes and library data. (AC: 2)
4. Define and implement the object-storage layout. (AC: 3)

## Test Requirements

- Validate at least one release where only part of the library changes and confirm pack reuse.
- Verify generated artifacts match the Story 6.1 manifest contract.

## Definition of Done

- The pipeline can generate manifests and packs.
- Packs are reusable.
- Runtime can resolve target versions and packs predictably.
