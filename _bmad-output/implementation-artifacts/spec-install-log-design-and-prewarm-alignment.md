---
title: 'Installation log layout and prewarm confirmation alignment'
type: 'feature'
created: '2026-10-08'
status: 'done'
route: 'one-shot'
---

# Installation log layout and prewarm confirmation alignment

## Intent

**Problem:** The cancelled-prewarm retry confirmation was centered vertically while Scheduled Tasks deletion appeared near the workspace top. Installation logs had an oversized title, English stage/actions in Chinese mode, bottom-aligned output, and only a short tail from the latest stage.

**Approach:** Align the shared retry dialog to the workspace top plus 16px with width min(480px, workspace width minus 24px). Reorganize installation logs into a compact title/stage band, continuous scrollable output, and responsive status/actions footer. Preserve error conclusions and source details. Show recent 500 lines across stages, while copying and exporting all available stages. Add Lucide copy/download/close controls, localized stage/status labels, and a follow-output switch that pauses on upward scrolling. Keep real cancellation semantics unchanged and disable the cancel button during submission. Remove repeated structured status/ID fields from formatted lines and retain progress units. Use the mounted log node for initial following because the dialog is portaled.

Validation:
- Production build and touched-file editor diagnostics passed; deployed frontend only to websoft9-dev.
- Actual Scheduled Tasks retry and delete dialogs both measured x=590, y=76, width=480 at 1440x900.
- Authenticated desktop checks verified follow, pause, resume, and copy/export payload equality. Clipboard and anchor operations were captured by browser-only test substitutes; operating-system clipboard and saved downloads were not tested.
- At 390x844, actual cancelled logs and error summaries remained in the viewport. The log dialog measured x=12, width=366, height=607.67; text and controls did not overflow. Screenshots inspected on desktop and mobile.
- Browser-only installing sample with 620/621 lines rendered exactly 500 rows; new output did not move the paused scroll position; resuming followed the bottom. Mocked cancellation submitted once with the button disabled. No real cancellation POST was issued. Test substitutions were restored and the page reloaded.
- Four formatter cases passed: repeated status/ID, distinct error/details, raw string, numeric progress. Installation-dialog English/Chinese parity passed for 36 keys.
- Full i18n:check remains blocked by two pre-existing Chinese date strings in my-app-access-panel.tsx (lines 154, 178); unrelated file not modified. npm install reported 11 audit advisories; no unrelated dependency upgrades attempted.

## Suggested Review Order

1. [Retry dialog](../../console/src/shared/design-system/prewarm-resume-dialog.tsx): top alignment and width matching Scheduled Tasks deletion, standard focus and Escape handling retained.
2. [Installation logs](../../console/src/features/my-apps/my-apps-page.tsx): structured formatting, three-part layout, mounted-node following, full export and cancellation submission guard.
3. [Translations](../../console/src/shared/i18n/resources.ts): stage, status, clipboard and cancel feedback parity.
4. [Dependencies](../../console/package.json): Lucide icons for log tool controls.