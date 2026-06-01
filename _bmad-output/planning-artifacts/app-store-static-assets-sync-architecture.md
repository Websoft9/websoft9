# Architecture Design - Global App Store Data Online Update Architecture

**Author:** Websoft9
**Date:** 2026-06-01
**Status:** Draft
**Version:** 0.2
**Related Documents:** [Global App Store Data Online Update PRD](./app-store-static-assets-sync-prd.md), [Architecture](./architecture.md), [Product Container README](../../docker/product/README.md), [Runtime Asset Boundaries](../../docker/product/runtime-asset-boundaries.yaml)

## 1. Architecture Summary

The target architecture is not a more complex zip script. It is a full publish-distribute-consume-activate-rollback subsystem for App Store data.

The subsystem spans three layers:

1. publishing: DevOps generates versions, manifests, and pack artifacts
2. distribution: object storage serves version pointers, manifests, and packs
3. runtime: the platform performs compatibility checks, incremental sync, staging activation, and rollback

This architecture covers browse indexes, runtime-derived install data, and docker library data. It does not include `media` image sync.

## 2. Architectural Root Cause

The current implementation fails because runtime code and publishing flow do not share a stable contract. The runtime relies on fixed filenames and full overwrite packages, which means:

- it cannot confidently identify the active data version
- it cannot evaluate compatibility cleanly
- it cannot plan differential downloads
- it cannot activate safely or roll back quickly
- it cannot expose coherent operator state

This change therefore requires both DevOps and runtime architecture changes.

## 3. Target Principles

1. version-first: every App Store data release carries explicit version and compatibility metadata
2. manifest-first: runtime planning is driven by manifests, not implicit filenames
3. incremental-first: changed packs are the default transport unit, with full snapshot only as fallback
4. safe activation: all new data is staged and verified before switch-over
5. clear control surface: operators can inspect state, trigger actions, and diagnose failures

## 4. Component Model

### 4.1 Publishing Components

The publishing side adds these responsibilities:

1. generate App Store data versions
2. generate top-level release manifests
3. generate file and pack inventories
4. pack indexes and library data with fixed sharding rules
5. publish manifests, packs, and integrity metadata to object storage

### 4.2 Runtime Components

The runtime adds these responsibilities:

1. read local current and previous version state
2. fetch remote latest pointers and target manifests
3. evaluate compatibility
4. build sync plans
5. download changed packs into staging
6. verify key files and recalculate derived install data
7. activate atomically or roll back

### 4.3 Operator Control Surface

The control surface adds these responsibilities:

1. show current active version and latest compatible version
2. show compatibility state and recent sync result
3. provide check, sync, and rollback actions
4. expose error summary and stage information

## 5. Version and Compatibility Model

### 5.1 Version Axes

The architecture keeps three version axes:

1. `platform_version`
2. `asset_schema_version`
3. `app_store_data_version`

### 5.2 Bidirectional Compatibility Contract

The platform declares:

- supported data schema range
- supported data version range
- default update channel

Each App Store data release declares:

- its data version
- its schema version
- its compatible platform version range
- which older versions can upgrade incrementally to it

Activation gate:

- the schema must be supported by the platform
- the data version must fall within the platform-supported range
- the running platform version must satisfy the release compatibility range
- manifest and pack verification must succeed

## 6. Artifact Model

### 6.1 Recommended Artifact Set

Each data release should contain at least:

- `latest.json` for channel latest pointer
- `release.json` for top-level version descriptor
- `files-manifest.json` for logical inventory
- `delta-from-<version>.json` for differential inventory
- `packs/*` for deterministic pack files
- `checksums.txt` or equivalent integrity metadata

### 6.2 Sharding Strategy

Recommended first-phase sharding:

1. one pack for `catalog-index`
2. one pack for `product-index`
3. `derived-install-data` remains a local derivation step rather than a published pack
4. multiple packs for `library-apps` by app-name range or directory range

This is a practical compromise:

- fewer requests than one-file-per-object sync
- more incremental than one large zip
- easier to coordinate between DevOps and runtime

## 7. Object Storage Layout

Recommended logical layout:

```text
app-store-data/v1/
  channels/
    release/latest.json
    dev/latest.json
  releases/
    2.2.17-data.3/
      release.json
      files-manifest.json
      deltas/
        from-2.2.17-data.2.json
      packs/
        catalog-index-<hash>.tar.zst
        product-index-<hash>.tar.zst
        library-apps-a-f-<hash>.tar.zst
        library-apps-g-m-<hash>.tar.zst
        library-apps-n-z-<hash>.tar.zst
```

## 8. Local Runtime Store

Recommended local layout:

```text
/websoft9/app-store-data/
  manifests/
  packs/
  releases/
    <version>/
      indexes/
      library/
      derived/
      release.json
  staging/
  current
  previous
  state.json
```

Consumer-facing read paths stay stable:

- current index paths remain valid
- current library paths remain valid

Implementation should expose them through stable mapping or pointer switching, not through in-place overwrite of live directories.

## 9. Incremental Sync Flow

### 9.1 Check

1. read local `state.json`
2. fetch channel `latest.json`
3. fetch target `release.json`
4. evaluate compatibility

### 9.2 Plan

1. stop if current already equals target
2. use delta manifest if current-to-target delta is available
3. otherwise use the target full manifest
4. compute required downloads, deletions, and retained packs

### 9.3 Download

1. download changed packs into local cache
2. verify checksums
3. materialize the target release into staging

### 9.4 Verify

1. verify key index files exist
2. verify required library directories exist
3. recalculate `app-store-install-metadata.json` from the upgraded docker library and local configuration
4. verify overall target structure

### 9.5 Activate

1. record current as previous
2. atomically switch to the new release
3. update `state.json`
4. emit success event

### 9.6 Roll Back

If activation or post-activation verification fails:

1. restore previous
2. record failure reason
3. preserve failed staging for diagnosis

## 10. Runtime-Derived Install Data Strategy

`app-store-install-metadata.json` is not authoritative release metadata. It is a runtime-derived artifact rebuilt from docker library contents and local configuration.

This architecture makes that explicit:

1. the publishing pipeline does not ship `app-store-install-metadata.json` as the source-of-truth metadata artifact
2. after App Store data upgrade, the runtime must recalculate this file
3. the new release is not fully consumable until the recalculation step completes successfully

This keeps local configuration semantics inside the runtime boundary instead of incorrectly turning them into static published metadata.

## 11. Trigger Model

### 11.1 Startup Guarantee

- if there is no compatible local baseline, the platform must reconcile minimum required data before ready

### 11.2 Manual Trigger

- operators can run check, sync, and rollback manually

### 11.3 Scheduled Trigger

- the platform can periodically check for newer compatible releases

### 11.4 Platform Upgrade Hook

- platform upgrades automatically trigger reconcile

## 12. API and Status Surface

Suggested backend surface:

- `GET /app-store/data/status`
- `POST /app-store/data/check`
- `POST /app-store/data/sync`
- `POST /app-store/data/rollback`

Suggested state fields:

- `currentVersion`
- `previousVersion`
- `latestCompatibleVersion`
- `compatibilityState`
- `lastCheckAt`
- `lastSyncResult`
- `currentStage`

## 13. DevOps Change Boundary

The publishing pipeline must add:

1. version generation rules
2. manifest and delta manifest generators
3. pack creation rules
4. checksum generation
5. standard object storage layout publication

Without this work, runtime cannot perform real incremental update.

## 14. Code Change Boundary

The runtime code must add:

1. local version state persistence
2. manifest fetch and compatibility evaluation
3. incremental plan generation
4. pack download and staging materialization
5. atomic activation and rollback
6. status APIs and task feedback

Without this work, even a correct publishing pipeline cannot be consumed by the product.

## 15. Migration Path

### Phase 0

- keep current zip artifacts
- add manifest and pack artifacts alongside them

### Phase 1

- runtime prefers the new manifest-first protocol
- old zip path stays as fallback

### Phase 2

- ship staging, atomic switch, and previous-version rollback

### Phase 3

- downgrade the old full-zip path to emergency compatibility only

## 16. Key Risks

1. current library layout may not map cleanly to stable pack boundaries
2. whether install-data recalculation failure should block activation still needs final product decision
3. blocking versus degraded behavior during reconcile must be defined clearly

## 17. Recommended Implementation Split

1. publishing pipeline and manifest generator
2. runtime sync and activation engine
3. status APIs and task model
4. operator control surface
5. migration and fallback hardening
