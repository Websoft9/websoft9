---
title: 'Story 4.3: Build the basic user-management entry'
type: 'feature'
created: '2026-04-28'
status: 'done'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `users` module is currently only a protected shell placeholder. Story 4.2 created a reusable product-owned operator/session baseline, but administrators still cannot manage product-side accounts needed for future protected flows.

**Approach:** Replace the `users` placeholder with a minimal native user-management module that reuses the existing operator storage and session model. Extend AppHub with focused user-management endpoints and build a shell-aligned page that supports create, disable, password reset, and delete without introducing RBAC, host-account coupling, or a storage redesign.

## Boundaries & Constraints

**Always:** Reuse the operator record shape, disabled/deleted semantics, reset-password eligibility, and forced session invalidation behavior from Story 4.2; keep product-side users decoupled from host accounts and Cockpit sessions; keep persistence inside the existing product-auth storage boundary; keep the feature inside the current shared shell and bilingual resource model; preserve the existing protected-route gate for `users`.

**Ask First:** Expanding beyond the four required actions; introducing roles, permissions, or ownership matrices; adding a database or replacing JSON persistence; exposing host-user management or Linux account linkage; changing the protected-module set.

**Never:** Build full RBAC; bypass the existing product-auth guard; store raw passwords or return password material to the frontend; let operators disable or delete the only remaining active account without a deliberate safety rule; create a second parallel identity store.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LIST_USERS | Authenticated operator opens `users` page with initialized product auth | Page loads current product-side operators and shows available actions per user | Backend returns auth/user-management errors through existing error envelope |
| CREATE_USER | Valid username, display name, and password for a new operator | New operator is persisted, visible in the list, and audit metadata is recorded | Reject duplicate/invalid usernames and invalid payload with stable 4xx response |
| DISABLE_ACTIVE_USER | Operator disables another existing active user | User becomes disabled, active sessions for that user are invalidated, and future protected access is denied | Reject disabling the last active operator account |
| RESET_PASSWORD | Operator resets another user's password | Password hash is replaced, existing sessions are invalidated, and user can log in with the new password | Reject missing target, invalid password, or action on deleted user |
| DELETE_USER | Operator deletes a user that is no longer needed | User is marked deleted, active sessions are invalidated, and the entry no longer behaves as an active account | Reject deleting the last active operator account |
| SELF_IMPACT_GUARD | Current operator targets self for disable/delete/reset | System handles the action consistently with session invalidation and safety rules | If the action invalidates current session, the frontend must fall back through the existing auth flow rather than hanging on stale state |

</frozen-after-approval>

## Code Map

- `apphub/src/services/product_auth.py` -- existing operator/session storage, hashing, audit, and invalidation logic to extend for CRUD-style management.
- `apphub/src/api/v1/routers/auth.py` -- current product-auth API surface and the most direct place to expose user-management endpoints.
- `apphub/src/schemas/productAuth.py` -- current operator and auth DTOs; add request/response models for list/create/disable/reset/delete flows.
- `apphub/tests/test_product_auth.py` -- focused regression suite already covering auth/session behavior; extend with user-management edge cases.
- `console/src/app/router/index.tsx` -- current `users` route still points to a placeholder wrapped by the product-auth guard.
- `console/src/shared/i18n/resources.ts` -- shared bilingual strings for route labels, auth copy, and the upcoming users surface.
- `console/src/features/product-auth/product-auth-provider.tsx` -- existing authenticated status source; likely place to reuse refresh behavior after destructive user actions.
- `console/src/app/shell/app-shell.tsx` -- current shell user menu consumes product-auth state and may need refresh-safe behavior if the current session is invalidated by a self-action.

## Tasks & Acceptance

**Execution:**
- [x] `apphub/src/schemas/productAuth.py` -- add user-management request/response DTOs for list, create, disable, reset-password, and delete operations -- keep validation aligned with the existing operator model.
- [x] `apphub/src/services/product_auth.py` -- implement operator listing and management methods with audit logging, last-active-user safety checks, and forced session invalidation on account changes -- extend the existing identity boundary instead of replacing it.
- [x] `apphub/src/api/v1/routers/auth.py` -- expose focused authenticated endpoints for the user-management action set -- keep the API surface close to the current product-auth contract.
- [x] `apphub/tests/test_product_auth.py` -- add regression coverage for create, disable, password reset, delete, duplicate/invalid input, and last-active-user protection -- lock the edge-case matrix into executable checks.
- [x] `console/src/features/users/users-page.tsx` -- replace the `users` placeholder with a minimal native management page showing list and action flows -- deliver the actual module entry promised by Story 4.3.
- [x] `console/src/app/router/index.tsx` -- route `users` to the native page while preserving the existing product-auth guard -- switch from placeholder wiring to functional module entry.
- [x] `console/src/shared/i18n/resources.ts` -- add bilingual strings for the user list, dialogs/forms, empty/error states, and action feedback -- keep the page aligned with the shared shell localization contract.
- [x] `console/src/features/product-auth/product-auth-provider.tsx` and/or `console/src/app/shell/app-shell.tsx` -- ensure current-session refresh behavior stays correct if a self-targeted reset/disable/delete invalidates the live session -- prevent stale-auth UI after destructive account actions.

**Acceptance Criteria:**
- Given product-side authentication is enabled and an authenticated administrator opens the `users` route, when the page loads, then the route renders a native user-management page instead of a shell placeholder and exposes create, disable, reset-password, and delete actions.
- Given an administrator creates or mutates a product-side user, when AppHub accepts the action, then the operator store, audit trail, and frontend list stay consistent without introducing RBAC or host-account coupling.
- Given a user is disabled or deleted, when that user continues or attempts a protected-module session, then access is denied because the existing session invalidation path has been applied.
- Given the requested action would remove the last active operator account, when the backend evaluates the mutation, then the action is rejected with a stable client-facing error instead of leaving the product without an active administrator.

## Spec Change Log

- 2026-04-28: Backend user-management mutations initially deadlocked because session invalidation re-entered a non-reentrant lock. Switched the shared product-auth lock to `threading.RLock()` so disable, reset-password, and delete can invalidate sessions inside the same service boundary without hanging the regression suite. Keep the existing single shared lock boundary for storage consistency.

## Design Notes

Use the existing auth service as the ownership boundary for all operator mutations. The frontend should stay intentionally light: one list surface, a create form, and action affordances that call the focused backend endpoints and then refresh authoritative status/list data instead of maintaining a second local identity model.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_product_auth.py` -- expected: all auth and user-management regression tests pass
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/api/v1/routers/auth.py src/services/product_auth.py src/schemas/productAuth.py` -- expected: touched backend files compile cleanly
- `cd /workspace/websoft9/console && npm run build` -- expected: users page and updated auth/session flows compile successfully

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Reused the Story 4.2 product-auth boundary instead of introducing a second user store or a database-backed redesign.
- Added AppHub user-management endpoints for list, create, disable, reset-password, and delete, with last-active-operator safety checks and forced session invalidation on destructive changes.
- Extended the focused `test_product_auth.py` suite to cover the Story 4.3 CRUD path, duplicate username rejection, unauthenticated access rejection, and last-active-operator protection.
- Replaced the `users` shell placeholder with a native page that supports create, disable, reset-password, and delete actions while staying under the existing product-auth route guard.
- Added bilingual copy for the new user-management surface and confirmed the frontend refresh path handles self-impacting actions by re-reading authoritative auth state.

### File List

- _bmad-output/implementation-artifacts/4-3-build-the-basic-user-management-entry.md
- _bmad-output/implementation-artifacts/epic-4-context.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/api/v1/routers/auth.py
- apphub/src/schemas/productAuth.py
- apphub/src/services/product_auth.py
- apphub/tests/test_product_auth.py
- console/src/app/router/index.tsx
- console/src/features/users/users-page.tsx
- console/src/shared/i18n/resources.ts

### Change Log

- 2026-04-28: Compiled Epic 4 context and created the Story 4.3 BMAD implementation artifact.
- 2026-04-28: Implemented minimal product-side user management in AppHub and the console, then validated with focused auth tests and a production console build.