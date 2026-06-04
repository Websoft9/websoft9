## Architecture - Websoft9 Unified Release, Upgrade, and Migration Model

**Author:** Websoft9
**Date:** 2026-06-01
**Status:** Draft
**Version:** 0.1

## 1. Summary

The target is not another upgrade script. The target is a unified control line for release, platform upgrade, cross-generation migration, and component incremental updates.

The architecture has four layers:

1. Release layer
2. Orchestration layer
3. Runtime execution layer
4. Control and support layer

## 2. Core Principles

1. Classify first, orchestrate second.
2. Consume standard artifacts, not implicit script behavior.
3. Treat legacy Cockpit multi-container to 3.0 as migration, not routine upgrade.
4. Make component updates manifest-first and incremental-first.
5. Keep state, status, and diagnosis consistent across user, operator, and support surfaces.

## 3. Upgrade Paths

### platform-upgrade

Normal 3.x to later 3.x upgrade.

### legacy-migration

Legacy Cockpit multi-container to 3.0 migration with legacy asset discovery, supported-source-range evaluation, mapping, blocking rules, execution, and continuity verification.

### component-reconcile

Incremental update and compatibility reconciliation for internal components after release or platform upgrade.

### platform-managed-core-services

Gitea, Portainer, Nginx Proxy Manager, and AppHub remain platform-managed core services. In the first phase they move with the platform instead of exposing separate user-facing upgrade paths.

## 4. Shared State Model

Shared stages:

1. checking
2. planning
3. waiting-confirmation
4. downloading
5. executing
6. verifying
7. completed
8. failed
9. rolled-back
10. degraded

Shared result categories:

1. release-artifact-error
2. compatibility-blocked
3. environment-blocked
4. migration-mapping-required
5. execution-failed
6. verification-failed
7. rollback-failed
8. component-reconcile-failed

## 5. Legacy Migration Minimum Asset Set

1. Platform configuration
2. Domains and certificates
3. App catalog and installation sources
4. Proxy configuration
5. Gitea, Portainer, Nginx Proxy Manager, and AppHub data, config, and entry continuity
6. Third-party integration continuity
7. Important mounts and runtime-derived data

## 6. Runtime Responsibilities

1. Persist platform state
2. Detect upgrade domain
3. Run prechecks
4. Build migration summary
5. Materialize staging state
6. Activate, rollback, or resume repair
7. Reconcile component versions after platform change
8. Expose structured status and diagnosis

Core-service version movement is part of platform orchestration. Independently versioned components remain the App Store and other content-style subsystems unless a future service gains its own compatibility contract and rollback boundary.

## 7. Roadmap

1. Define artifact and compatibility model
2. Implement 3.x upgrade framework
3. Implement legacy migration precheck and summary
4. Implement execution and continuity verification
5. Expand offline delivery and automated repair policies