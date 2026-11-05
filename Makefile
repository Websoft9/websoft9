# Websoft9 platform — single entry point for local development and CI.
#
# This file only orchestrates. Every real command stays in console/package.json,
# apphub/pyproject.toml or scripts/, so the Makefile and .github/workflows cannot drift into
# two different truths.
#
#   make            # list the available targets
#   make doctor     # verify the local toolchain before anything else
#   make setup      # install Console and AppHub dependencies

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.DEFAULT_GOAL := help
# The repository has no implicit C/LaTeX style rules to fall back on.
MAKEFLAGS += --no-builtin-rules

ROOT_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
CONSOLE_DIR := $(ROOT_DIR)/console
APPHUB_DIR := $(ROOT_DIR)/apphub
COMPOSE_DEV := docker compose -f $(ROOT_DIR)/docker/docker-compose.dev.yml

# All overridable from the command line, e.g.
#   make test PYTHON=apphub/.venv/bin/python
#   make image IMAGE_TAG=dev
PYTHON ?= python3
NPM ?= npm
IMAGE_REPO ?= websoft9dev/websoft9
IMAGE_TAG ?= dev
CHANNEL ?= dev
# Branch coverage floor for the AppHub suite. `pytest-cov` does not honour
# `[coverage:report] fail_under`, so the number is passed as `--cov-fail-under`; keep the floor a
# couple of points under the current value (70.8%) so an honest PR rarely trips it but a real drop does.
COVERAGE_MIN ?= 69
# Prefer the interpreter's ruff (installed by `make setup-apphub`), fall back to `uvx ruff` so the
# gate is usable before the venv exists. Both read apphub/pyproject.toml.
RUFF ?= $(shell $(PYTHON) -m ruff --version >/dev/null 2>&1 && printf '%s -m ruff' '$(PYTHON)' || printf 'uvx ruff')

.PHONY: help doctor \
	setup setup-console setup-apphub \
	dev-up dev-down dev-logs \
	lint lint-console lint-apphub i18n \
	format-apphub format-check-apphub \
	typecheck typecheck-console typecheck-apphub \
	test test-contracts test-apphub test-fast test-unit test-e2e \
	build build-console image \
	version-check ci \
	clean

##@ Getting started

help: ## List the available targets
	@awk 'BEGIN {FS = ":.*## "} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z0-9_.-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Check that the local toolchain can run every target below
	@printf 'Toolchain\n'
	@printf '  %-10s %s\n' node "$$(node --version 2>/dev/null || echo 'missing - need >= 20.19')"
	@printf '  %-10s %s\n' npm "$$($(NPM) --version 2>/dev/null || echo missing)"
	@printf '  %-10s %s\n' python "$$($(PYTHON) --version 2>&1 || echo missing)"
	@printf '  %-10s %s\n' docker "$$(docker --version 2>/dev/null || echo 'missing - only needed for the container workflows')"
	@printf '  %-10s %s\n' compose "$$(docker compose version --short 2>/dev/null || echo missing)"
	@node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>20||(a===20&&b>=19)?0:1)' 2>/dev/null \
		|| printf '  %-10s %s\n' warning 'node < 20.19 - the Console build requires >= 20.19'
	@$(PYTHON) -c 'import sys;sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)' 2>/dev/null \
		|| printf '  %-10s %s\n' warning 'python outside 3.10-3.13 - CI uses 3.11; pass PYTHON=python3.11 if the AppHub install fails'
	@$(PYTHON) -c 'import fastapi' 2>/dev/null \
		|| printf '  %-10s %s\n' warning 'AppHub runtime deps missing - run `make setup-apphub`'
	@$(PYTHON) -m ruff --version >/dev/null 2>&1 \
		|| printf '  %-10s %s\n' warning 'ruff missing - run `make setup-apphub` (needed by `make lint-apphub`)'
	@cd $(CONSOLE_DIR) && test -d node_modules \
		|| printf '  %-10s %s\n' warning 'console/node_modules missing - run `make setup-console`'

##@ Dependencies

setup: setup-console setup-apphub ## Install every dependency used by the targets below

setup-console: ## Install Console dependencies from the lockfile (npm ci)
	@printf '==> console: npm ci\n'
	@cd $(CONSOLE_DIR) && $(NPM) ci

setup-apphub: ## Create apphub/.venv and install dev + runtime dependencies
	@printf '==> apphub: create .venv and install dependencies\n'
	@test -d $(APPHUB_DIR)/.venv || $(PYTHON) -m venv $(APPHUB_DIR)/.venv
	@$(APPHUB_DIR)/.venv/bin/python -m pip install --upgrade pip
	@$(APPHUB_DIR)/.venv/bin/python -m pip install ruff mypy pytest pytest-cov pytest-asyncio pytest-timeout httpx
	@$(APPHUB_DIR)/.venv/bin/python -m pip install -r $(APPHUB_DIR)/requirements.txt
	@$(APPHUB_DIR)/.venv/bin/python -m pip install -r $(APPHUB_DIR)/requirements-dev.txt
	@printf '\nDone. Activate it (`source apphub/.venv/bin/activate`) or pass PYTHON=apphub/.venv/bin/python\nso the targets below use the same interpreter.\n'

##@ Development runtime

dev-up: ## Build and start the local container from docker/docker-compose.dev.yml
	@printf '==> docker: compose dev up (websoft9-dev, console on http://localhost:9000)\n'
	@$(COMPOSE_DEV) up -d --build

dev-down: ## Stop and remove the local development container
	@$(COMPOSE_DEV) down

dev-logs: ## Follow the local development container logs
	@$(COMPOSE_DEV) logs -f --tail=200

##@ Quality

lint: lint-console lint-apphub lint-shell ## Console ESLint + AppHub ruff + ShellCheck (same checks as CI)
lint-console: ## ESLint for the Console
	@printf '==> console: eslint\n'
	@cd $(CONSOLE_DIR) && $(NPM) run lint
i18n: ## Guarded hardcoded-string check (stricter than CI, currently has findings)
	@printf '==> console: i18n:check\n'
	@cd $(CONSOLE_DIR) && $(NPM) run i18n:check
lint-apphub: ## ruff lint for AppHub (the merge gate)
	@printf '==> apphub: ruff check\n'
	@cd $(APPHUB_DIR) && $(RUFF) check src/ tests/
lint-shell: ## ShellCheck for install/ and scripts/ (warnings and errors block)
	@printf '==> shell: shellcheck\n'
	@command -v shellcheck >/dev/null || { printf 'shellcheck missing: install it or run `make lint-shell` in CI\n' >&2; exit 1; }
	@find scripts/ install/ -type f \( -name '*.sh' -o -executable \) -print0 | \
		xargs -0 -I{} shellcheck -e SC1091,SC2034 --severity=warning "{}"
test-install: ## Installer self-tests (install/tests/*.sh)
	@printf '==> install: self-tests\n'
	@set -euo pipefail; for test_file in install/tests/*.sh; do printf '  %s\n' "$$test_file"; bash "$$test_file" >/dev/null; done
format-check-apphub: ## Verify ruff formatting without rewriting files
	@printf '==> apphub: ruff format --check\n'
	@cd $(APPHUB_DIR) && $(RUFF) format --check src/ tests/
format-apphub: ## Rewrite AppHub sources with ruff format
	@printf '==> apphub: ruff format\n'
	@cd $(APPHUB_DIR) && $(RUFF) format .

typecheck: typecheck-console typecheck-apphub ## TypeScript project build check + mypy
typecheck-console: ## tsc -b for the Console
	@printf '==> console: tsc -b\n'
	@cd $(CONSOLE_DIR) && $(NPM) run typecheck
typecheck-apphub: ## mypy src/ for AppHub (blocking, same as CI)
	@printf '==> apphub: mypy\n'
	@cd $(APPHUB_DIR) && $(PYTHON) -m mypy src/

##@ Tests

test: test-apphub test-unit test-install ## The suites that must stay green (AppHub + Console unit + installer scripts)
test-contracts: ## Fast AppHub contract subset (previously the only CI test step)
	@printf '==> apphub: CLI contracts\n'
	@cd $(APPHUB_DIR) && $(PYTHON) -m pytest -q -o addopts='' tests/test_cli_usability.py tests/test_apphub_cli_check_update.py tests/test_cli_contract_regressions.py
	@printf '==> apphub: install and compose contracts\n'
	@cd $(APPHUB_DIR) && $(PYTHON) -m pytest -q -o addopts='' tests/test_cli_git_regressions.py tests/test_app_compose_install.py tests/test_compose_app_classification.py tests/test_apphub_cli_apps.py
test-apphub: ## Full AppHub suite in one pytest process, with coverage reports and a coverage floor
	@printf '==> apphub: pytest tests/ (single process, min coverage $(COVERAGE_MIN)%%)\n'
	@cd $(APPHUB_DIR) && $(PYTHON) -m pytest -q --cov-fail-under=$(COVERAGE_MIN) tests/
test-fast: ## Fast AppHub feedback loop: single process, no coverage
	@printf '==> apphub: pytest (single process, no coverage)\n'
	@cd $(APPHUB_DIR) && $(PYTHON) -m pytest -q -o addopts='' tests/
test-unit: ## Console unit tests (Playwright unit project)
	@printf '==> console: test:unit\n'
	@cd $(CONSOLE_DIR) && $(NPM) run test:unit
test-e2e: ## Console end-to-end tests against a running console
	@printf '==> console: test:e2e\n'
	@cd $(CONSOLE_DIR) && $(NPM) run test:e2e

##@ Build

build: build-console ## Production build of the Console
build-console: ## tsc -b && vite build into console/dist
	@printf '==> console: build\n'
	@cd $(CONSOLE_DIR) && $(NPM) run build
image: ## Build the product image locally (single architecture; CI owns multi-arch)
	@printf '==> docker: build $(IMAGE_REPO):$(IMAGE_TAG) (channel $(CHANNEL))\n'
	@docker build -f $(ROOT_DIR)/docker/Dockerfile --build-arg WEBSOFT9_APPSTORE_CHANNEL=$(CHANNEL) \
		-t $(IMAGE_REPO):$(IMAGE_TAG) $(ROOT_DIR)

##@ Release metadata

version-check: ## Validate version metadata (mirrors the CI version-consistency job)
	@set -euo pipefail; \
	version=$$(jq -r '.version // empty' $(ROOT_DIR)/version.json); \
	if [[ -z "$$version" || ! "$$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$$ ]]; then \
		printf 'version.json version is invalid: "%s"\n' "$$version" >&2; exit 1; \
	fi; \
	grep -Eq "version='[0-9]+(\.[0-9]+){1,2}'" $(APPHUB_DIR)/setup.py \
		|| { printf 'apphub/setup.py must declare a numeric version\n' >&2; exit 1; }; \
	console_version=$$(jq -r '.version // empty' $(CONSOLE_DIR)/package.json); \
	[[ -n "$$console_version" ]] || { printf 'console/package.json version must not be empty\n' >&2; exit 1; }; \
	printf 'version metadata OK (%s)\n' "$$version"

##@ Aggregates

ci: lint format-check-apphub typecheck test version-check build ## What a pull request has to pass locally


##@ Housekeeping

clean: ## Remove build output and coverage reports
	@rm -rf $(CONSOLE_DIR)/dist $(APPHUB_DIR)/htmlcov $(APPHUB_DIR)/coverage.xml \
		$(ROOT_DIR)/htmlcov $(ROOT_DIR)/coverage.xml
	@printf 'Removed console/dist, htmlcov and coverage.xml\n'
