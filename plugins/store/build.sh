#!/bin/bash
# Build script for epic5-store plugin

PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# Copy build files to the appropriate location
echo "Building epic5-store plugin..."

# Ensure build directory exists
if [ ! -d "build" ]; then
    echo "Error: build directory not found. Run 'npm run build' first."
    exit 1
fi

# Deploy to cockpit container
COCKPIT_DIR="/usr/share/cockpit/store"
CONTAINER_NAME="websoft9-cockpit"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: ${CONTAINER_NAME} container is not running."
    exit 1
fi

# Copy to container
echo "Deploying to ${CONTAINER_NAME} container..."
docker cp build/. ${CONTAINER_NAME}:${COCKPIT_DIR}/

echo "Build completed successfully!"
echo "Plugin deployed to ${CONTAINER_NAME}:${COCKPIT_DIR}"
