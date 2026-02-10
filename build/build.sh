#!/bin/bash
# Build script for Websoft9 Console (integrated Cockpit + Portainer + Gitea + Apphub)

set -e

# 切换到项目根目录
cd "$(dirname "$0")/../.."

CONSOLE_VERSION=${CONSOLE_VERSION:-dev}
IMAGE_NAME="websoft9"
IMAGE_TAG="${IMAGE_NAME}:${CONSOLE_VERSION}"

echo "==================================="
echo "Building Websoft9 Console"
echo "Version: ${CONSOLE_VERSION}"
echo "Tag: ${IMAGE_TAG}"
echo "==================================="

# Build image from project root
docker build -f build/Dockerfile -t "${IMAGE_TAG}" -t websoft9:latest .

# Show image size
echo ""
echo "Image built successfully!"
docker images | grep websoft9

echo ""
echo "To test the image, run:"
echo "  docker run -d --name websoft9 -p 9091:80 ${IMAGE_TAG}"
echo ""
echo "To push to registry, run:"
echo "  docker push ${IMAGE_TAG}"
