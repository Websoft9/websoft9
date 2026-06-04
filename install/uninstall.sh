#!/bin/bash
set -euo pipefail

# ==============================================================================
# Websoft9 Uninstall Script — Single-Container Runtime
# ==============================================================================
#
# Usage:
#   curl -fsSL https://websoft9.github.io/websoft9/install/uninstall.sh | sudo bash
#   sudo bash uninstall.sh              # remove container + data
#   sudo bash uninstall.sh --keep-data  # remove container, keep volumes
#   sudo bash uninstall.sh --purge      # remove container + data + images
#
# ==============================================================================

KEEP_DATA=false
PURGE=false
INSTALL_PATH="/opt/websoft9"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep-data) KEEP_DATA=true; shift ;;
        --purge)     PURGE=true;     shift ;;
        --path)      INSTALL_PATH="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "  --keep-data   Remove container only, keep volumes"
            echo "  --purge       Remove container + volumes + images"
            echo "  --path        Installation path (default: /opt/websoft9)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ $(id -u) -ne 0 ]]; then
    echo "❌ This script must be run as root or with sudo."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Websoft9 Uninstaller"
echo "=========================================="

# ── Stop and remove container ──
if [[ -f "$INSTALL_PATH/docker-compose.yml" ]]; then
    echo ""
    echo "🛑 Stopping Websoft9..."
    cd "$INSTALL_PATH"

    if $KEEP_DATA; then
        docker compose down
        echo "✅ Container removed (data volumes preserved)"
    else
        docker compose down -v
        echo "✅ Container and data volumes removed"
    fi
else
    echo "⚠️  No docker-compose.yml found at $INSTALL_PATH"
    echo "   Removing container by name..."
    docker rm -f websoft9 2>/dev/null || echo "   No running container found"
fi

# ── Remove install directory ──
if [[ -d "$INSTALL_PATH" ]]; then
    echo ""
    echo "🗑️  Removing $INSTALL_PATH..."
    rm -rf "$INSTALL_PATH"
fi

# ── Purge images ──
if $PURGE; then
    echo ""
    echo "🗑️  Removing Websoft9 Docker images..."
    docker images websoft9dev/websoft9-product -q | xargs -r docker rmi -f 2>/dev/null || true
fi

# ── Remove /etc/issue banner ──
if grep -q "Websoft9" /etc/issue 2>/dev/null; then
    echo ""
    echo "🗑️  Removing login banner..."
    rm -f /etc/issue
fi

echo ""
echo "=========================================="
echo "  ✅ Websoft9 uninstall complete"
echo "=========================================="
if $KEEP_DATA; then
    echo "  ℹ️  Data volumes were preserved"
fi
echo "=========================================="
