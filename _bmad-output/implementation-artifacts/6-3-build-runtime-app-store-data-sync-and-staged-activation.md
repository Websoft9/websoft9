# Story 6.3: Build Runtime App Store Data Sync and Staged Activation

## Status

ready-for-dev

## Story

As a platform runtime owner,
I want the platform to perform compatibility checks, incremental sync, staged activation, and previous-version rollback through manifests,
so that online updates are safe and recoverable.

## Acceptance Criteria

1. When runtime detects a compatible new version, it compares local and target manifests first and downloads only changed packs.
2. When the target version finishes downloading, the system materializes it into staging instead of directly overwriting live data.
3. When the target passes verification, the system atomically switches the active version; when verification fails, it restores the previous version.

## Dependencies

- Story 6.1 defines the runtime contract.
- Story 6.2 provides manifests and pack artifacts.

## Development Context

- This is the core runtime story for online update.
- It decides whether App Store data can leave the bootstrap-time full-overwrite model.

## Guardrails

- No sync failure may corrupt active data.
- Do not overwrite the live directory tree in place.
- Previous-version rollback must exist in the first implementation slice.

## Suggested Files

- docker/product/scripts/platform-sync-runtime-assets.py
- docker/product/scripts/platform-entrypoint.sh
- apphub/
- docs/

## Implementation Tasks

1. Add local version-state persistence and current/previous tracking. (AC: 1, 3)
2. Implement manifest fetch, compatibility evaluation, and incremental planning. (AC: 1)
3. Implement pack download, staging materialization, and structure verification. (AC: 2)
4. Implement atomic activation and previous-version rollback. (AC: 3)

## Test Requirements

- Validate that upgrading from one version to another downloads only changed packs.
- Validate that verification failure does not corrupt active data and restores the previous version.

## Definition of Done

- Runtime supports manifest-first incremental sync.
- Updates use staging.
- Rollback is available.
