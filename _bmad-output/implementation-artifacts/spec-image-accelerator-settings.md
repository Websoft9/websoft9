---
title: 'Image accelerator settings'
type: 'feature'
created: '2026-09-07'
status: 'draft'
context:
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/implementation-artifacts/3-7-build-product-settings-and-the-sensitive-configuration-baseline.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The current Settings UI displays preloaded `mirrors.json` values as editable configuration, and uses a comma-delimited `config.ini` value that cannot associate an accelerator with optional credentials. Pull paths duplicate mirror parsing and cannot authenticate per accelerator.

**Approach:** Replace the editable list with platform-managed accelerator profiles and a row-based Settings UI. On a direct-pull failure, use ordered user profiles exclusively when any are enabled; otherwise use the invisible `mirrors.json` system fallback list.

## Boundaries & Constraints

**Always:** Direct image pulls precede every accelerator attempt. The Console displays only user-created accelerator profiles, initially empty. Each profile has a normalized root URL, optional username/password, enabled state, and explicit order. Passwords are write-only in API responses and logs. A profile with credentials authenticates only its individual pull or test request; do not call global `docker login`. User profiles take precedence over and must never fall through to `mirrors.json`; system mirrors are tried only when no enabled user profile exists. Apply the same selection rule to both application pull paths and Restic backup pulls.

**Ask First:** Halt before changing the selected persistence directory, adding a third-party frontend dependency, or altering the global Docker daemon configuration.

**Never:** Do not build private image-registry management, alter Compose image references, expose stored passwords in the browser, modify SSH behavior, or change unrelated Settings modules.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| No user profiles | Direct pull fails; no enabled user profile | Try normalized entries from local `mirrors.json` in file order | Report failure only after all system entries fail |
| User profiles exist | Direct pull fails; one or more enabled profiles | Try only enabled user entries by saved order | Do not try `mirrors.json` after user failures |
| Credentialed profile | Profile contains username and password | Test and accelerated pull carry that profile's one-request authentication | Do not log secrets; continue to next profile on authentication failure |
| Profile edit | Existing profile update omits password | Keep existing password and return only `has_password` | Reject malformed URL or incomplete new credential pair |
| Test | Saved or unsaved normalized profile | Probe registry `/v2/`, returning reachability, auth outcome, and elapsed milliseconds | Return safe, actionable error without credentials |

</frozen-after-approval>

## Code Map

- `apphub/src/services/image_accelerators.py` -- new platform-level SQLite persistence, validation, selection, test, and pull-auth helpers.
- `apphub/src/api/v1/routers/image_accelerators.py` -- authenticated profile CRUD, ordering, and test endpoints.
- `apphub/src/main.py` -- register the accelerator router and initialize its storage.
- `apphub/src/services/app_manager.py` -- replace duplicated configuration parsing with profile selection and per-request authentication for async and synchronous pulls.
- `apphub/src/services/back_manager.py` -- reuse selection and authentication for Restic pull fallback.
- `apphub/src/services/settings_manager.py` -- stop exposing `docker_mirror.url` and default mirror values in the Settings summary.
- `console/src/features/settings/settings-page.tsx` -- query and edit row-based accelerator profiles instead of the Chip editor.
- `console/src/features/settings/settings-page.css` -- style stable row layout, native drag state, inline feedback, and responsive controls.
- `console/src/shared/i18n/resources.ts` -- bilingual labels and safe test/save validation feedback.
- `apphub/tests/test_image_accelerators.py` -- persistence, secret masking, selection, migration, and request authentication behavior.

## Tasks & Acceptance

**Execution:**
- [ ] `apphub/src/services/image_accelerators.py`, `apphub/src/schemas/imageAccelerator.py` -- add validated SQLite-backed accelerator profiles, one-time legacy migration, invisible system fallback loading, and safe test/auth helpers.
- [ ] `apphub/src/api/v1/routers/image_accelerators.py`, `apphub/src/main.py` -- expose authenticated list/save/delete/reorder/test endpoints and initialize durable storage.
- [ ] `apphub/src/services/app_manager.py`, `apphub/src/services/back_manager.py`, `apphub/src/services/settings_manager.py` -- centralize consumption, remove `docker_mirror` from the visible settings summary, and preserve direct-first pull behavior.
- [ ] `console/src/features/settings/settings-page.tsx`, `console/src/features/settings/settings-page.css`, `console/src/shared/i18n/resources.ts` -- replace the mirror editor with add/edit/delete/test/reorder rows and write-only password fields using native drag and drop.
- [ ] `apphub/tests/test_image_accelerators.py` -- cover matrix cases plus no-secret API responses and the legacy `config.ini` transition.

**Acceptance Criteria:**
- Given the user opens Image Accelerator settings on a new install, when no user profile exists, then the list is empty and `mirrors.json` entries are not displayed.
- Given a user adds, edits, deletes, or reorders accelerators, when saving succeeds, then the next query and pull attempt retain those changes in the selected order.
- Given a configured user accelerator fails, when the direct image pull had already failed, then no system mirror is tried.
- Given no enabled user accelerator is configured, when a direct pull fails, then system mirrors provide the only fallback.
- Given a credentialed accelerator, when it is tested or used for an accelerated pull, then its stored credentials are applied without being exposed through the UI, API response, or logs.

## Spec Change Log

## Design Notes

Legacy `config.ini` must be read only once for migration. If its normalized sequence exactly equals the local system mirror sequence, do not create user profiles; otherwise import the sequence as anonymous user profiles. Mark migration complete so legacy values can never override profiles later.

## Verification

**Commands:**
- `cd apphub && pytest tests/test_image_accelerators.py` -- expected: profile, migration, selection, and secret-handling tests pass.
- `cd apphub && python3 -m py_compile src/services/image_accelerators.py src/api/v1/routers/image_accelerators.py src/services/app_manager.py src/services/back_manager.py src/services/settings_manager.py` -- expected: no syntax errors.
- `cd console && npm run typecheck && npm run lint && npm run i18n:check` -- expected: type, lint, and translation checks pass.