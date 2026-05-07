---
title: 'Story 2.6: Unify integration readiness and session prewarm'
type: 'feature'
created: '2026-05-07'
status: 'done'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Gitea, Portainer, and Nginx Proxy Manager already use one backend session bridge, but the browser session bootstrap still happens lazily when each embedded workspace is opened. That creates repeated per-page bootstrap waits and makes integration continuity feel fragmented instead of product-owned.

**Approach:** Keep system-start initialization and browser-session bootstrap as separate responsibilities. The product runtime should continue to initialize service accounts, credentials, endpoints, and proxy conditions at startup, while the Websoft9 shell should trigger one unified integration-session prewarm after product-auth succeeds. AppHub should expose one bulk bootstrap contract that seeds all supported integration sessions in one response, and the current per-integration bootstrap path should remain as a fallback for retry and expiry recovery.

## Boundaries & Constraints

**Always:** Keep AppHub as the only public API layer; preserve product-auth as the gate before any browser-side integration prewarm runs; keep Gitea, Portainer, and NPM on one shared backend bridge instead of reintroducing frontend-owned login flows; preserve the current per-integration bootstrap endpoint as a fallback path; keep browser-session prewarm separate from runtime service bootstrap; keep bilingual shell-resource patterns.

**Ask First:** Replacing third-party embedded workspaces with native product pages in this slice; removing all per-integration retry logic; introducing new external dependencies; moving browser session materialization into product-container startup hooks.

**Never:** Attempt to create browser cookies or localStorage during container startup; force iframe pages to own their own login protocols again; make one integration prewarm failure block the entire shell; collapse service-readiness validation and browser-session bootstrap into one undocumented side effect.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| AUTH_SUCCESS_PREWARM | Product-auth status is authenticated | Shell triggers one bulk integration bootstrap for Gitea, Portainer, and NPM | Partial failures are recorded per integration without breaking the shell |
| BULK_BOOTSTRAP_SUCCESS | All integrations reachable and credentials valid | Browser receives the required cookies and token bridge state before opening embedded workspaces | Workspace pages open without repeating the first bootstrap wait |
| PARTIAL_BOOTSTRAP_FAILURE | One integration is unavailable or credentials are invalid | Successful integrations remain prewarmed; failed one stays diagnosable and retryable | Failure is isolated to the affected integration |
| SESSION_EXPIRED_AFTER_PREWARM | Existing prewarmed session expires later | Existing per-integration bootstrap still retries on demand from the workspace route | No hard dependency on one-shot startup bootstrap |
| AUTH_LOGOUT | User logs out of product auth | Product-owned integration prewarm cache is cleared for the browser session | Later users do not inherit stale session state |
| AUTH_STATUS_LOADING | Product-auth state not resolved yet | No prewarm request is sent until authenticated state is confirmed | Avoid premature session bootstrap attempts |

</frozen-after-approval>

## Code Map

- `apphub/src/services/integration_session_bridge.py` -- shared bridge that already knows how to bootstrap Gitea, Portainer, and NPM; extend it with a bulk bootstrap contract rather than branching into separate services.
- `apphub/src/api/v1/routers/integrations.py` -- current per-integration session endpoint; add a bulk endpoint here and keep the single-integration endpoint intact for fallback recovery.
- `apphub/src/main.py` -- current auth bypass already allows `/api/integrations/`; keep the new bulk endpoint inside the same boundary.
- `console/src/features/product-auth/product-auth-provider.tsx` -- product-auth success boundary; best place to trigger one unified post-auth prewarm without coupling it to a single integration page.
- `console/src/features/integrations/use-integration-session.ts` -- current per-workspace bootstrap hook; should learn to reuse bulk-prewarm state first and only hit the per-integration fallback when necessary.
- `console/src/features/integrations/integration-workspace-page.tsx` -- workspace shell should stay compatible with fallback retry when a prewarmed session later expires.
- `console/src/shared/i18n/resources.ts` -- add any shell-level copy required for prewarm or recovery states if the current wording becomes inaccurate.
- `apphub/tests/` -- add focused regression coverage for the bulk bootstrap API and partial-failure behavior.

## Tasks & Acceptance

**Execution:**
- [x] `apphub/src/services/integration_session_bridge.py` -- add a bulk bootstrap method that runs all supported integrations and returns per-integration results plus all cookies that should be written to the response.
- [x] `apphub/src/api/v1/routers/integrations.py` -- add a bulk session bootstrap endpoint for the authenticated shell and keep the existing per-integration endpoint unchanged for retry fallback.
- [x] `apphub/tests/` -- add focused tests for bulk success, partial failure isolation, and response cookie emission.
- [x] `console/src/app/shell/app-shell.tsx` and `console/src/features/integrations/integration-session-bootstrap.ts` -- trigger unified integration prewarm once product-auth reaches authenticated shell state, and clear cache when the shell exits.
- [x] `console/src/features/integrations/use-integration-session.ts` -- reuse bulk-prewarm completion state before falling back to the single-integration session bootstrap path.
- [x] `console/src/features/integrations/` -- keep workspace-level retry and degraded-state handling intact so expired sessions or later failures still recover locally.
- [x] `console/src/shared/i18n/resources.ts` -- existing wording remains acceptable for this slice, so no copy change was required.

**Acceptance Criteria:**
- Given a user has authenticated into Websoft9, when the shell initializes, then Websoft9 performs one unified integration session prewarm for Gitea, Portainer, and NPM instead of waiting for the first visit to each workspace.
- Given one integration prewarm fails while others succeed, when the shell continues loading, then successful integrations remain usable and the failed integration still exposes explicit retry and diagnostics behavior.
- Given an integration session later expires after the initial prewarm, when the user opens that workspace, then the existing per-integration bootstrap path still refreshes the session without breaking other integrations.
- Given Websoft9 product runtime starts or restarts, when no browser session exists yet, then runtime initialization validates service readiness and credentials but does not attempt to materialize browser cookies or localStorage ahead of user auth.

## Spec Change Log

- 2026-05-07: Story created to move integration continuity from per-workspace lazy bootstrap to a product-auth-triggered unified prewarm while preserving local fallback recovery.
- 2026-05-07: Implemented the bulk integration bootstrap API, auth-shell prewarm trigger, workspace fallback reuse, regression tests, and live runtime validation.

## Design Notes

The main architectural split in this story is deliberate. Runtime initialization owns service readiness, default-account creation, endpoint bootstrap, and proxy correctness. Browser session bootstrap owns cookies, JWTs, and localStorage-compatible continuity for the specific authenticated browser session. Treating those as two separate layers keeps the model honest and avoids trying to solve browser state during container startup.

The safest implementation path is additive. AppHub already has one bridge that can bootstrap each integration individually. This story should extend that bridge with a bulk contract rather than replace it. The frontend should then consume the bulk prewarm once per authenticated shell session and keep the current per-workspace session hook as a fallback for expiry and diagnostics recovery.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_integrations.py` -- expected: bulk bootstrap success and partial-failure tests pass.
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/api/v1/routers/integrations.py src/services/integration_session_bridge.py src/main.py` -- expected: touched backend files compile cleanly.
- `cd /workspace/websoft9/console && npm run build` -- expected: auth-shell prewarm and workspace fallback logic compile successfully.
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh` -- expected: updated auth shell and integration session flow are deployed into the running product container.

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Added a bulk AppHub integration bootstrap contract at `/api/integrations/session` that emits per-integration results and writes all required browser cookies in one response.
- Added focused backend regression tests for bulk success and partial-failure isolation.
- Added a shared frontend integration-session bootstrap cache so the authenticated shell prewarms Gitea, Portainer, and NPM once and each workspace reuses the result before falling back to the single-integration endpoint.
- Kept the existing per-workspace bootstrap path intact for post-prewarm expiry and retry recovery.
- Revalidated the slice with focused backend tests, backend compile checks, console build, live hot-sync, direct live API probing, and browser checks for repository, containers, and gateway embedded workspaces.
- Performed a post-implementation self-review and only kept one follow-up adjustment: cache now clears when the shell unmounts so browser-session bootstrap state does not survive logout.
- Tightened the first-entry experience for direct login redirects into `/containers`, `/gateway`, or `/repository` by moving integration prewarm earlier into the login/setup success path before navigation.

### File List

- _bmad-output/implementation-artifacts/2-6-unify-integration-readiness-and-session-prewarm.md
- _bmad-output/implementation-artifacts/2-6-unify-integration-readiness-and-session-prewarm_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/services/integration_session_bridge.py
- apphub/src/api/v1/routers/integrations.py
- apphub/tests/test_integrations.py
- console/src/app/shell/app-shell.tsx
- console/src/features/integrations/integration-session-bootstrap.ts
- console/src/features/integrations/use-integration-session.ts

### Change Log

- 2026-05-07: Story created and marked in-progress for implementation.
- 2026-05-07: Story completed after backend/frontend validation, live deployment, browser verification, and post-implementation cache cleanup.
- 2026-05-07: Follow-up refinement moved integration prewarm into the login redirect path for direct integration destinations, which removed the visible first-entry bootstrap card in the validated `/auth/login?next=/containers` flow.