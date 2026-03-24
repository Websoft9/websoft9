#!/bin/bash
#
# Download and extract cockpit-files from official releases
# Supports multiple mirror sources for China network acceleration
#

set -e

# Configuration
VERSION="${1:-35}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
TMP_DIR="/tmp/cockpit-files-download-$$"
FILE_NAME="cockpit-files-${VERSION}.tar.xz"

# GitHub release mirrors (primary + fallbacks)
MIRRORS=(
    "https://github.com"
    "https://ghproxy.com/https://github.com"
    "https://gh.api.99988866.xyz/https://github.com"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function
cleanup() {
    if [ -d "$TMP_DIR" ]; then
        log_info "Cleaning up temporary files..."
        rm -rf "$TMP_DIR"
    fi
}

trap cleanup EXIT ERR

# Create directories
mkdir -p "$BUILD_DIR"
mkdir -p "$TMP_DIR"

log_info "Downloading cockpit-files version ${VERSION}..."
log_info "Target: ${BUILD_DIR}"

# Try downloading from mirrors
DOWNLOAD_SUCCESS=false
for mirror in "${MIRRORS[@]}"; do
    DOWNLOAD_URL="${mirror}/cockpit-project/cockpit-files/releases/download/${VERSION}/${FILE_NAME}"
    
    log_info "Attempting download from: ${mirror}"
    
    # Try 3 times per mirror
    for attempt in {1..3}; do
        if [ $attempt -gt 1 ]; then
            log_warn "Retry attempt ${attempt}/3..."
        fi
        
        if curl -fL \
            --progress-bar \
            --connect-timeout 10 \
            --max-time 120 \
            --retry 2 \
            -o "${TMP_DIR}/${FILE_NAME}" \
            "$DOWNLOAD_URL" 2>&1; then
            
            log_info "✓ Successfully downloaded from ${mirror}"
            DOWNLOAD_SUCCESS=true
            break 2
        else
            log_warn "✗ Failed to download from ${mirror} (attempt ${attempt})"
        fi
    done
done

if [ "$DOWNLOAD_SUCCESS" = false ]; then
    log_error "Failed to download from all mirrors"
    exit 1
fi

# Verify download
if [ ! -f "${TMP_DIR}/${FILE_NAME}" ]; then
    log_error "Downloaded file not found"
    exit 1
fi

FILE_SIZE=$(stat -f%z "${TMP_DIR}/${FILE_NAME}" 2>/dev/null || stat -c%s "${TMP_DIR}/${FILE_NAME}" 2>/dev/null)
log_info "Downloaded file size: $(numfmt --to=iec-i --suffix=B $FILE_SIZE 2>/dev/null || echo "${FILE_SIZE} bytes")"

# Extract archive
log_info "Extracting archive..."
tar -xJf "${TMP_DIR}/${FILE_NAME}" -C "$TMP_DIR"

# Find the extracted directory (usually cockpit-files)
EXTRACTED_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "cockpit-files" ! -path "$TMP_DIR" | head -n 1)

if [ -z "$EXTRACTED_DIR" ]; then
    log_error "Extracted directory 'cockpit-files' not found"
    log_info "Available contents in ${TMP_DIR}:"
    ls -la "$TMP_DIR"
    exit 1
fi

log_info "Extracted to: ${EXTRACTED_DIR}"

# Check if dist directory exists
if [ ! -d "${EXTRACTED_DIR}/dist" ]; then
    log_error "dist directory not found in extracted files"
    log_info "Available contents:"
    ls -la "$EXTRACTED_DIR"
    exit 1
fi

# Clean build directory
log_info "Cleaning build directory..."
rm -rf "${BUILD_DIR:?}"/*

# Copy dist contents to build directory
log_info "Copying dist files to build directory..."
cp -r "${EXTRACTED_DIR}/dist/"* "$BUILD_DIR/"

# Verify copy
if [ "$(ls -A "$BUILD_DIR")" ]; then
    log_info "✓ Successfully copied files to ${BUILD_DIR}"
    log_info "Files in build directory:"
    ls -lh "$BUILD_DIR" | head -n 10
    
    FILE_COUNT=$(find "$BUILD_DIR" -type f | wc -l)
    log_info "Total files copied: ${FILE_COUNT}"
else
    log_error "Build directory is empty after copy"
    exit 1
fi

log_info "✓ Download and extraction completed successfully!"
log_info "cockpit-files version ${VERSION} is ready in: ${BUILD_DIR}"
