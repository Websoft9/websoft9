# CI/CD Pipeline Guide

This document describes the current CI/CD implementation in Websoft9 and defines the immediate upgrade direction for the DevOps modernization program.

## Workflow Topology

Websoft9 uses multiple GitHub Actions workflows instead of a single pipeline file.

- `.github/workflows/ci-pr.yml`: Pull request quality gates and selective checks.
- `.github/workflows/ci-main.yml`: Main and dev branch continuous integration, image build/push, smoke test.
- `.github/workflows/release.yml`: Version-driven release packaging and channel distribution.
- `.github/workflows/security-scan.yml`: Scheduled container vulnerability scanning.
- `.github/workflows/_shared/docker-build.yml`: Reusable Docker build and security scan workflow.
- `.github/workflows/_shared/smoke-test.yml`: Reusable smoke test workflow.

## Current Pipeline Behavior

### 1. Pull Request Checks (`ci-pr.yml`)

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

### 2. Main/Dev CI (`ci-main.yml`)

Trigger:

```yaml
on:
  push:
    branches: [main, dev]
```

Execution model:

1. Reuse `ci-pr.yml` checks through `workflow_call`.
2. Compute channel/version metadata from `version.json` and branch.
3. Build once, tag many via shared Docker build workflow.
4. Run smoke test against SHA-pinned image.
5. Update DockerHub description on `main`.

### 3. Release (`release.yml`)

Triggers:

- `workflow_dispatch`
- Push where `version.json` changed on `main`, `dev`, `hotfix*`

Execution model:

1. Determine release channel (`release`, `rc`, `dev`).
2. Update `CHANGELOG.md` using `changelog_latest.md`.
3. Build release archive and upload artifacts to Cloudflare R2.
4. Create GitHub Release for release/hotfix channels.
5. Deploy GitHub Pages on release channel from `main`.

### 4. Security Scan (`security-scan.yml`)

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
