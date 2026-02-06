.PHONY: help start-cockpit stop-cockpit restart-cockpit logs-cockpit clean-cockpit kill-port

# Default port for Cockpit
PORT ?= 9090

# Support positional port argument, e.g. `make start-cockpit 9091`
PRIMARY_GOAL := $(firstword $(MAKECMDGOALS))
PORT_ARG := $(word 2,$(MAKECMDGOALS))
ifneq ($(filter start-cockpit kill-port,$(PRIMARY_GOAL)),)
PORT_EFFECTIVE := $(if $(PORT_ARG),$(PORT_ARG),$(PORT))
else
PORT_EFFECTIVE := $(PORT)
endif

# Default target
help:
	@echo "Websoft9 Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Cockpit Management:"
	@echo "  make start-cockpit 9091         - Start Cockpit container (default: 9090)"
	@echo "  make start-cockpit PORT=9091    - Start Cockpit container (default: 9090)"
	@echo "  make stop-cockpit               - Stop Cockpit container"
	@echo "  make restart-cockpit            - Restart Cockpit container"
	@echo "  make logs-cockpit               - View Cockpit container logs"
	@echo "  make clean-cockpit              - Stop and remove Cockpit container"
	@echo ""
	@echo "Utilities:"
	@echo "  make kill-port 9090             - Force kill process using the port"
	@echo "  make kill-port PORT=9090        - Force kill process using the port"
	@echo ""

# Cockpit container management
start-cockpit:
	@echo "Starting Cockpit container on port $(PORT_EFFECTIVE)..."
	@docker run -d --name websoft9-cockpit \
		--restart unless-stopped \
		-v /var/run/docker.sock:/var/run/docker.sock \
		-v /data/compose:/data/compose \
		-v cockpit_portainer_data:/portainer_data \
		-p $(PORT_EFFECTIVE):80 \
		websoft9/cockpit:latest || \
	(echo "Container already exists, starting it..." && docker start websoft9-cockpit)
	@echo "Cockpit started at http://localhost:$(PORT_EFFECTIVE)"
	@echo "Portainer at http://localhost:$(PORT_EFFECTIVE)/w9deployment/"
	@echo "Login: websoft9 / websoft9"

stop-cockpit:
	@echo "Stopping Cockpit container..."
	@docker stop websoft9-cockpit || echo "Container not running"

restart-cockpit:
	@echo "Restarting Cockpit container..."
	@docker restart websoft9-cockpit || echo "Container not found"

logs-cockpit:
	@docker logs -f websoft9-cockpit

clean-cockpit:
	@echo "Removing Cockpit container..."
	@docker stop websoft9-cockpit 2>/dev/null || true
	@docker rm websoft9-cockpit 2>/dev/null || true
	@echo "Cockpit container removed"

# Force kill process using a port
kill-port:
ifeq ($(strip $(PORT_EFFECTIVE)),)
	$(error PORT is required. Usage: make kill-port PORT=9090)
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

# Swallow positional args like `9091`
%:
	@:
