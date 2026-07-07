#!/bin/bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: prepare_platform_artifact.sh --channel <release|rc|dev> --bundle-docker-dir <path> --artifact-dir <path>
EOF
}

CHANNEL=""
BUNDLE_DOCKER_DIR=""
ARTIFACT_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --channel)
      CHANNEL="$2"
      shift 2
      ;;
    --bundle-docker-dir)
      BUNDLE_DOCKER_DIR="$2"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$CHANNEL" in
  release|rc|dev) ;;
  *)
    echo "Unsupported channel: ${CHANNEL:-<empty>}" >&2
    usage >&2
    exit 2
    ;;
esac

[ -n "$BUNDLE_DOCKER_DIR" ] || { echo "Missing --bundle-docker-dir" >&2; exit 2; }
[ -n "$ARTIFACT_DIR" ] || { echo "Missing --artifact-dir" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_COMPOSE="$ROOT_DIR/docker/docker-compose.yml"
TMP_COMPOSE="$(mktemp)"
trap 'rm -f "$TMP_COMPOSE"' EXIT

if [ "$CHANNEL" = "dev" ]; then
  sed \
    -e '1s/^# Production docker-compose.yml — single-container runtime$/# Dev artifact docker-compose.yml — single-container runtime/' \
    -e '2s|^# Usage: docker compose -f docker-compose.yml up -d$|# Usage: docker compose -f docker-compose.yml up -d|' \
    -e 's/^name: websoft9$/name: websoft9-dev/' \
    -e 's|image: ${IMAGE_REPO:-websoft9dev/websoft9}:${IMAGE_TAG:-latest}|image: ${IMAGE_REPO:-websoft9dev/websoft9}:${IMAGE_TAG:-dev}|' \
    -e 's|container_name: ${CONTAINER_NAME:-websoft9}|container_name: ${CONTAINER_NAME:-websoft9-dev}|' \
    "$SOURCE_COMPOSE" > "$TMP_COMPOSE"
else
  cp "$SOURCE_COMPOSE" "$TMP_COMPOSE"
fi

mkdir -p "$BUNDLE_DOCKER_DIR" "$ARTIFACT_DIR"
cp "$TMP_COMPOSE" "$BUNDLE_DOCKER_DIR/docker-compose.yml"
rm -f "$BUNDLE_DOCKER_DIR/docker-compose.dev.yml"
cp "$TMP_COMPOSE" "$ARTIFACT_DIR/docker-compose.yml"