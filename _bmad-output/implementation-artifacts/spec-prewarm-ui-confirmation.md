---
title: 'Prewarm button consistency and cancelled retry confirmation'
type: 'bugfix'
created: '2026-10-08'
status: 'done'
route: 'one-shot'
---

# Prewarm button consistency and cancelled retry confirmation

## Intent

**Problem:** The App Store prewarm button did not match neighboring secondary actions. Retrying a cancelled prewarm required an explicit confirmation in both App Store and Scheduled Tasks.

**Approach:** Match the favorite button's secondary styling and reuse a scoped confirmation dialog with localized text. Confirm only cancelled retries; failed retries remain direct. Disable the App Store action until its status lookup succeeds, resetting stale status when the selected application or version changes. Escape dismisses the confirmation without closing the installation form. Keep dispatch and retention behavior unchanged.

Validation: production build and forced TypeScript check passed. Desktop computed styles matched the favorite button. Authenticated browser checks with narrowly mocked POST requests confirmed cancel sends zero requests and confirm sends one request. A deliberately held initial status response kept the action disabled and prevented confirmation bypass. At 390x844, the confirmation occupied x=12, width=366; footer controls stayed within the viewport. Final mobile action checks used DOM click events because the hidden integrated browser stopped Playwright stability checks. Screenshots were inspected and test fetch hooks removed. The editor retained an unconfirmed module-resolution diagnostic despite a clean forced compiler check.

## Suggested Review Order

1. [App Store flow](../../console/src/features/app-store/app-store-page.tsx): secondary button styling, status readiness guard, cancelled retry routing and underlying overlay close handling.
2. [Shared confirmation](../../console/src/shared/design-system/prewarm-resume-dialog.tsx): standard scoped dialog, accessible title and description, cancel and confirm controls.
3. [Scheduled Tasks flow](../../console/src/features/scheduled-tasks/scheduled-tasks-page.tsx): desktop/mobile retry actions and duplicate submission guard.
4. [Translations](../../console/src/shared/i18n/resources.ts): cancelled retry explanation and existing action labels.