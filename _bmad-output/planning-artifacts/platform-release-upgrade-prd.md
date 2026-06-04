## PRD - Websoft9 Platform Release, Upgrade, and Migration Strategy

**Author:** Websoft9
**Date:** 2026-06-01
**Status:** Draft
**Version:** 0.1
**Scope:** A unified strategy for Websoft9 3.0 day-to-day releases, ongoing 3.x upgrades, legacy Cockpit multi-container to 3.0 migration, component-level incremental updates, and upgrade governance
**Related Documents:** [Master PRD](./prd.md), [Master Architecture](./architecture.md), [Upgrade Architecture](./platform-release-upgrade-architecture.md), [Upgrade Epics](./platform-release-upgrade-epics.md)

## 1. Objective

This document reframes the Websoft9 upgrade problem as a complete product release and evolution system instead of a narrow online-update feature.

It covers four areas together:

1. Day-to-day release flow for Websoft9 3.0 and later 3.x versions
2. Upgrade or migration path from legacy Cockpit multi-container Websoft9 versions to 3.0, with 2.2.19 as the latest anchor rather than the only source version
3. Incremental update mechanisms for platform components and content subsystems such as App Store data, docker library data, and runtime-derived install data
4. The continuity, rollback, support, compatibility, and operational issues that are usually overlooked

## 2. Root Problem

The current upgrade discussion mixes three fundamentally different concerns:

1. Normal in-family platform upgrades between newer versions
2. Cross-generation migration from legacy Cockpit multi-container versions to 3.0
3. Incremental updates for internal platform components

They cannot share one simplistic online-upgrade model. The root issue is not the lack of a download action. The root issue is the absence of one unified upgrade domain model, which causes unclear release boundaries, weak compatibility contracts, unstable execution semantics, and poor diagnosis.

## 3. Goals

1. Establish one unified upgrade taxonomy that separates platform release, 3.x upgrade, cross-generation migration, and component incremental updates.
2. Define standard release artifacts for Websoft9 3.0 and later versions.
3. Design a single-path migration flow from legacy Cockpit multi-container versions to 3.0 with explicit precheck, blocking, execution, verification, and rollback semantics.
4. Define compatibility contracts across platform version, component version, and data schema version.
5. Make component updates incremental-first with staging, atomic activation, and rollback.
6. Give operators and support a shared, structured state model for diagnosis and recovery.

## 4. Upgrade Domains

### Domain A: Platform Release

This domain defines how a Websoft9 version is packaged and published so it can be consumed by upgrade or migration flows.

### Domain B: 3.x Platform Upgrade

This domain covers normal upgrade flow from one 3.x version to another 3.x version.

### Domain C: Legacy Cockpit Multi-container to 3.0 Migration

This is not a normal upgrade. It is a migration because topology, control-plane boundaries, configuration sources, and continuity assumptions have changed.

The source line must not be modeled as only 2.2.19. It should be defined as the supported legacy Cockpit multi-container range, with 2.2.19 treated as the latest validation anchor and earlier versions evaluated for direct support, bridge-path requirement, or explicit blocking.

### Domain D: Component Incremental Updates

This domain covers independently versioned internal subsystems, starting with App Store indexes, docker library data, and runtime-derived install data.

### Domain E: Platform-managed Core Services

Gitea, Portainer, Nginx Proxy Manager, and AppHub should not be treated as independently upgradable user-facing components in the first phase. They are platform-managed core services.

That means their major-version movement should normally follow platform release and platform upgrade orchestration, while migration focuses on carrying their data, configuration, entry continuity, and integration state into the new single-container runtime.

## 5. Key Requirements

### FR-UPG-001: Unified Classification

The product must clearly separate platform release, 3.x upgrade, legacy Cockpit multi-container to 3.0 migration, and component incremental updates.

### FR-UPG-002: Standard Release Artifacts

Each release must expose structured version, compatibility, integrity, and migration metadata.

### FR-UPG-003: 3.x Upgrade Precheck

Normal upgrades must run environment and compatibility prechecks before execution.

### FR-UPG-004: Legacy Migration Precheck

Migration must detect legacy configuration, certificates, app metadata, proxy state, integrations, mounts, and non-portable assets before execution.

### FR-UPG-005: Single-path Execution

Upgrade and migration must remain observable, stage-based, and recoverable without degrading into a manual branching tree.

### FR-UPG-006: Post-upgrade Continuity Verification

The platform must explicitly verify platform entry, certificates, core integration access, and important app access continuity after execution.

### FR-UPG-007: Component Incremental Updates

Components must support their own versioning, compatibility contract, incremental delivery, staging, activation, and rollback.

### FR-UPG-008: Shared Support State Model

Operators and support must be able to distinguish release failures, platform upgrade failures, migration failures, and component update failures from one consistent state model.

## 6. Often-missed Concerns

1. Release flow and upgrade flow are separate concerns and both must be designed.
2. Legacy Cockpit multi-container to 3.0 must be treated as migration, not routine upgrade.
3. Component updates cannot drift independently of the platform compatibility matrix.
4. Entry continuity matters more than merely changing a version string.
5. Diagnosis and support semantics must be designed before failures happen.
6. Offline and restricted-network delivery must be considered early.

## 7. Success Metrics

1. Websoft9 3.x upgrades follow one standard repeatable workflow.
2. Legacy Cockpit multi-container to 3.0 migration no longer depends on hidden tribal knowledge.
3. Component updates no longer require full platform image republishing.
4. Support can triage upgrade issues from structured state instead of guesswork.