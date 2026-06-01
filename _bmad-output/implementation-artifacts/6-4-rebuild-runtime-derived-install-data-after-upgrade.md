# Story 6.4: Rebuild Runtime-Derived Install Data After Upgrade

## Status

ready-for-dev

## Story

As a platform runtime owner,
I want `app-store-install-metadata.json` to be recalculated after App Store data upgrade,
so that Console and AppHub continue consuming correct runtime-derived install data.

## Acceptance Criteria

1. When the upgraded docker library becomes active, the runtime recalculates `app-store-install-metadata.json` instead of reusing the old file or downloading it as a release artifact.
2. When recalculation succeeds, Console and AppHub continue reading current install data through the existing paths.
3. When recalculation fails, the system exposes a clear error and either blocks activation or rolls back according to the defined policy instead of silently continuing.

## Dependencies

- Story 6.3 provides the upgrade, staging, and activation flow.

## Development Context

- This is the most easily misdefined part of the feature and must make runtime rebuild explicit in the implementation.
- The current script already contains generation logic, but it still belongs to bootstrap-time asset preparation rather than a formal upgrade pipeline step.

## Guardrails

- Do not move `app-store-install-metadata.json` back into the publishing pipeline.
- Do not let recalculation failure become silent data drift.
- Preserve current consumer paths.

## Suggested Files

- docker/product/scripts/platform-sync-runtime-assets.py
- apphub/
- console/
- docs/api-contracts-apphub.md

## Implementation Tasks

1. Move `app-store-install-metadata.json` rebuild into the formal upgrade pipeline. (AC: 1)
2. Decide whether rebuild happens before or after activation and codify the failure policy. (AC: 1, 3)
3. Validate continuity for Console and AppHub consumers. (AC: 2)

## Test Requirements

- Verify `app-store-install-metadata.json` is regenerated after upgrade.
- Verify recalculation failure surfaces clear state and never silently succeeds.

## Definition of Done

- `app-store-install-metadata.json` is formally part of the post-upgrade runtime rebuild step.
- Consumer paths remain continuous.
- Failure policy is explicit.
