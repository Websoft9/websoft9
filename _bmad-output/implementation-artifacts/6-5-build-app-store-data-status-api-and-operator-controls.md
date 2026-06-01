# Story 6.5: Build App Store Data Status API and Operator Controls

## Status

ready-for-dev

## Story

As an operator,
I want to inspect current version, available version, sync stage, and failure reason, and manually trigger check, sync, and rollback,
so that I can independently manage App Store data updates.

## Acceptance Criteria

1. When an operator inspects App Store data status, the system returns current active version, previous version, latest compatible version, current stage, and the most recent failure summary.
2. When an operator triggers check-only, sync, or rollback, the system reports the result through one unified task or state model.
3. When the system is in incompatible, failed, or rolled-back state, the operator sees an explicit diagnosis instead of a vague failure banner.

## Dependencies

- Story 6.3 provides runtime sync and base state.
- Story 6.4 makes runtime-derived install data a formal upgrade step.

## Implementation Tasks

1. Define the status API response model and stage fields. (AC: 1)
2. Provide check, sync, and rollback control entry points. (AC: 2)
3. Standardize failure summaries and stage information. (AC: 3)

## Definition of Done

- Operator-visible state is complete.
- Manual control entry points are available.
- Failure diagnosis is explicit.
