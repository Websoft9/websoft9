#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG=""
PRODUCT_VERSION=""
APPSTORE_CHANNEL="release"
# Which accelerator list the image ships with, and which regional list it asks the artifact
# server for. `cn` keeps the historical behaviour.
REGION="${WEBSOFT9_REGION:-cn}"

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
        --appstore-channel)
            APPSTORE_CHANNEL="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$IMAGE_TAG" || -z "$PRODUCT_VERSION" ]]; then
    echo "Usage: scripts/build_product_image.sh --tag <image:tag> --version <semver> [--appstore-channel <release|rc|dev>] [--region <cn|global>]" >&2
    exit 1
fi

case "$APPSTORE_CHANNEL" in
    release|rc|dev)
        ;;
    *)
        echo "Unsupported app store channel: $APPSTORE_CHANNEL" >&2
        exit 1
        ;;
esac

case "$REGION" in
    cn|global)
        ;;
    *)
        echo "Unsupported region: $REGION" >&2
        exit 1
        ;;
esac

docker build \
    -f "$ROOT_DIR/docker/Dockerfile" \
    -t "$IMAGE_TAG" \
    --build-arg WEBSOFT9_PRODUCT_VERSION="$PRODUCT_VERSION" \
    --build-arg WEBSOFT9_APPSTORE_CHANNEL="$APPSTORE_CHANNEL" \
    --build-arg WEBSOFT9_REGION="$REGION" \
    "$ROOT_DIR"