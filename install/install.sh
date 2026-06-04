#!/bin/bash
set -Eeuo pipefail

# ==============================================================================
# Websoft9 Installer — Single-Container Runtime
# ==============================================================================
# Usage:
#   curl -fsSL https://websoft9.github.io/websoft9/install/install.sh | sudo bash
#   sudo bash install.sh --mode upgrade --version 3.0.0
# ==============================================================================

readonly LOG_DIR="/var/log/websoft9"
readonly LOG_FILE="${LOG_DIR}/install.log"
readonly IMAGE_REPO="websoft9dev/websoft9-product"
# ── Artifact download URLs (tried in order) ──
readonly COMPOSE_URLS=(
    "https://websoft9.github.io/websoft9/docker/docker-compose.yml"
    "https://artifact.websoft9.com/release/websoft9/docker-compose.yml"
)

VERSION="latest"
CHANNEL="release"
MODE="auto"          # auto | install | upgrade
CHECK_ONLY=false
CONSOLE_PORT="9000"
INSTALL_PATH="/opt/websoft9"
MIRRORS=""
PROXY=""
START_TIME=$(date +%s)
STEP_NUM=0

# ── Logging ──
init_logging() {
    mkdir -p "$LOG_DIR"
    if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt 1048576 ]]; then
        mv "$LOG_FILE" "${LOG_FILE}.1"
    fi
    echo "" >> "$LOG_FILE"
    echo "========== $(date '+%Y-%m-%d %H:%M:%S') | install.sh v3.0 ==========" >> "$LOG_FILE"
}
log_info()  { echo -e "  ✅  $*" | tee -a "$LOG_FILE"; }
log_warn()  { echo -e "  ⚠️  $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "  ❌  $*" | tee -a "$LOG_FILE" >&2; }
log_step()  { STEP_NUM=$((STEP_NUM + 1)); echo -e "\n── Step ${STEP_NUM}: $*" | tee -a "$LOG_FILE"; }

# ── Error trap ──
on_error() {
    local exit_code=$?
    log_error "Failed at line ${1} (exit code: ${exit_code})"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Troubleshooting:"
    echo "  1. Full log:    cat ${LOG_FILE}"
    echo "  2. Docker:      docker info"
    echo "  3. Network:     curl -I https://registry-1.docker.io"
    echo "  4. Support:     https://www.websoft9.com/support"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit "$exit_code"
}
trap 'on_error ${LINENO}' ERR

# ── Help ──
show_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --mode          install | upgrade | auto (default: auto)
  --check         Run preflight checks only, do not install
  --version       Image version tag (default: latest)
  --channel       Release channel: release | rc | dev (default: release)
  --console_port  Console web port (default: 9000)
  --path          Install directory (default: /opt/websoft9)
  --mirrors       Comma-separated Docker registry mirrors
  --proxy         HTTP/HTTPS proxy

Examples:
  curl -fsSL https://websoft9.github.io/websoft9/install/install.sh | sudo bash
  sudo bash install.sh --check
  sudo bash install.sh --mode upgrade --version 3.0.0
  sudo bash install.sh --channel dev
EOF
    exit 0
}

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)         MODE="$2";         shift 2 ;;
        --check)        CHECK_ONLY=true;    shift ;;
        --version)      VERSION="$2";      shift 2 ;;
        --channel)      CHANNEL="$2";      shift 2 ;;
        --console_port) CONSOLE_PORT="$2";  shift 2 ;;
        --path)         INSTALL_PATH="$2";  shift 2 ;;
        --mirrors)      MIRRORS="$2";       shift 2 ;;
        --proxy)        PROXY="$2";         shift 2 ;;
        -h|--help)      show_help ;;
        *) echo "Unknown option: $1. Use --help."; exit 1 ;;
    esac
done

# ── Preflight ──
if [[ $(id -u) -ne 0 ]]; then
    echo "❌ Must run as root. Try: sudo bash $0"
    exit 1
fi
[[ -n "$PROXY" ]] && export http_proxy="$PROXY" https_proxy="$PROXY"

init_logging

# ── Determine actual mode ──
EXISTING_CONTAINER=false
docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^websoft9$' && EXISTING_CONTAINER=true

if [[ "$MODE" == "auto" ]]; then
    if $EXISTING_CONTAINER; then
        MODE="upgrade"
    else
        MODE="install"
    fi
fi

if [[ "$MODE" != "install" ]] && [[ "$MODE" != "upgrade" ]]; then
    echo "❌ Invalid mode: $MODE. Use: install | upgrade | auto"
    exit 1
fi

# ── Banner ──
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       Websoft9 v3.0 — ${MODE^}          ║"
echo "╚══════════════════════════════════════════╝"
echo "  Version:      ${VERSION}"
echo "  Channel:      ${CHANNEL}"
echo "  Console Port: ${CONSOLE_PORT}"
echo "  Install Path: ${INSTALL_PATH}"
echo "  Mirrors:      ${MIRRORS:-none}"
echo "  Proxy:        ${PROXY:-none}"
echo "  Log:          ${LOG_FILE}"
echo ""

# ── Warn on latest tag ──
if [[ "$VERSION" == "latest" ]]; then
    log_warn "Using 'latest' tag — image content may change between runs"
    log_warn "For production, pin a specific version: --version 3.0.0"
fi

# ── Step 1: System checks ──
log_step "Checking system"

if [[ ! -f /etc/os-release ]]; then
    log_error "Unsupported OS. Requires Ubuntu, Debian, CentOS, RHEL, Rocky, Fedora"
    exit 1
fi
. /etc/os-release
log_info "OS: $PRETTY_NAME"

AVAILABLE_KB=$(df -P / | awk 'NR==2 {print $4}')
if [[ "$AVAILABLE_KB" -lt 2097152 ]]; then
    log_error "Insufficient disk space. Need ≥2GB. Available: $((AVAILABLE_KB / 1024 / 1024))GB"
    exit 1
fi
log_info "Disk: $((AVAILABLE_KB / 1024 / 1024))GB free"

if ss -tuln 2>/dev/null | grep -q ":${CONSOLE_PORT} " && ! docker inspect websoft9 &>/dev/null; then
    log_warn "Port ${CONSOLE_PORT} is in use. Use --console_port to change."
else
    log_info "Port ${CONSOLE_PORT}: available"
fi

# ── Check-only mode: stop here ──
if $CHECK_ONLY; then
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║       ✅  Preflight checks passed            ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║  OS:      ${PRETTY_NAME}"
    echo "║  Disk:    $((AVAILABLE_KB / 1024 / 1024))GB free"
    echo "║  Port:    ${CONSOLE_PORT}"
    echo "║  Docker:  $(command -v docker &>/dev/null && echo installed || echo missing)"
    echo "║  Compose: $(command -v docker &>/dev/null && docker compose version --short 2>/dev/null || echo missing)"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "All checks passed. Run without --check to install:"
    echo "  sudo bash install.sh"
    exit 0
fi

# ── Step 2: Prerequisites ──
log_step "Installing prerequisites"

install_pkg() {
    local pkg="$1"
    command -v "$pkg" &>/dev/null && { log_info "$pkg: OK"; return 0; }
    log_info "Installing $pkg..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq && apt-get install -y -qq "$pkg" >> "$LOG_FILE" 2>&1
    elif command -v dnf &>/dev/null; then
        dnf install -y -q "$pkg" >> "$LOG_FILE" 2>&1
    elif command -v yum &>/dev/null; then
        yum install -y -q "$pkg" >> "$LOG_FILE" 2>&1
    else
        log_error "No package manager found"
        exit 1
    fi
}
install_pkg curl
install_pkg jq

# ── Step 3: Docker ──
log_step "Setting up Docker"

if command -v docker &>/dev/null; then
    log_info "Docker: $(docker --version | awk '{print $3}' | sed 's/,//')"
else
    log_info "Installing Docker..."
    curl -fsSL https://get.docker.com | bash >> "$LOG_FILE" 2>&1
    systemctl enable docker
    systemctl start docker
    log_info "Docker installed"
fi

if ! docker compose version &>/dev/null; then
    log_error "Docker Compose plugin required"
    log_error "Install: apt-get install docker-compose-plugin (or dnf equivalent)"
    exit 1
fi
log_info "Compose: $(docker compose version --short)"

if [[ -n "$MIRRORS" ]]; then
    log_info "Configuring registry mirrors..."
    JSON="["; FIRST=true
    IFS=',' read -ra MA <<< "$MIRRORS"
    for m in "${MA[@]}"; do $FIRST || JSON+=","; JSON+="\"$m\""; FIRST=false; done
    JSON+="]"
    mkdir -p /etc/docker
    echo "{\"registry-mirrors\": $JSON}" > /etc/docker/daemon.json
    systemctl restart docker
    log_info "Mirrors configured"
fi

# ── Step 4: Download docker-compose.yml (artifact, not generated) ──
log_step "Downloading deployment artifacts"

mkdir -p "$INSTALL_PATH"
cd "$INSTALL_PATH"

# ── Try multiple sources in order ──
download_compose() {
    for url in "${COMPOSE_URLS[@]}"; do
        log_info "Trying: ${url}"
        if curl -fsSL --retry 2 --retry-delay 2 --connect-timeout 10 -o docker-compose.yml "${url}" 2>/dev/null; then
            log_info "Downloaded from: ${url}"
            return 0
        fi
        log_warn "Failed: ${url}"
    done
    return 1
}

if ! download_compose; then
    log_error "Failed to download docker-compose.yml from all sources"
    log_error "Check network or try again later"
    exit 1
fi
log_info "docker-compose.yml downloaded"

# Determine image tag
case "$CHANNEL" in
    release) IMAGE_TAG="${VERSION}" ;;
    rc)      IMAGE_TAG="${VERSION}" ;;
    dev)     IMAGE_TAG="${VERSION}-dev" ;;
    *) log_error "Unknown channel: $CHANNEL"; exit 1 ;;
esac
if [[ "$VERSION" == "latest" ]]; then
    case "$CHANNEL" in release) IMAGE_TAG="latest" ;; rc) IMAGE_TAG="rc" ;; dev) IMAGE_TAG="dev" ;; esac
fi
log_info "Image: ${IMAGE_REPO}:${IMAGE_TAG}"

# ── Step 5: .env ──
log_step "Writing environment configuration"

# Upgrade: preserve existing .env if present
if [[ "$MODE" == "upgrade" ]] && [[ -f .env ]]; then
    log_info "Preserving existing .env (upgrade mode)"
    cp .env .env.bak
    # Update version in existing .env
    sed -i "s|^WEBSOFT9_PRODUCT_VERSION=.*|WEBSOFT9_PRODUCT_VERSION=${VERSION}|" .env
else
    cat > .env <<ENVEOF
IMAGE_REPO=${IMAGE_REPO}
IMAGE_TAG=${IMAGE_TAG}
CONSOLE_PORT=${CONSOLE_PORT}
NETWORK_NAME=websoft9
WEBSOFT9_PRODUCT_VERSION=${VERSION}
ENVEOF
    log_info ".env created"
fi

# ── Step 6: Pull image ──
log_step "Pulling container image"

docker compose pull >> "$LOG_FILE" 2>&1 || {
    log_error "Failed to pull image. Check network or try --mirrors"
    exit 1
}
log_info "Image pulled"

# ── Step 7: Start/restart ──
if [[ "$MODE" == "upgrade" ]]; then
    log_step "Upgrading container (data volumes preserved)"

    # Graceful stop
    log_info "Stopping existing container..."
    docker compose down >> "$LOG_FILE" 2>&1 || true

    log_info "Starting with new image..."
    docker compose up -d >> "$LOG_FILE" 2>&1 || {
        log_error "Upgrade failed. Rolling back..."
        if [[ -f .env.bak ]]; then
            cp .env.bak .env
            docker compose up -d >> "$LOG_FILE" 2>&1 || log_warn "Rollback also failed"
        fi
        exit 1
    }
    # Clean up backup
    rm -f .env.bak
else
    log_step "Starting container"
    docker compose up -d >> "$LOG_FILE" 2>&1 || {
        log_error "Failed to start container. Check: docker logs websoft9"
        exit 1
    }
fi
log_info "Container running"

# ── Step 8: Health check ──
log_step "Health check"

MAX_WAIT=120; WAITED=0
while [[ $WAITED -lt $MAX_WAIT ]]; do
    if docker exec websoft9 /websoft9/script/platform-healthcheck.sh --readiness &>/dev/null; then
        log_info "Healthy after ${WAITED}s"
        break
    fi
    sleep 3; WAITED=$((WAITED + 3))
done
[[ $WAITED -ge $MAX_WAIT ]] && log_warn "Health check timed out. Container may still be starting."

# ── Step 9: Login banner ──
log_step "Generating login banner"

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || HOST_IP="<your-server-ip>"
cat > /etc/issue <<ISSUEEOF
==========================================
  Welcome to Websoft9
  Console: http://${HOST_IP}:${CONSOLE_PORT}
==========================================
  OS: \s \v  (\r \m)
  Hostname: \n
  Time: \d \t
==========================================
\l
ISSUEEOF
chmod 644 /etc/issue

# ── Done ──
ELAPSED=$(($(date +%s) - START_TIME))
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║          ✅  ${MODE^} Complete              ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Console:   http://${HOST_IP}:${CONSOLE_PORT}"
echo "║  Directory: ${INSTALL_PATH}"
echo "║  Log:       ${LOG_FILE}"
echo "║  Time:      ${ELAPSED}s"
echo "╠══════════════════════════════════════════════╣"
echo "║  Manage:                                      ║"
echo "║    cd ${INSTALL_PATH} && docker compose ps"
echo "║    docker logs websoft9 -f"
echo "║    docker compose down      # stop"
echo "║    docker compose up -d     # start"
echo "╚══════════════════════════════════════════════╝"
echo ""
