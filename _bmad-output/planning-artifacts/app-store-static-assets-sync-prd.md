# Product Requirements Document - Global App Store Data Online Update Plan

**Author:** Websoft9
**Date:** 2026-06-01
**Status:** Draft
**Version:** 0.2
**Scope:** End-to-end online update design for App Store indexes, runtime-derived install data, and docker library data
**Related Documents:** [PRD](./prd.md), [Architecture](./architecture.md), [Current Architecture Baseline](../../docs/current-architecture-baseline.md), [AppHub API Baseline](../../docs/api-contracts-apphub.md), [Product Container README](../../docker/product/README.md)

## 1. Document Goal

This document defines the global product plan for App Store data online update. The scope is no longer a single sync script. It covers publishing, storage, runtime sync, compatibility governance, operator control surface, and migration.

This App Store data scope includes:

- browse indexes such as `catalog_{locale}.json` and `product_{locale}.json`
- `app-store-install-metadata.json` and similar runtime-derived install data
- docker library templates, default env files, install source files, and the source inputs used to derive install data

This document does not cover:

- `media` image and screenshot sync
- installed application runtime upgrade
- platform container or image self-upgrade
- user business data volumes

## 2. Current Baseline and Root Problem

The current update model is still a bootstrap-time full download and overwrite flow. When specific directories or markers are missing, the runtime fetches compressed packages from object storage and expands them into runtime directories.

The core problem is not only the packaging format. The system lacks a stable contract between publishing and runtime consumption:

1. There is no independently traceable App Store data version.
2. There is no explicit compatibility rule between platform version and App Store data version.
3. There is no standard artifact layout for runtime diffing.
4. There is no staging, atomic activation, or previous-version rollback boundary.
5. There is no unified operator entry or status model.
6. There is no stable contract between DevOps publishing and runtime code.

## 3. Problem Statement

Websoft9 needs an App Store data online update system so that browse indexes, runtime-derived install data, and docker library data can evolve together as a versioned content subsystem: incrementally updatable, compatibility-gated, and safely recoverable.

The solution must answer six questions:

1. How the publishing side generates incrementally consumable artifacts.
2. How the runtime knows which version is active.
3. How the platform decides whether a new version is compatible.
4. How sync downloads only changed data instead of doing full overwrite.
5. How the runtime rolls back safely when activation fails.
6. How operators inspect state, trigger sync, and diagnose failure.

## 4. Goals and Non-Goals

### 4.1 Goals

1. Make App Store indexes and docker library data independently publishable.
2. Use incremental update as the default path instead of full overwrite.
3. Establish explicit compatibility constraints between platform versions and App Store data versions.
4. Create one contract spanning DevOps publishing and runtime consumption.
5. Support staging, atomic activation, previous-version rollback, and status tracking.
6. Support both platform-upgrade reconciliation and manual operator sync.
7. Preserve current product read paths so Console and AppHub do not need a one-shot redesign.

### 4.2 Non-Goals

1. The solution does not define `media` image sync.
2. MVP does not use block-level binary patching.
3. MVP does not convert App Store data into a mutable database-first system.
4. MVP does not accept arbitrary third-party sync sources outside trusted Websoft9 artifact storage.
5. The solution does not define installed application upgrade semantics.

## 5. Primary Stakeholders and Jobs

### 5.1 Stakeholders

- release engineering teams that produce App Store data versions
- platform runtime owners that need compatibility, sync, activation, and rollback
- operators that need state visibility and manual controls

### 5.2 Primary Jobs To Be Done

- know which App Store data version is active on the platform
- determine whether a newer compatible version exists
- download only changed index and library packs
- activate the new version without breaking the current experience
- recover quickly to the previous version when activation fails

## 6. Scope Boundary

This solution covers four logical data domains:

1. `catalog-index`
2. `product-index`
3. `derived-install-data`: runtime-derived install data recalculated from docker library and local configuration
4. `library-apps`

It also spans three system boundaries:

1. DevOps publishing: version generation, manifest generation, pack creation, artifact publication
2. Runtime consumption: version detection, compatibility check, incremental download, staging activation, rollback
3. Operator control: status inspection, update check, sync trigger, failure diagnosis

## 7. Global Functional Requirements

### FR-GLOBAL-001: App Store Data Version Identity

The system must define an App Store data release identity that evolves separately from platform version.

Acceptance criteria:

- each App Store data release has a unique version
- the runtime persists current active and previous versions
- operators can query the current active version

### FR-GLOBAL-002: Compatibility Governance

The system must establish a bidirectional compatibility contract between platform version and App Store data version.

Acceptance criteria:

- the platform declares supported data schema and data version ranges
- each data release declares compatible platform version ranges
- activation is allowed only when both sides agree

### FR-GLOBAL-003: Standardized Artifacts

The system must define standard artifacts so the runtime can plan diffs and incremental consumption.

Acceptance criteria:

- the publishing pipeline emits a top-level manifest
- the manifest contains version, compatibility range, file inventory, pack inventory, and integrity metadata
- the publishing pipeline produces reusable packs instead of only one large compressed package
- `app-store-install-metadata.json` is not shipped as an authoritative release metadata artifact

### FR-GLOBAL-004: Incremental Sync

The system must support pack-level incremental sync.

Acceptance criteria:

- the runtime can compare local and target manifests
- it downloads only changed packs or required deletions
- it can fall back to a full snapshot sync when no valid incremental path exists

### FR-GLOBAL-005: Safe Activation and Rollback

The system must activate new versions without corrupting the currently active data.

Acceptance criteria:

- new data is downloaded into staging first
- all packs and key files are verified before activation
- after an upgrade, the runtime must recalculate `app-store-install-metadata.json` from the upgraded docker library and local configuration
- activation atomically switches the active pointer
- activation failure can restore the previous version

### FR-GLOBAL-006: Operator Status and Controls

The system must provide actionable status and controls.

Acceptance criteria:

- operators can see current version, available compatible version, compatibility state, last sync result, and error summary
- the system supports check-only, sync, and rollback actions
- sync exposes clear stages such as checking, downloading, verifying, activating, rolled-back, and failed

### FR-GLOBAL-007: Platform Upgrade Reconciliation

Platform upgrades must automatically re-evaluate and reconcile App Store data versions.

Acceptance criteria:

- the platform upgrade flow runs reconcile after upgrade
- if the current active data version is incompatible with the new platform version, the system upgrades or reverts to a compatible target
- if no compatible target exists, the system must surface a blocked or degraded state instead of silently continuing

### FR-GLOBAL-008: Read Path Continuity

The system must preserve current consumer read contracts.

Acceptance criteria:

- Console keeps using the current index and runtime-derived install data paths
- AppHub keeps reading library and runtime-derived install data through compatible paths
- the frontend does not need direct awareness of object storage layout

## 8. Non-Functional Requirements

### 8.1 Reliability

- interrupted sync must not corrupt active data

### 8.2 Performance

- regular updates should transfer only changed packs, significantly less than full overwrite

### 8.3 Security

- only trusted manifests and packs from the official release pipeline may be accepted

### 8.4 Operability

- operators must be able to quickly answer current version, available version, and failure reason

## 9. Success Indicators

1. Most App Store data updates no longer require full-package overwrite.
2. Platform upgrades automatically reconcile App Store data to a compatible version.
3. DevOps artifacts and runtime code follow a stable contract instead of implicit filenames.
4. Operators can independently run check, sync, and rollback without rebuilding the whole platform image.

## 10. Open Questions

1. What should be the exact rebuild trigger, timeout budget, and failure policy for `app-store-install-metadata.json` regeneration?
2. Should the first operator entry live in Settings or in a dedicated App Store maintenance surface?
3. Should pack boundaries be based on data type or on library app ranges?
4. Should the UI show newer but incompatible versions as informational status?

## 11. BMAD Next Steps

1. `CA` / `bmad-create-architecture`: define the publishing flow, manifest format, storage layout, runtime activation, and rollback mechanics.
2. `CU` / `bmad-create-ux-design`: define status surfaces, sync entry points, failure messaging, and task feedback.
3. `CE` / `bmad-create-epics-and-stories`: split the work into DevOps publishing changes, runtime sync engine, status APIs, operator UI, and migration tasks.
