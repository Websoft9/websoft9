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

# Deploy to cockpit directory
COCKPIT_DIR="/usr/share/cockpit/store"
sudo mkdir -p $COCKPIT_DIR
sudo cp -r build/* $COCKPIT_DIR/

echo "Build completed successfully!"
echo "Plugin deployed to $COCKPIT_DIR"
