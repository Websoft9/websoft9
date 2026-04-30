# Sprint Change Proposal: File Module Execution-Layer Correction

**Date:** 2026-04-30  
**Scope:** Moderate  
**Primary Affected Story:** Story 4.5 - Build the controlled file-management workspace

## 1. Issue Summary

The file-management module is functionally implemented and validated, but implementation feedback uncovered a material architecture mismatch in its execution layer. The current backend performs file operations by launching an ephemeral helper container for each file action. That approach preserves isolation, but it introduces repeated cold-start cost, request fan-out, script-fragment drift, and a larger debugging surface than intended for an operator-facing file workspace.

During implementation review, the team selected a corrected approach: keep AppHub as the only public API and policy boundary, but replace per-request helper-container execution with a long-lived internal `files-agent` style sidecar or equivalent warm bridge inside the current product runtime.

## 2. Impact Analysis

### Epic Impact

- Epic 4 remains the correct epic.
- Story 4.5 must be reopened because the accepted runtime approach for file execution changed.
- Story 4.6 and other privileged bridge stories are indirectly affected because they should follow the clarified bridge pattern: AppHub-owned API plus internal execution dependency, not repeated ad hoc helper-container startup.

### Story Impact

- Story 4.5 English and Chinese artifacts must replace helper-container wording with long-lived internal sidecar wording.
- Story 4.5 status should move from `done` back to `in-progress` because the accepted architecture is not fully implemented yet.
- Story 4.5 tasks and validation notes must explicitly record the remaining migration from ephemeral helper containers to a warm internal file-execution sidecar.

### Artifact Conflicts

- Architecture planning artifacts already allow the narrow sidecar exception for the file bridge.
- The Story 4.5 implementation artifact still states that helper-container execution is the approved implementation baseline.
- Epic 4 context should acknowledge the approved file-bridge exception so later stories do not reintroduce the old constraint.
- Sprint tracking must be synchronized to reflect that Story 4.5 has reopened.

### Technical Impact

- The public AppHub API surface stays unchanged.
- The backend execution layer should move toward an internal long-lived `files-agent` sidecar or equivalent warm bridge.
- Existing tests remain valuable but are incomplete for the corrected runtime pattern and will need follow-up updates during implementation.

## 3. Recommended Approach

**Chosen Path:** Direct adjustment with story reopening.

This is not a PRD rewrite and not a full replan. The product intent is unchanged. The correct action is to reopen Story 4.5, align the implementation artifact to the corrected architecture, and route the story back into development for execution-layer replacement.

### Rationale

1. The issue is architectural but tightly scoped to one implemented module.
2. The public API, UX intent, and security boundary remain valid.
3. Reopening the story is cheaper and clearer than inventing a parallel cleanup story with duplicated acceptance criteria.

### Risk Assessment

- **Low product risk:** UX and external contracts remain stable.
- **Moderate implementation risk:** execution-layer refactor touches privileged file operations and runtime wiring.
- **High benefit:** lower latency, lower debugging cost, and tighter consistency with the accepted runtime model.

## 4. Detailed Change Proposals

### Story 4.5

**OLD:** helper-container execution per request is treated as the implementation baseline.  
**NEW:** file operations must move to a long-lived internal `files-agent` sidecar or equivalent warm bridge; AppHub remains the only public API boundary.

**Additional story changes:**

- Reopen status from `done` to `in-progress`.
- Replace helper-container acceptance wording with sidecar wording.
- Add an explicit implementation task for replacing the ephemeral execution layer.
- Record that existing validation applies to the superseded helper-container version and must be rerun after sidecar migration.

### Epic 4 Context

**OLD:** new epic capabilities extend AppHub and avoid a parallel backend.  
**NEW:** preserve that rule, but explicitly allow a narrow internal file-bridge sidecar exception while keeping AppHub as the only public API and auth boundary.

### Sprint Tracking

**OLD:** Story 4.5 marked `done`.  
**NEW:** Story 4.5 marked `in-progress` until the sidecar execution-layer migration is implemented and revalidated.

## 5. Implementation Handoff

**Scope Classification:** Moderate

### Handoff Recipients

- **Developer agent:** replace helper-container execution with a long-lived internal file-execution sidecar or warm bridge, update tests, and revalidate runtime behavior.
- **Tech writer / documentation owner:** keep Story 4.5, Epic 4 context, and architecture artifacts synchronized with the accepted execution model.

### Success Criteria

1. Story 4.5 implementation artifact, Chinese working copy, Epic 4 context, and sprint tracking all describe the same sidecar-based execution model.
2. Story 4.5 remains reopened until the code matches the corrected architecture.
3. Follow-up implementation can proceed without ambiguity about helper containers versus warm sidecar execution.
