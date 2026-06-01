# App Store Data Online Update - Epics and Stories

## Overview

This document breaks the Global App Store Data Online Update plan into executable epics and stories.

The feature scope is:

1. browse index data such as `catalog_{locale}.json` and `product_{locale}.json`
2. docker library templates, default env files, and install source files
3. runtime-derived install data such as `app-store-install-metadata.json`

This feature explicitly excludes:

1. `media` image and screenshot sync
2. installed application upgrades
3. platform self-upgrade implementation details

## Requirements Inventory

### Functional Requirements

FR1: Define App Store data version identity, schema version, and platform compatibility ranges.

FR2: Define standard release artifacts so runtime can plan incremental sync through manifests instead of implicit zip filenames.

FR3: Enable the publishing pipeline to generate `latest.json`, `release.json`, file inventory, delta inventory, and reusable packs.

FR4: Enable runtime to identify the current active version, discover a compatible target, and build an incremental download plan.

FR5: Use staging, atomic switch, and previous-version rollback for safe activation.

FR6: Treat `app-store-install-metadata.json` as runtime-derived install data that must be recalculated after upgrade.

FR7: Provide status inspection, update check, sync, and rollback entry points.

FR8: Trigger App Store data reconcile after platform upgrade and surface blocked or degraded state when no compatible target exists.

### Non-Functional Requirements

NFR1: Regular updates should transfer only changed packs.

NFR2: Interrupted sync must not corrupt active data.

NFR3: Runtime must surface current version, available version, current stage, and failure reason.

NFR4: Runtime-derived install-data rebuild failure must have an explicit policy.

## Epic Sequencing Principles

This feature follows this order:

1. define source-data boundaries, versioning, and manifest contracts first
2. implement the publishing pipeline next so incremental consumption becomes possible
3. implement runtime sync, staged activation, and rollback after that
4. then land runtime-derived install-data rebuild
5. finally expose status APIs, operator controls, and platform-upgrade reconcile

## Epic List

### Epic 6: App Store Data Online Update Capability

Deliver a publishable, incrementally updatable, safely activatable, and recoverable App Store data subsystem for browse indexes, docker library data, and runtime-derived install data.

**Why first:** Current App Store data still depends on bootstrap-time full overwrite and implicit package naming. Without a shared release contract and runtime sync model, online update remains an ad hoc script problem.

**Scope:**

- define source-data versus derived-data boundaries
- define version, schema, and compatibility contracts
- build publishing manifests and sharded artifact model
- implement runtime incremental sync, staged activation, and rollback
- land `app-store-install-metadata.json` rebuild flow
- expose status APIs, manual controls, and platform-upgrade reconcile

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8

### Story 6.1: Define the App Store Data Release Contract and Source Boundaries

As a platform architecture owner,
I want the App Store data source boundaries, version structure, and manifest contract to be defined,
so that the publishing pipeline and runtime logic can share one authoritative rule set.

### Story 6.2: Build the App Store Data Publishing Pipeline and Sharded Artifacts

As a release engineer,
I want the App Store data pipeline to produce versioned manifests, delta inventories, and reusable packs,
so that runtime can do incremental update instead of full overwrite.

### Story 6.3: Build the Runtime Data Sync, Staged Activation, and Rollback Engine

As a platform runtime owner,
I want the platform to perform compatibility checks, incremental sync, staged activation, and previous-version rollback through manifests,
so that online updates are safe and recoverable.

### Story 6.4: Rebuild Runtime-Derived Install Data After Upgrade

As a platform runtime owner,
I want `app-store-install-metadata.json` to be recalculated after App Store data upgrade,
so that Console and AppHub continue consuming correct runtime-derived install data.

### Story 6.5: Provide App Store Data Status APIs and Operator Controls

As an operator,
I want to inspect current version, available version, sync stage, and failure reason, and manually trigger check, sync, and rollback,
so that I can independently manage App Store data updates.

### Story 6.6: Integrate App Store Data Reconcile into Platform Upgrade

As a platform administrator,
I want platform upgrade completion to automatically reconcile App Store data to a compatible version,
so that platform and App Store data versions do not drift into an incompatible state.
