.PHONY: help dev dev-build dev-down dev-logs test lint format clean release \
	start stop restart logs clean-container rm kill-port \
	build build-base plugin plugins list-plugins

# Default values
PORT ?= 9091
SERVICE ?=
COMPOSE_FILE := docker/docker-compose-dev.yml
COMPOSE_CMD := docker compose -f $(COMPOSE_FILE)
BUILD_COMPOSE := build/docker-compose.yml

# Support positional port argument, e.g. `make start-cockpit 9091`
PRIMARY_GOAL := $(firstword $(MAKECMDGOALS))
PORT_ARG := $(word 2,$(MAKECMDGOALS))
ifneq ($(filter start kill-port,$(PRIMARY_GOAL)),)
PORT_EFFECTIVE := $(if $(PORT_ARG),$(PORT_ARG),$(PORT))
else
PORT_EFFECTIVE := $(PORT)
endif

# Default target
help:
	@echo "Websoft9 Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Development Environment: (TODO - Not Implemented Yet)"
	@echo "  make dev                        - Start development environment"
	@echo "  make dev-build                  - Rebuild development images"
	@echo "  make dev-down                   - Stop and cleanup development environment"
	@echo "  make dev-logs                   - View development logs (optional: SERVICE=apphub)"
	@echo ""
	@echo "Testing & Quality: (TODO - Not Implemented Yet)"
	@echo "  make test                       - Run all tests"
	@echo "  make lint                       - Run code linting checks"
	@echo "  make format                     - Format code"
	@echo ""
	@echo "Build & Release:"
	@echo "  make build                      - Build Websoft9 image"
	@echo "  make build-base                 - Build base image"
	@echo "  make release                    - Build production images locally"
	@echo ""
	@echo "Container Management:"
	@echo "  make start                      - Start Websoft9 container (default: 9091)"
	@echo "  make start 9092                 - Start on custom port"
	@echo "  make start PORT=9092            - Start on custom port"
	@echo "  make stop                       - Stop Websoft9 container"
	@echo "  make restart                    - Restart Websoft9 container"
	@echo "  make logs                       - View container logs"
	@echo "  make clean-container            - Stop and remove container (keeps volumes)"
	@echo "  make rm                         - Force remove container and all volumes"
	@echo ""
	@echo "Plugin Development:"
	@echo "  make plugin gitea               - Build specific plugin (gitea, nginx, portainer, etc.)"
	@echo "  make plugins                    - Build all plugins"
	@echo "  make plugins exclude=plugin1,plugin2  - Build all except specified plugins"
	@echo "  make list-plugins               - List all available plugins"
	@echo ""
	@echo "Utilities:"
	@echo "  make kill-port 9091             - Force kill process using the port"
	@echo "  make kill-port PORT=9091        - Force kill process using the port"
	@echo "  make clean                      - Clean cache and temporary files (requires confirmation)"
	@echo ""

# Development environment commands
dev:
	@echo "Starting development environment..."
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Error: $(COMPOSE_FILE) not found"; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) up -d
	@echo "✓ Development environment started"
	@echo "Services available:"
	@$(COMPOSE_CMD) ps

dev-build:
	@echo "Rebuilding development images..."
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Error: $(COMPOSE_FILE) not found"; \
		exit 1; \
	fi
	@$(COMPOSE_CMD) build --no-cache
	@echo "✓ Development images rebuilt"

dev-down:
	@echo "Stopping development environment..."
	@$(COMPOSE_CMD) down
	@echo "✓ Development environment stopped"

dev-logs:
ifdef SERVICE
	@echo "Viewing logs for service: $(SERVICE)"
	@$(COMPOSE_CMD) logs -f $(SERVICE)
else
	@echo "Viewing all development logs (Ctrl+C to exit)..."
	@$(COMPOSE_CMD) logs -f
endif

# Testing commands
test:
	@echo "Running tests..."
	@if [ -d "apphub" ] && [ -f "apphub/pytest.ini" ]; then \
		echo "Running apphub tests..."; \
		cd apphub && python3 -m pytest -v || echo "Tests failed or pytest not installed"; \
	else \
		echo "No tests configured yet"; \
	fi
	@echo "✓ Tests completed"

lint:
	@echo "Running linting checks..."
	@if command -v pylint >/dev/null 2>&1; then \
		echo "Running pylint..."; \
		find . -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/node_modules/*" | xargs pylint --errors-only || true; \
	else \
		echo "pylint not installed, skipping..."; \
	fi
	@if command -v eslint >/dev/null 2>&1; then \
		echo "Running eslint..."; \
		find plugins -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" | xargs eslint --quiet || true; \
	else \
		echo "eslint not installed, skipping..."; \
	fi
	@echo "✓ Linting completed"

format:
	@echo "Formatting code..."
	@if command -v black >/dev/null 2>&1; then \
		echo "Formatting Python code with black..."; \
		find . -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/node_modules/*" | xargs black || true; \
	else \
		echo "black not installed, skipping Python formatting..."; \
	fi
	@if command -v prettier >/dev/null 2>&1; then \
		echo "Formatting JavaScript/TypeScript with prettier..."; \
		prettier --write "plugins/**/*.{js,jsx,ts,tsx,json,css,md}" 2>/dev/null || true; \
	else \
		echo "prettier not installed, skipping JS/TS formatting..."; \
	fi
	@echo "✓ Code formatting completed"

clean:
	@echo "This will remove the following:"
	@echo "  - Python __pycache__ directories"
	@echo "  - .pytest_cache directories"
	@echo "  - node_modules directories"
	@echo "  - .cache directories"
	@echo ""
	@echo "Note: Plugin build directories (plugins/*/build) will be preserved"
	@echo ""
	@read -p "Are you sure you want to continue? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "Cleaning cache and temporary files..."; \
		find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name "*.pyc" -delete 2>/dev/null || true; \
		find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name "build" ! -path "*/plugins/*/build" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name ".cache" -exec rm -rf {} + 2>/dev/null || true; \
		echo "✓ Cache cleaned (plugins/*/build preserved)"; \
	else \
		echo "Cancelled."; \
	fi

release:
	@echo "Building production images locally..."
	@if [ -f "docker/docker-compose.yml" ]; then \
		docker compose -f docker/docker-compose.yml build; \
		echo "✓ Production images built"; \
	else \
		echo "Error: docker/docker-compose.yml not found"; \
		exit 1; \
	fi

# Docker build commands
build:
	@echo "Building Websoft9 image..."
	docker build -f build/Dockerfile -t websoft9:latest .
	@echo "✓ Image built: websoft9:latest"

build-base:
	@echo "Building Websoft9 base image..."
	docker build -f build/Dockerfile.base -t websoft9-base:latest .
	@echo "✓ Base image built: websoft9-base:latest"

# Container management (using docker compose)
start:
	@echo "Starting Websoft9 container on port $(PORT_EFFECTIVE)..."
	@if [ ! -f "$(BUILD_COMPOSE)" ]; then \
		echo "Error: $(BUILD_COMPOSE) not found"; \
		exit 1; \
	fi
	@cd build && HTTP_PORT=$(PORT_EFFECTIVE) docker compose up -d
	@echo "✓ Websoft9 started at http://localhost:$(PORT_EFFECTIVE)"
	@echo "  Portainer at http://localhost:$(PORT_EFFECTIVE)/w9deployment/"
	@echo "  Login: websoft9 / websoft9"

stop:
	@echo "Stopping Websoft9 container..."
	@cd build && docker compose stop || echo "Container not running"

restart:
	@echo "Restarting Websoft9 container..."
	@cd build && docker compose restart || echo "Container not found"

logs:
	@cd build && docker compose logs -f

clean-container:
	@echo "Removing Websoft9 container..."
	@if docker ps -a --format '{{.Names}}' | grep -q '^websoft9$$'; then \
		echo "Found container, removing..."; \
		docker stop websoft9 2>/dev/null || true; \
		docker rm websoft9 2>/dev/null || true; \
	fi
	@cd build && docker compose down 2>/dev/null || true
	@echo "✓ Websoft9 container removed"

rm:
	@echo "Force removing Websoft9 container and volumes..."
	@if docker ps -a --format '{{.Names}}' | grep -q '^websoft9$$'; then \
		echo "Found container, force removing..."; \
		docker rm -f websoft9 2>/dev/null || true; \
	fi
	@cd build && docker compose down -v 2>/dev/null || true
	@echo "✓ Container and volumes removed"

# Force kill process using a port
kill-port:
ifeq ($(strip $(PORT_EFFECTIVE)),)
	$(error PORT is required. Usage: make kill-port PORT=9091)
endif
	@echo "Killing process on port $(PORT_EFFECTIVE)..."
	@if command -v fuser >/dev/null 2>&1; then \
		fuser -k $(PORT_EFFECTIVE)/tcp 2>/dev/null || echo "No process found on port $(PORT_EFFECTIVE)"; \
	elif command -v lsof >/dev/null 2>&1; then \
		PID=$$(lsof -t -i:$(PORT_EFFECTIVE) 2>/dev/null); \
		if [ -n "$$PID" ]; then \
			echo "Found PID: $$PID"; \
			kill -9 $$PID && echo "Process killed"; \
		else \
			echo "No process found on port $(PORT_EFFECTIVE)"; \
		fi; \
	elif command -v ss >/dev/null 2>&1; then \
		PID=$$(ss -ltnp 2>/dev/null | awk '/:$(PORT_EFFECTIVE) /{print $$NF}' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1); \
		if [ -n "$$PID" ]; then \
			echo "Found PID: $$PID"; \
			kill -9 $$PID && echo "Process killed"; \
		else \
			echo "No process found on port $(PORT_EFFECTIVE)"; \
		fi; \
	else \
		echo "No fuser/lsof/ss available to find the process."; \
		exit 1; \
	fi

# Plugin management
PLUGIN_DIR := plugins
AVAILABLE_PLUGINS := $(shell find $(PLUGIN_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort)

list-plugins:
	@echo "Available plugins in $(PLUGIN_DIR)/:"
	@echo "======================================"
	@for plugin in $(AVAILABLE_PLUGINS); do \
		if [ "$$plugin" = "cockpit-files" ]; then \
			echo "  $$plugin [download script]"; \
		elif [ -f "$(PLUGIN_DIR)/$$plugin/package.json" ]; then \
			echo "  $$plugin [buildable]"; \
		else \
			echo "  $$plugin"; \
		fi; \
	done
	@echo ""
	@echo "Usage:"
	@echo "  make plugin <plugin-name>  - Build specific plugin"
	@echo "  make plugins               - Build all plugins"
	@echo "Example: make plugin gitea"

plugin:
	@if [ -z "$(filter-out plugin,$(MAKECMDGOALS))" ]; then \
		echo "Error: Plugin name required"; \
		echo "Usage: make plugin <plugin-name>"; \
		echo ""; \
		echo "Available plugins:"; \
		make list-plugins | grep "^  " || true; \
		exit 1; \
	fi
	@PLUGIN=$(word 2,$(MAKECMDGOALS)); \
	if [ ! -d "$(PLUGIN_DIR)/$$PLUGIN" ]; then \
		echo "Error: Plugin '$$PLUGIN' not found in $(PLUGIN_DIR)/"; \
		echo ""; \
		echo "Available plugins:"; \
		make list-plugins | grep "^  " || true; \
		exit 1; \
	fi; \
	if [ "$$PLUGIN" = "cockpit-files" ]; then \
		echo "========================================"; \
		echo "Building plugin: $$PLUGIN (using download.sh)"; \
		echo "========================================"; \
		if [ -x "$(PLUGIN_DIR)/$$PLUGIN/download.sh" ]; then \
			cd $(PLUGIN_DIR)/$$PLUGIN && ./download.sh && \
			echo ""; \
			echo "✓ Plugin '$$PLUGIN' downloaded successfully!"; \
			echo "Build output: $(PLUGIN_DIR)/$$PLUGIN/build/"; \
			echo "========================================"; \
		else \
			echo "Error: download.sh not found or not executable"; \
			exit 1; \
		fi; \
	elif [ ! -f "$(PLUGIN_DIR)/$$PLUGIN/package.json" ]; then \
		echo "Error: No package.json found in $(PLUGIN_DIR)/$$PLUGIN/"; \
		exit 1; \
	else \
		echo "========================================"; \
		echo "Building plugin: $$PLUGIN"; \
		echo "========================================"; \
		cd $(PLUGIN_DIR)/$$PLUGIN && \
		echo "Installing/updating dependencies..."; \
		npm install && \
		echo "Building plugin..."; \
		npm run build && \
		echo ""; \
		echo "✓ Plugin '$$PLUGIN' built successfully!"; \
		echo "Build output: $(PLUGIN_DIR)/$$PLUGIN/build/"; \
		echo "========================================"; \
	fi;

plugins:
	@echo "========================================"
	@echo "Building all plugins..."
	@if [ -n "$(exclude)" ]; then \
		echo "Excluding: $(exclude)"; \
	fi
	@echo "========================================"
	@SUCCESS=0; FAILED=0; SKIPPED=0; EXCLUDED=0; \
	EXCLUDE_LIST="$(subst $(,), ,$(exclude))"; \
	for plugin in $(AVAILABLE_PLUGINS); do \
		SHOULD_EXCLUDE=0; \
		for excl in $$EXCLUDE_LIST; do \
			if [ "$$plugin" = "$$excl" ]; then \
				SHOULD_EXCLUDE=1; \
				break; \
			fi; \
		done; \
		if [ $$SHOULD_EXCLUDE -eq 1 ]; then \
			echo "⊘ Excluding $$plugin"; \
			EXCLUDED=$$((EXCLUDED + 1)); \
			continue; \
		fi; \
		if [ "$$plugin" = "cockpit-files" ]; then \
			echo ""; \
			echo "Building: $$plugin (using download.sh)"; \
			echo "----------------------------------------"; \
			if [ -x "$(PLUGIN_DIR)/$$plugin/download.sh" ]; then \
				if cd $(PLUGIN_DIR)/$$plugin && ./download.sh; then \
					echo "✓ $$plugin downloaded successfully"; \
					SUCCESS=$$((SUCCESS + 1)); \
				else \
					echo "✗ $$plugin download failed"; \
					FAILED=$$((FAILED + 1)); \
				fi; \
				cd - > /dev/null; \
			else \
				echo "✗ download.sh not found or not executable"; \
				FAILED=$$((FAILED + 1)); \
			fi; \
		elif [ -f "$(PLUGIN_DIR)/$$plugin/package.json" ]; then \
			echo ""; \
			echo "Building: $$plugin"; \
			echo "----------------------------------------"; \
			if cd $(PLUGIN_DIR)/$$plugin && npm install --silent && npm run build --silent; then \
				echo "✓ $$plugin built successfully"; \
				SUCCESS=$$((SUCCESS + 1)); \
			else \
				echo "✗ $$plugin build failed"; \
				FAILED=$$((FAILED + 1)); \
			fi; \
			cd - > /dev/null; \
		else \
			echo "⊘ Skipping $$plugin (no package.json)"; \
			SKIPPED=$$((SKIPPED + 1)); \
		fi; \
	done; \
	echo ""; \
	echo "========================================"; \
	echo "Build Summary:"; \
	echo "  Success:  $$SUCCESS"; \
	echo "  Failed:   $$FAILED"; \
	echo "  Skipped:  $$SKIPPED"; \
	echo "  Excluded: $$EXCLUDED"; \
	echo "========================================"

# Swallow positional args like `9091`
%:
	@:
