#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

load_helpers() {
  source <(sed -n '/^_build_repo_list()/,/^# Repo-based installation helper/p' \
    "$ROOT_DIR/install/install_docker.sh")
}

test_repo_list_excludes_log_messages() {
  local repos
  log_info() { printf 'INFO: %s\n' "$*" >&2; }
  _url_reachable() { return 1; }

  repos="$(_build_repo_list ubuntu)"
  [[ "$repos" == $'https://mirrors.aliyun.com/docker-ce/linux\nhttps://mirror.azure.cn/docker-ce/linux\nhttps://download.docker.com/linux' ]]
}

test_clear_failed_docker_repos_preserves_unrelated_sources() {
  local test_dir
  test_dir="$(mktemp -d)"
  trap 'rm -rf "$test_dir"' RETURN
  W9_APT_SOURCES_LIST_DIR="$test_dir"

  printf 'deb https://mirror.azure.cn/docker-ce/linux/ubuntu resolute stable\n' > "$test_dir/docker.list"
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\n' > "$test_dir/docker.sources"
  printf 'deb https://archive.ubuntu.com/ubuntu resolute main\n' > "$test_dir/ubuntu.list"

  _clear_failed_docker_apt_repos

  [[ ! -e "$test_dir/docker.list" ]]
  [[ ! -e "$test_dir/docker.sources" ]]
  [[ -e "$test_dir/ubuntu.list" ]]
}

load_helpers
test_repo_list_excludes_log_messages
test_clear_failed_docker_repos_preserves_unrelated_sources
printf 'ok: Docker installer helpers\n'