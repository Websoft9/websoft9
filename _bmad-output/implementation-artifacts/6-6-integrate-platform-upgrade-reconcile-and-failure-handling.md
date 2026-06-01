# Story 6.6: Integrate Platform Upgrade Reconcile and Failure Handling

## Status

ready-for-dev

## Story

As a platform administrator,
I want platform upgrade completion to automatically reconcile App Store data to a compatible version,
so that platform and App Store data versions do not drift into an incompatible state.

## Acceptance Criteria

1. When a platform upgrade completes, the system automatically runs App Store data reconcile instead of relying on later manual repair.
2. When the current active data version is incompatible with the new platform version, the system upgrades or reverts to a compatible target version.
3. When no compatible target exists or reconcile fails, the system surfaces an explicit blocked or degraded state that operators can diagnose.

## Dependencies

- Stories 6.3, 6.4, and 6.5 provide sync, rebuild, and status-control foundations.

## Implementation Tasks

1. Hook App Store data reconcile into the platform-upgrade flow. (AC: 1)
2. Define the policy for incompatible versions and no-compatible-target cases. (AC: 2, 3)
3. Feed failure state into status APIs and diagnostic entry points. (AC: 3)

## Definition of Done

- Platform upgrade triggers reconcile automatically.
- Incompatibility handling is explicit.
- Operators can see blocked or degraded diagnostics.
