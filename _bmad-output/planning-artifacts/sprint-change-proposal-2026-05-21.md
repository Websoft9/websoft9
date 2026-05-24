# Sprint Change Proposal: Console Visual System Enforcement and Priority Page Convergence

**Date:** 2026-05-21  
**Scope:** Major  
**Primary Affected Area:** Epic 4 - Product-Native Operations and Observability Expansion

## 1. Issue Summary

The current planning set already contains Story 4.3A for design-system foundation and Story 4.3B for the product visual system and canonical page families. Those stories established direction, but they did not create a durable enforcement layer for implementation. As a result, the console still drifts page by page.

The current operator-visible problem is not the absence of design intent. It is the absence of a shared implementation contract for tokens, panels, form controls, spacing, and first-wave page adoption.

This mismatch is now visible in production-facing pages such as overview, App Store, My Apps, settings, services, and logs. Those pages still carry duplicated page-local tokens, duplicated field styling, and inconsistent surface geometry even though the platform already claims a unified visual system.

## 2. Impact Analysis

### UX / Product Impact

- Operators still experience the console as a set of individually designed admin screens rather than one coherent product.
- High-visibility native pages do not reliably inherit the same spacing, control, and panel grammar.
- Each new page implementation still has room to invent its own local style contract.

### Architecture / Frontend Impact

- The current shared design-system layer is treated as optional instead of authoritative.
- Design tokens are duplicated across feature CSS files instead of being sourced from one shared layer.
- Repeated MUI field overrides increase drift and raise the cost of future UI-heavy stories.

### Planning / Delivery Impact

- Sprint tracking currently omits Story 4.3A and 4.3B from `sprint-status.yaml`, which hides the real redesign progression.
- The project needs one execution story that turns 4.3A foundation and 4.3B visual direction into an enforced implementation baseline.

## 3. Recommended Approach

**Chosen Path:** Add one execution story for enforcement and first-wave adoption.

The correct next step is not another abstract UX document and not a full redesign restart. The correct step is a focused implementation story that:

1. Centralizes shared design tokens for the console.
2. Establishes a reusable shared field-style helper for product-native forms.
3. Migrates first-wave native pages to that shared token and surface contract.
4. Updates sprint tracking so redesign work is visible and auditable again.

## 4. Detailed Change Proposals

### Epic / Story Adjustment

**OLD:** Epic 4 has design direction stories, but no explicit enforcement story that converts that direction into shared implementation rules.

**NEW:** Add Story 4.3C: `Enforce shared design tokens and priority-page convergence`.

### Frontend Implementation Adjustment

**OLD:** Page-local CSS variables and page-local TextField styling remain common practice.

**NEW:** Shared console tokens and shared field styling become the default path for priority product-native pages.

### Tracking Adjustment

**OLD:** `sprint-status.yaml` does not include Story 4.3A or 4.3B, so the redesign track is partially invisible.

**NEW:** `sprint-status.yaml` explicitly tracks 4.3A, 4.3B, and 4.3C.

## 5. Implementation Handoff

**Scope Classification:** Major execution adjustment inside the current sprint path.

### Success Criteria

1. Shared console tokens exist in one authoritative frontend layer.
2. Shared product form-field styling is reusable instead of copied page by page.
3. Overview, App Store, My Apps, settings, services, and logs adopt the shared token layer.
4. Sprint tracking reflects the actual redesign execution path.

## 6. Final Recommendation

Proceed with Story 4.3C as the enforcement story between the abstract redesign direction and continued feature development. Treat it as the minimum bar for preventing more page-level visual drift in Epic 4 and later UI-heavy stories.