# Story 1.1: Bootstrap the Unified Console Workspace

## Status

done

## Story

As a platform operator,
I want a standalone Websoft9 console workspace,
so that the new control plane can evolve outside the legacy Cockpit plugin structure.

## Acceptance Criteria

1. A standalone `console/` workspace exists in the repository and is not implemented inside legacy plugin folders.
2. The workspace is based on Vite + React + TypeScript.
3. Developers can install dependencies and start the base dev server successfully.
4. React Router, Material UI, TanStack Query, and base project conventions are already connected.

## Dependencies

- None. This is the first delivery story of Epic 1.

## Developer Context

- The repository currently has no `console/` directory.
- Architecture explicitly selects `npm create vite@latest console -- --template react-ts` as the starter.
- Required stack baseline: React 19.2, React Router v7, Material UI 9.0.0, TanStack Query 5.99.2, Zustand 5.0.12.
- The new console must live beside existing brownfield workspaces, not inside `pluings/`.
- `console/src/app` will later own shell, providers, and route composition; this story should leave a clean foundation for that layout.

## Implementation Guardrails

- Do not reuse Cockpit plugin build tooling as the base of the new console.
- Do not move existing plugin code into `console/` as a shortcut.
- Keep the workspace feature-first compatible with the target architecture, even if only placeholder modules exist now.
- Add only the frontend baseline needed for shell and routing stories that follow immediately.

## Suggested File Targets

- `console/package.json`
- `console/tsconfig.json`
- `console/vite.config.ts`
- `console/index.html`
- `console/src/main.tsx`
- `console/src/app/`
- `console/src/shared/`
- `console/public/`
- `console/.env.example`

## Implementation Tasks

 - [x] Initialize the new Vite React TypeScript workspace at `console/`.
 - [x] Add and wire the required baseline dependencies for routing, UI foundation, query management, and lightweight UI state.
 - [x] Create the initial source structure so the next story can add providers, shell, and i18n without rework.
 - [x] Ensure the base application boots cleanly in development.
 - [x] Document workspace-specific run commands in the workspace README.

## Testing Requirements

- Verify dependency installation succeeds.
- Verify the base dev server starts successfully.
- Verify the application renders a minimal root without relying on Cockpit runtime globals.
- If tests are added this early, keep them limited to a smoke-level frontend baseline.

## Definition of Done

- `console/` exists and is runnable.
- The selected frontend stack is reflected in workspace dependencies.
- The repository still preserves existing brownfield plugin workspaces untouched.
- The workspace is ready for Story 1.2 to add shell routing and bilingual entry.

## Source Notes

- Primary sources: Epic 1 in `epics.md`, architecture frontend stack selection, target directory structure, and development workflow notes.

## Dev Agent Record

### Debug Log

- Initialized `console/` with the architecture-mandated Vite React TypeScript template.
- Replaced the default demo app with a minimal Websoft9 bootstrap surface wired through `src/app` and `src/shared` boundaries.
- Added React Router v7, Material UI 9, TanStack Query 5.99.2, and Zustand 5.0.12 to satisfy the frontend baseline.
- Added a minimal environment example for later AppHub integration and documented the required Node runtime floor for Vite 8.
- Fixed two build blockers during validation: TypeScript 6 `baseUrl` deprecation gating and MUI 9 `Stack` prop typing incompatibility.
- Followed up review findings by moving router creation into the app composition point, adding a route boundary for future route-aware providers, removing deprecated alias configuration, and replacing leftover Vite-branded entry metadata.

### Completion Notes

- Story 1.1 acceptance criteria are satisfied: `console/` now exists as a standalone workspace, required baseline libraries are connected, `npm install` succeeds, `npm run build` succeeds, and `npm run dev -- --host 0.0.0.0` starts correctly.
- The workspace is now ready for Story 1.2 to add bilingual app entry and shell routing on top of the existing `app/providers/router/shared` structure, with a dedicated route boundary available for route-aware root capabilities.
- Final re-review returned no blocking findings. Remaining risk is limited to the absence of an automated frontend smoke test for the root render path.

### File List

- console/.env.example
- console/README.md
- console/eslint.config.js
- console/.gitignore
- console/index.html
- console/package.json
- console/package-lock.json
- console/public/favicon.svg
- console/src/app/App.tsx
- console/src/app/pages/bootstrap-page.tsx
- console/src/app/providers/app-providers.tsx
- console/src/app/router/app-route-boundary.tsx
- console/src/app/router/index.tsx
- console/src/index.css
- console/src/main.tsx
- console/src/shared/lib/query-client.ts
- console/src/shared/theme/theme.ts
- console/tsconfig.app.json
- console/tsconfig.json
- console/tsconfig.node.json
- console/vite.config.ts

### Change Log

- 2026-04-22: initialized the standalone console workspace and wired the Story 1.1 frontend baseline.
- 2026-04-22: resolved review follow-ups for router composition, Node runtime constraints, and console entry metadata.
- 2026-04-22: completed final validation and re-review with no findings; story moved to done.
