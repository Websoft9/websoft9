#!/bin/bash
# Build script for Websoft9 Console (integrated Cockpit + Portainer + Gitea + Apphub)

set -e

# 切换到项目根目录
cd "$(dirname "$0")/../.."

CONSOLE_VERSION=${CONSOLE_VERSION:-dev}
IMAGE_NAME="websoft9/appmanage"
IMAGE_TAG="${IMAGE_NAME}:${CONSOLE_VERSION}"

echo "==================================="
echo "Building Websoft9 Console"
echo "Version: ${CONSOLE_VERSION}"
echo "Tag: ${IMAGE_TAG}"
echo "==================================="

# Build image from project root
docker build -f docker/cockpit/Dockerfile -t "${IMAGE_TAG}" -t websoft9-console:latest .

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
