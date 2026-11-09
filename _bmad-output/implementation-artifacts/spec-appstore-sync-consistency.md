---
title: 'App Store sync consistency and recovery'
type: 'bugfix'
created: '2026-11-09'
status: 'done'
baseline_commit: '8d88f0ce'
context: []
---

<frozen-after-approval reason="human-owned intent">

## Intent

**Problem:** App Store sync can advance its recorded dataset after dictionary or index failure, accept inconsistent publication objects, and require a full library download when the device skips published versions.

**Approach:** Harden the current project's sync boundary: verify publication identity, fail and restore on incomplete post-steps, and reconcile trusted local and remote indexes for skipped versions. Retain the existing public API, CLI and snapshot layout.

## Boundaries & Constraints

**Always:** Preserve existing uncommitted changes and legacy artifact compatibility; reuse the current rollback mechanism and focused tests; use the installed library as the source of installation metadata. Healthy unchanged datasets retain their lightweight path. Persist new state only after all required sync steps succeed.

**Ask First:** Changes to public APIs, installation request fields, persistent snapshot layout, upstream files, commits or deployment to a live environment.

**Never:** Change docker-library, installed instances, user volumes, frontend behavior, database installation semantics, or run full CI repeatedly. Do not weaken checksum validation to mask transient failures.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Legacy checksum absent | Confirmed HTTP 404 for optional checksum | Read legacy JSON | All other checksum failures fail or retry |
| Torn publication | Root and component versions disagree | Do not activate or advance state | Retry then return failure |
| Incomplete post-step | Dictionary/index write or manifest build fails | Restore previous live resources and active snapshots | Preserve previous successful state |
| Historical partial state | Same remote dataset, previous partial flag | Fetch required metadata and repair resources | Do not clear partial before repair succeeds |
| Skipped releases | Server delta starts after local version | Compare validated indexes and update only differing apps | Invalid local baseline falls back to full sync |
| Mutable latest package | ZIP and current checksum agree but index fingerprint differs | Reject candidate | Retry publication fetch on a later sync |
| Unchanged healthy dataset | All versions and local metadata agree | Avoid unnecessary component/package requests | No state advancement to unverified data |

</frozen-after-approval>

## Code Map

- `docker/scripts/platform-sync-runtime-assets.py` -- download, delta planning, staged packages, dictionary/index publication, rollback and state ownership.
- `apphub/tests/test_platform_sync_dictionary.py` -- checksum, consistency, recovery and index/fingerprint unit cases.
- `apphub/tests/test_appstore_manifest_builder.py` -- main sync orchestration, published manifests and rollback integration cases.

## Tasks & Acceptance

**Execution:**
- [x] `docker/scripts/platform-sync-runtime-assets.py` -- restrict optional checksum fallback; validate component versions on all paths and declared index/delta checksums and identities.
- [x] `docker/scripts/platform-sync-runtime-assets.py` -- propagate dictionary/index failures, protect repair paths with rollback, preserve active state on failure, and recover historical partial states.
- [x] `docker/scripts/platform-sync-runtime-assets.py` -- validate app fingerprints against the index and use trusted local index reconciliation when the server delta chain cannot apply; retain full fallback for unavailable baselines.
- [x] `apphub/tests/test_platform_sync_dictionary.py` -- exercise checksum errors, component mismatch, local baseline corruption, skipped-version additions/changes/removals and app content mismatch.
- [x] `apphub/tests/test_appstore_manifest_builder.py` -- exercise post-step failures and same-version repair with actual temporary trees and persisted state.

**Acceptance Criteria:**
- Given an existing valid App Store dataset, when a required sync step fails, then subsequent reads still see the previous assets and the recorded dataset is not advanced.
- Given an incomplete historical sync, when synchronization succeeds, then dictionary, index and app tree agree with the recorded dataset before partial status is removed.
- Given a valid local baseline and a newer validated index, when the server delta chain skips the local version, then only added or changed application packages are fetched and removed apps are deleted.
- Given legacy artifacts without extended metadata, when synchronization runs, then existing supported behavior remains available without accepting malformed declared checksums.

## Spec Change Log

## Design Notes

The existing backup/restore boundary provides failure recovery, not instantaneous multi-directory visibility to concurrent readers. Atomic file replacement prevents mutating hard-linked snapshot files. App fingerprints use sorted canonical `apps/<app>/<relative-file>` paths plus NUL-delimited file SHA-256 values. Local index reconciliation is permitted only when dataset identity and every existing app fingerprint match the baseline.

## Verification

**Commands:**
- `python3 -m pytest apphub/tests/test_platform_sync_dictionary.py apphub/tests/test_appstore_manifest_builder.py --no-cov -p no:cacheprovider -q` -- all scoped cases pass.
- `python3 -m pytest apphub/tests/test_appstore_sync_manager_versions.py --no-cov -p no:cacheprovider -q` -- existing snapshot activation remains compatible.
- Focused Ruff checks on touched tests and Python syntax validation of the sync script.

**Results (2026-11-09):** 152 focused tests passed, including the existing snapshot activation tests. Ruff check/format on both touched test files, Python syntax validation and `git diff --check` passed. Independent reviews identified legacy-format regressions, incomplete retry coverage and a missing-version fixture; these were repaired and verified. The completed blind review found no proven new issues. Existing `datetime.utcnow()` deprecation warnings remain. No upstream inspection, deployment, commit, branch, push, dependency installation or full CI was performed in this implementation.

## Suggested Review Order

**Sync Boundary**

- Follow planning, backups, activation and the final state commit.
	[platform-sync-runtime-assets.py:2514](../../docker/scripts/platform-sync-runtime-assets.py#L2514)
- Verify optional legacy checksum handling and required checksum failure behavior.
	[platform-sync-runtime-assets.py:160](../../docker/scripts/platform-sync-runtime-assets.py#L160)
- Reject missing versions and components from another publication channel.
	[platform-sync-runtime-assets.py:917](../../docker/scripts/platform-sync-runtime-assets.py#L917)

**Trusted Incremental Updates**

- Compare indexes only after checking the actual local baseline.
	[platform-sync-runtime-assets.py:1196](../../docker/scripts/platform-sync-runtime-assets.py#L1196)
- Bind downloaded templates to canonical content fingerprints.
	[platform-sync-runtime-assets.py:1155](../../docker/scripts/platform-sync-runtime-assets.py#L1155)
- Replace indexes atomically without mutating hard-linked snapshots.
	[platform-sync-runtime-assets.py:1360](../../docker/scripts/platform-sync-runtime-assets.py#L1360)

**Regression Coverage**

- Check skipped releases, damaged baselines, package races, retries and partial recovery.
	[test_platform_sync_dictionary.py:734](../../apphub/tests/test_platform_sync_dictionary.py#L734)
- Check real resource and state restoration after each required post-step fails.
	[test_appstore_manifest_builder.py:996](../../apphub/tests/test_appstore_manifest_builder.py#L996)