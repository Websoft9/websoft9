# CI/CD Pipeline Guide

This document describes the current CI/CD implementation in Websoft9 and defines the immediate upgrade direction for the DevOps modernization program.

## Workflow Topology

Websoft9 uses multiple GitHub Actions workflows instead of a single pipeline file.

- `.github/workflows/ci-pr.yml` (`Pull Request Validation`): Pull request quality gates and selective checks.
- `.github/workflows/ci-main.yml` (`Dev Candidate Build`): Dev branch continuous integration, image build/push, smoke test.
- `.github/workflows/release.yml` (`Main Release Publish`): Version-driven release packaging and channel distribution.
- `.github/workflows/security-scan.yml` (`Registry Security Scan`): Scheduled container vulnerability scanning.
- `.github/workflows/docker-build.yml`: Reusable Docker build and security scan workflow.
- `.github/workflows/smoke-test.yml`: Reusable smoke test workflow.

Appstore publishing and Contentful synchronization are no longer owned by this repository. They are handled in the `docker-library` project workflows.

## Current Pipeline Behavior

### 1. Pull Request Validation (`ci-pr.yml`)

Trigger:

```yaml
on:
  pull_request:
    branches: [main, dev]
```

Execution model:

1. Secret scan (`gitleaks`) runs first.
2. Path-based change detection decides which jobs should run.
3. Relevant quality jobs run in parallel:
   - Python (`apphub`): Ruff, format check, mypy, pytest + coverage.
   - Console (`console`): eslint, typecheck, build, optional tests.
   - Docker: hadolint.
   - Shell scripts: shellcheck.
4. A summary gate evaluates all job results and fails PR when required jobs fail.

### 2. Dev Candidate Build (`ci-main.yml`)

Trigger:

```yaml
on:
  push:
    branches: [dev]
```

Execution model:

1. Feature branches merge into `dev` through PR checks first.
2. A push on `dev` computes candidate metadata from `version.json`.
3. Build once, tag many via shared Docker build workflow.
4. Run smoke test against the SHA-pinned image.
5. Publish dev candidate image tags.
6. Upload the dev install surface to `artifact/websoft9/dev`, including `manifest.json`, and publish the dev zip bundle through a GitHub prerelease.

Current dev image tags:

1. `sha-<commit>`: Immutable build identity for smoke tests, traceability, rollback, and security evidence.
2. `dev`: Moving alias for the latest dev candidate.
3. `<version>-dev`: Human-readable moving alias for the current semantic dev candidate line.

Practical rule:

1. Use `sha-<commit>` when exact reproduction matters.
2. Use `dev` for fast-moving shared dev environments.
3. Treat `<version>-dev` as a convenience alias, not as an immutable release artifact.

The default merge flow is short-lived branch -> `dev` -> `main`.

### 3. Main Release Publish (`release.yml`)

Triggers:

- `workflow_dispatch`
- Push where `version.json` changed on `main`

Execution model:

1. Determine release metadata from `version.json`.
2. Extract the current version's release notes directly from the matching Keep a Changelog style section in `CHANGELOG.md`.
3. Upload the install surface and `manifest.json` to Cloudflare R2.
4. Publish the release zip bundle and release notes through GitHub Release.
5. Deploy GitHub Pages from `main`.

Current release image tags:

1. `sha-<commit>`: Immutable build identity.
2. `<version>` such as `3.0.0`: Immutable semantic release tag.
3. `<major>.<minor>` such as `3.0`: Moving alias for the latest patch in that minor line.
4. `<major>` such as `3`: Moving alias for the latest release in that major line.
5. `latest`: Moving alias for the current stable release.

Practical rule:

1. Use `sha-<commit>` or the full `<version>` tag for rollback, audit, and reproducible deployment.
2. Use `<major>.<minor>` or `<major>` only when consumers explicitly want a moving compatibility line.
3. Keep `latest` reserved for the current stable release and never use it for dev channel publication.

Appstore catalog/library publishing is no longer owned by this repository. It is published from the `docker-library` project workflow on the `dev` branch.

## Version Metadata Boundary

`version.json` should still be kept, but it should now be treated as release metadata for program publishing instead of a general-purpose runtime configuration file.

Current active usage:

1. `ci-pr.yml`, `ci-main.yml`, `release.yml`, and `docker-build.yml` read release metadata from `version.json`.
2. Release artifacts still package `version.json` together with the published program bundle.
3. The runtime release identity used inside the image is copied to `/websoft9/version.json`, while mutable runtime edition state is stored in the existing AppHub SQLite database.

Practical rule:

1. Keep `version`.
2. Keep only `edition_key` for release/build logic.
3. Do not keep plugin version maps in this file.
4. Keep OS support matrices in install-facing documentation instead of release metadata.
5. Keep runtime-facing edition display fields such as edition names and max-app limits out of this file.
6. Move runtime-facing product fields to code-owned catalogs plus SQLite-backed runtime state instead of reintroducing a JSON runtime truth source.

Current recommendation:

1. Short term: keep `version.json`, but shrink it toward release-only metadata.
2. Legacy upgrade compatibility should be handled by the upgrade entry or dedicated legacy data, not by expanding `version.json`.
3. Long term: keep `version.json` as the single source of release identity, while runtime display and edition state are derived from code catalogs and persisted runtime state.

## Artifact Manifest

Program release channels now publish a product-level `manifest.json` alongside the install surface.

Current role:

1. Describe the install surface filenames and checksum file.
2. Describe the image repository, default moving tag, and current version tag.
3. Record build metadata such as channel, version, edition key, git SHA, and generation time.
4. Provide a machine-readable handoff for installers and external automation.

Installer behavior:

1. `install.sh` fetches `manifest.json` when available.
2. The installer uses manifest metadata to resolve the compose artifact path and preferred image tags.
3. If the manifest is unavailable or invalid, the installer falls back to built-in defaults for backward compatibility.

### 4. Registry Security Scan (`security-scan.yml`)

- Scheduled vulnerability scanning for published images.
- Uploads SARIF reports to GitHub Security.

## Local Validation Commands

Use these commands before opening a PR.

### AppHub

```bash
cd apphub
pip install -r requirements.txt
pip install -r requirements-dev.txt
ruff check src/
ruff format --check src/
mypy src/
pytest tests/ -v --cov=src --cov-report=term
```

### Console

```bash
cd console
npm ci
npm run lint
npm run typecheck
npm run build
npm run test --if-present
```

### Docker and Scripts

```bash
cd /workspace/websoft9
hadolint docker/Dockerfile
find scripts install -type f -name "*.sh" -print0 | xargs -0 -I{} shellcheck -e SC1091,SC2034 "{}"
```

## Known Gaps (Baseline)

These gaps are accepted in current baseline and are tracked by the DevOps upgrade plan:

- Console tests are optional and not enforced as a required gate.
- CLI package quality checks are not fully integrated.
- Coverage quality gate uses a low threshold in PR checks.
- Branch protection and required status checks are not fully codified in repository settings.
- Staging verification and rollback drills are not yet mandatory.

## Immediate Upgrade Priorities

1. Enable strict branch protection + required checks for `main` and `dev`.
2. Enforce deterministic test gates for `console` and `cli`.
3. Raise quality thresholds incrementally and make failures blocking.
4. Add supply-chain checks (SAST, dependency license, signed artifacts).
5. Add staged deployment verification and automated rollback validation.

See `docs/standards/devops/roadmap_cn.md` for execution phases, main-branch baseline, and acceptance criteria.
