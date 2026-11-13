---
title: 'Switch Websoft9 to AGPL-3.0'
type: 'chore'
created: '2026-11-13'
status: 'done'
route: 'plan-code-review'
baseline_commit: '2cc4b430bedc1470a6a251d6a5eacdc20f50b8b1'
context: []
---

# Switch Websoft9 to AGPL-3.0

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The current LGPL license file adds a cloud-marketplace distribution restriction, which is inconsistent with the intended open-source licensing model and README claims.

**Approach:** Replace the repository license with standard GNU AGPL version 3.0, update the README license badge, and add an Open Source section that identifies the license and confirms there are currently no user-count or application-installation limits for the open-source edition.

## Boundaries & Constraints

**Always:** Use the unmodified AGPL-3.0-only terms; do not retain the marketplace restriction; preserve separate third-party component licensing.

**Ask First:** No additional licensing or commercial policy changes.

**Never:** Do not imply the AGPL applies to third-party components bundled in the product.

</frozen-after-approval>

## Code Map

- `LICENSE.md` -- repository's full license text.
- `README.md` -- license badge and user-facing open-source information.

## Tasks & Acceptance

**Execution:**
- [x] `LICENSE.md` -- replace LGPL and its added restriction with standard AGPL-3.0-only text.
- [x] `README.md` -- replace the License section with Open Source details, update the badge, and state there are no current user or installed-app count limits.

**Acceptance Criteria:**
- Given the repository license file, when inspected, then it contains the standard AGPL version 3.0 text without the marketplace restriction.
- Given the README, when a user checks the Open Source section, then it names AGPL-3.0 and explicitly says the open-source edition has no user-count or installed-application-count limits.
- Given the README's license badge, when clicked, then it identifies AGPL v3 and links to the AGPL license.

## Verification

**Commands:**
- `git diff --check` -- expected: no whitespace errors.
- Compare `LICENSE.md` against the canonical AGPL-3.0-only text, accounting only for the repository copyright notice.

## Suggested Review Order

**License and user-facing statement**

- Start with the README badge and Open Source text to confirm the public-facing license and edition limits.
  [`README.md:10`](../../README.md#L10)

- Check the complete license text that governs Websoft9.
  [`LICENSE.md:1`](../../LICENSE.md#L1)
