#!/bin/bash
# Build script for Cockpit base image

set -e

COCKPIT_VERSION=${COCKPIT_VERSION:-337}
IMAGE_NAME="websoft9dev/cockpit-base"
IMAGE_TAG="${IMAGE_NAME}:${COCKPIT_VERSION}"

echo "==================================="
echo "Building Cockpit Base Image"
echo "Version: ${COCKPIT_VERSION}"
echo "Tag: ${IMAGE_TAG}"
echo "==================================="

# Build image
docker build -t "${IMAGE_TAG}" .

# Show image size
echo ""
echo "Image built successfully!"
docker images | grep cockpit-base

echo ""
echo "To test the image, run:"
echo "  docker run -d --name test-cockpit -p 9090:9090 ${IMAGE_TAG}"
echo ""
echo "To push to registry, run:"
echo "  docker push ${IMAGE_TAG}"
