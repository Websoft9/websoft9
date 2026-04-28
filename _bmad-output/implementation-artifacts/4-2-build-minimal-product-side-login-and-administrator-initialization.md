# Story 4.2: Build minimal product-side login and administrator initialization

## Status

done

## Story

As a first-time administrator,
I want Websoft9 to provide minimal product-side login and initialization when a migrated flow truly requires it,
so that high-risk actions no longer rely on host users or Cockpit sessions.

## Acceptance Criteria

1. Given the current flow requires product-side authentication, when the system detects that no operator account exists, then it enters an initialization path for the first administrator or operator, and protected areas are not accessible without the resulting product-side session.
2. Given a user tries to open a protected module without a valid session, when the request is evaluated, then the system blocks access to that module, and the old Cockpit session model no longer acts as a bypass.

## Dependencies

- Epic 1 and Epic 2 already established the unified shell, route tree, and product-owned integration workspace boundary.
- Story 3.7 already introduced a native settings surface and a masked-configuration baseline inside the new console.
- The current shell already reserves top-level routes for `users`, `files`, `terminal`, `services`, and `logs`, which are the best initial candidates for product-side protection.
- There is no existing product-side operator account or session service in AppHub yet; the story must not piggyback on Cockpit session state or host Linux users.
- Story 4.3 depends on this story to supply the operator bootstrap, login session, and protected-module gate.

## Scope Guardrails

- The feature must be driven by an explicit product-side auth enablement decision, not by implicit route heuristics.
- The initial protected-module baseline for this story is `users`, `files`, `terminal`, `services`, and `logs`; expanding or shrinking that list should be treated as a separate planning decision.
- The identity model introduced here must already support later multi-user continuity by defining reusable user records, disabled-state semantics, password-reset eligibility, and session invalidation behavior, even if Story 4.3 is the first place that exposes full user-management UI actions.
- Operator accounts, password hashes, and session secrets must be stored in product-owned persistence that is clearly separable from third-party integration credentials and traceable in later backup, restore, and upgrade work.

## Current Slice Summary

- The current router still renders `users` through a placeholder shell route, so the module entry exists but has no auth gate or native user-management implementation yet.
- The shell copy in `console/src/shared/i18n/resources.ts` already describes settings and user-management as product-owned capabilities, which means the UX surface is prepared conceptually but not functionally.
- Runtime bootstrapping for Portainer and NPM already stores third-party credentials in product-owned files, which is a useful delivery reference for first-admin bootstrap storage patterns, but those credentials must stay separate from Websoft9 operator accounts.
- AppHub currently brokers third-party sessions through `integration_session_bridge.py`, but there is no equivalent internal operator identity service; Story 4.2 needs to introduce that boundary explicitly rather than extending integration login tricks inward.
- The current refactor plan already places backup, restore, and upgrade work in later epics, so the new auth persistence layer must declare from day one which files or records belong to operator accounts, password hashes, session keys, and session state.

## Implementation Tasks

- [x] Add a product-side auth capability decision and initialization-status contract in AppHub, so the frontend can determine whether the product-owned auth flow is active and whether an operator account already exists. (AC: 1)
- [x] Introduce a reusable operator-account model in AppHub that can grow into Story 4.3 without replacing storage shape, including unique identity, password hash, disabled flag, deletion semantics, created-by metadata, and reset-password eligibility. (AC: 1, 2)
- [x] Introduce minimal operator bootstrap and login endpoints in AppHub, including first-admin initialization, credential verification, logout, current-session lookup, and explicit session invalidation when account state changes. (AC: 1, 2)
- [x] Establish a product-side session model independent from Cockpit and host users, using HTTP-only session cookies or an equivalent server-owned session mechanism, and define where session secrets and server-side session records persist. (AC: 1, 2)
- [x] Add a console auth gate and route-guard baseline so the protected-module baseline of `users`, `files`, `terminal`, `services`, and `logs` requires a valid product-side session whenever the feature is enabled. (AC: 1, 2)
- [x] Build the minimal frontend initialization and login views for the first operator and returning operator, keeping them inside the shared shell conventions without reintroducing legacy plugin dependencies. (AC: 1, 2)
- [x] Record audit-friendly metadata for bootstrap, login, logout, denied access, and forced session invalidation events at the service boundary, without widening this story into full RBAC or broad admin analytics. (AC: 1, 2)
- [x] Define how operator-account data, password hashes, session secrets, and session state participate in backup, restore, and upgrade boundaries so later stories do not invent incompatible persistence rules. (AC: 1, 2)

## Validation Notes

- Expected after implementation: `cd /workspace/websoft9/console && npm run build`
- Expected after implementation: `cd /workspace/websoft9/apphub && python3 -m py_compile src/api/v1/routers src/services src/schemas`
- Manual validation target: first-run bootstrap enters administrator initialization when no operator exists; running bootstrap again is idempotent and does not create a second first-admin path; login failure returns a stable rejection; logout clears access to the protected-module baseline; current-session lookup reflects session state accurately; existing Cockpit session alone does not unlock protected modules.
- Manual validation target: disabling or deleting a product-side operator record invalidates any active session for that account, even if Story 4.3 UI is not shipped yet.
- Manual validation target: operator account data, password hashes, and session secrets are stored separately from Portainer, Gitea, and NPM integration credentials and are documented as product-owned recoverable assets.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Story created from Epic 4 user-module planning track.
- Story 4.2 is intentionally treated as the first executable prerequisite for the user module even though Epic 4 also contains Story 4.1.
- Story 4.3 should not be implemented before this story lands, because product-side user actions require a product-side identity baseline.
- Implemented AppHub product auth status, initialize, login, session, and logout endpoints with operator persistence, audit events, and forced session invalidation support.
- Implemented product-owned route guards and minimal setup/login pages for `users`, `files`, `terminal`, `services`, and `logs`, and wired shell user controls to the new operator session.
- Hardened internal gateway trust to use a shared trust-key file instead of a bare internal marker, and aligned single-container and split-container gateway paths to the same trust mechanism.
- Validated with `pytest -q -o addopts='' tests/test_product_auth.py`, `python3 -m py_compile src/main.py src/api/v1/routers/auth.py src/services/product_auth.py src/schemas/productAuth.py src/core/request_auth.py`, `npm run build`, shell-script syntax checks, compose manifest validation, and live single-container runtime checks for `/api/auth/status` plus direct-header spoof rejection.

### File List

- _bmad-output/implementation-artifacts/4-2-build-minimal-product-side-login-and-administrator-initialization.md
- _bmad-output/implementation-artifacts/4-2-build-minimal-product-side-login-and-administrator-initialization_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/api/v1/routers/auth.py
- apphub/src/config/config.ini
- apphub/src/core/request_auth.py
- apphub/src/main.py
- apphub/src/schemas/productAuth.py
- apphub/src/services/product_auth.py
- apphub/tests/test_product_auth.py
- console/src/app/providers/app-providers.tsx
- console/src/app/router/index.tsx
- console/src/app/shell/app-shell.tsx
- console/src/features/product-auth/product-auth-page.tsx
- console/src/features/product-auth/product-auth-provider.tsx
- console/src/features/product-auth/product-auth-route-guard.tsx
- console/src/shared/i18n/resources.ts
- docker/docker-compose.yml
- docker/product/gateway/platform-gateway-routes.conf
- docker/product/proxy/config/platform-gateway-routes.conf
- docker/product/scripts/platform-sync-config.sh
- docker/proxy/config/platform-gateway-routes.conf
- docker/proxy/init_nginx.sh

### Change Log

- 2026-04-27: Created Story 4.2 as the BMAD-ready prerequisite for the user module and clarified the 4.2 -> 4.3 dependency inside Epic 4.
- 2026-04-27: Implemented product-owned operator bootstrap, session-backed protected-module gate, gateway trust hardening, split-container compatibility, and runtime validation for Story 4.2.