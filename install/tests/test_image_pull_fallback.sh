#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

run_case() {
  local case_name="$1"
  shift
  (
    source "$ROOT_DIR/install/lib/common.sh"
    CALLS=()
    direct_result=1
    ecr_result=1
    mirror_result=1
    tag_result=0
    TEST_DIR="$(mktemp -d)"
    trap 'rm -rf "$TEST_DIR"' EXIT

    log_info() { :; }
    log_warn() { :; }
    log_error() { :; }
    modern_compose() { CALLS+=("compose"); return "$direct_result"; }
    load_mirror_entries() { printf '%s\n' "mirror.example"; }
    docker() {
      case "$1" in
        pull)
          CALLS+=("pull:$2")
          case "$2" in
            "${ECR_PUBLIC_IMAGE_REPO}:"*) return "$ecr_result" ;;
            mirror.example/*) return "$mirror_result" ;;
          esac
          ;;
        tag)
          CALLS+=("tag:$2:$3")
          return "$tag_result"
          ;;
        rmi) CALLS+=("rmi:$2") ;;
        image) return 1 ;;
      esac
    }

    "$@"
    echo "ok: $case_name"
  )
}

test_docker_hub_success() {
  direct_result=0
  pull_image_with_mirrors "$TEST_DIR"
  [[ "${CALLS[*]}" == "compose" ]]
}

test_ecr_fallback_retags() {
  ecr_result=0
  pull_image_with_mirrors "$TEST_DIR"
  [[ "${CALLS[*]}" == *"pull:${ECR_PUBLIC_IMAGE_REPO}:latest"* ]]
  [[ "${CALLS[*]}" == *"tag:${ECR_PUBLIC_IMAGE_REPO}:latest:${DEFAULT_IMAGE_REPO}:latest"* ]]
  [[ "${CALLS[*]}" != *"mirror.example"* ]]
}

test_ecr_failure_uses_mirror() {
  mirror_result=0
  pull_image_with_mirrors "$TEST_DIR"
  [[ "${CALLS[*]}" == *"pull:${ECR_PUBLIC_IMAGE_REPO}:latest"* ]]
  [[ "${CALLS[*]}" == *"pull:mirror.example/${DEFAULT_IMAGE_REPO}:latest"* ]]
}

test_ecr_tag_failure_uses_mirror() {
  ecr_result=0
  tag_result=1
  mirror_result=0
  pull_image_with_mirrors "$TEST_DIR"
  [[ "${CALLS[*]}" == *"tag:${ECR_PUBLIC_IMAGE_REPO}:latest:${DEFAULT_IMAGE_REPO}:latest"* ]]
  [[ "${CALLS[*]}" == *"pull:mirror.example/${DEFAULT_IMAGE_REPO}:latest"* ]]
}

test_patch_tag_skips_ecr() {
  mirror_result=0
  printf 'IMAGE_REPO=%s\nIMAGE_TAG=2.4.2\n' "$DEFAULT_IMAGE_REPO" > "$TEST_DIR/.env"
  pull_image_with_mirrors "$TEST_DIR"
  [[ "${CALLS[*]}" != *"${ECR_PUBLIC_IMAGE_REPO}"* ]]
  [[ "${CALLS[*]}" == *"pull:mirror.example/${DEFAULT_IMAGE_REPO}:2.4.2"* ]]
}

test_utility_image_skips_ecr() {
  mirror_result=0
  pull_image_with_mirrors "$TEST_DIR" alpine:3.20
  [[ "${CALLS[*]}" != *"${ECR_PUBLIC_IMAGE_REPO}"* ]]
}

run_case "Docker Hub success" test_docker_hub_success
run_case "ECR fallback retags" test_ecr_fallback_retags
run_case "ECR failure uses mirror" test_ecr_failure_uses_mirror
run_case "ECR tag failure uses mirror" test_ecr_tag_failure_uses_mirror
run_case "Patch tag skips ECR" test_patch_tag_skips_ecr
run_case "Utility image skips ECR" test_utility_image_skips_ecr