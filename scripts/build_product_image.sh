#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG=""
PRODUCT_VERSION=""
PRODUCT_EDITION_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --version)
            PRODUCT_VERSION="$2"
            shift 2
            ;;
        --edition-key)
            PRODUCT_EDITION_KEY="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$IMAGE_TAG" || -z "$PRODUCT_VERSION" || -z "$PRODUCT_EDITION_KEY" ]]; then
    echo "Usage: scripts/build_product_image.sh --tag <image:tag> --version <semver> --edition-key <free|starter|standard|enterprise>" >&2
    exit 1
fi

docker build \
    -f "$ROOT_DIR/docker/product/Dockerfile" \
    -t "$IMAGE_TAG" \
    --build-arg WEBSOFT9_PRODUCT_VERSION="$PRODUCT_VERSION" \
    --build-arg WEBSOFT9_PRODUCT_EDITION_KEY="$PRODUCT_EDITION_KEY" \
    "$ROOT_DIR"