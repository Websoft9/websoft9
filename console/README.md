# Websoft9 Console Workspace

This workspace is the new frontend entry for the Websoft9 control plane.

## Stack Baseline

- Vite + React + TypeScript
- React Router v7
- Material UI 9
- TanStack Query 5
- Zustand 5

## Local Commands

Requires Node `^20.19.0 || >=22.12.0` because the current Vite 8 and React plugin baseline depends on that runtime floor.

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Current Scope

Story 1.2 extends the workspace with a bilingual shell baseline. The console now owns product shell routing, locale resources under `src/shared/i18n`, and a provider stack that carries theme, query, router, and i18n together.

The current shell exposes placeholder routes for app store, my apps, operations, integrations, and settings so later stories can attach feature pages without rebuilding the entry boundary.

