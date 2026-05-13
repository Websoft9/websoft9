# Sprint Change Proposal: Flexible Application Installation Expansion

**Date:** 2026-05-13  
**Scope:** Major  
**Primary Affected Area:** Epic 3 - Core Application Workflows, Flexible Installation, and Product Settings

## 1. Issue Summary

The current Websoft9 planning set assumes application installation is initiated only from the App Store template flow. That assumption no longer matches the intended product direction. The platform now needs to support two additional installation modes:

1. User-authored Docker Compose installation through upload or inline editing.
2. Runtime-based source deployment where operators upload project code and let Websoft9 provision a curated runtime topology, starting with PHP.

This is not a minor UI enhancement. It changes the product boundary of what “application installation” means inside Websoft9.

## 2. Impact Analysis

### PRD Impact

- The installation requirement must expand from marketplace-template-only behavior to a unified installation model.
- The PRD must explicitly describe custom compose deployment and runtime-based source deployment as first-class product capabilities.
- Phase 1 scope must include PHP as the first curated runtime profile.
- Security and policy boundaries must be clarified for custom compose input.

### Architecture Impact

- AppHub needs a normalized installation domain rather than three disconnected install surfaces.
- New persistent state is needed for installation-source metadata, deployment revisions, runtime-profile references, and uploaded source-bundle locations.
- Compose policy validation becomes a mandatory backend boundary.
- Runtime-source deployment requires a curated runtime-profile abstraction starting with PHP.

### Epic and Story Impact

- Epic 3 scope must expand to include flexible installation.
- New implementation stories are required for:
  - custom compose authoring and validation
  - custom compose execution
  - PHP runtime-source deployment
- My Apps and lifecycle stories must expose installation-source metadata and support consistent actions across all install types.

## 3. Recommended Approach

**Chosen Path:** Direct planning expansion with artifact synchronization.

This change is too large to treat as a single implementation story, but it does not require a full product restart. The correct BMAD action is to update planning artifacts in place and bring the planning set back to a coherent pre-development baseline.

### Why this path

1. The product direction is already decided.
2. The current conflict is between the new capability intent and the older planning baseline.
3. The fastest safe route is to synchronize PRD, architecture, and epics before generating new story contexts.

## 4. Detailed Change Proposals

### PRD

**OLD:** App installation is represented as an App Store initiated flow.  
**NEW:** App installation becomes a unified model with marketplace template, custom compose, and runtime-source deployment modes.

### Architecture

**OLD:** Installation is implied inside the general AppHub task model.  
**NEW:** Installation gets an explicit normalized domain model, policy-validation boundary, and runtime-profile abstraction.

### Epics and Stories

**OLD:** Epic 3 covers only App Store install, My Apps, application access, and settings.  
**NEW:** Epic 3 also includes custom compose install and PHP runtime-source deployment, with dedicated stories before downstream lifecycle completion.

## 5. Implementation Handoff

**Scope Classification:** Major planning change, implementation can proceed after story-context generation.

### Success Criteria

1. PRD, architecture, and epics describe the same three installation source types.
2. Security and policy constraints for custom compose are explicit.
3. Phase 1 runtime-source deployment scope is intentionally limited to curated PHP support.
4. The planning set is ready for create-story on the new Epic 3 installation stories.

## 6. Final Recommendation

Proceed next with story-context creation for the new flexible-installation slice in Epic 3, starting with custom compose upload/editing, custom compose execution, and PHP runtime-source deployment.
