#!/bin/bash
# install.sh - Websoft9 install / upgrade entrypoint
# Usage: sudo bash install.sh [options]

set -o pipefail

# Resolve the script directory and bundled libs.
W9_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
W9_ROOT_DIR="$(dirname "$W9_SCRIPT")"
W9_LIB_DIR="${W9_ROOT_DIR}/lib"
export W9_LIB_DIR

# Load libraries.
# The block below is replaced during bundle generation (install/build-bundle.sh)
# so the release artifact becomes a single self-contained script.
# >>> WEBSOFT9_LIB_SOURCING >>>
# shellcheck source=lib/common.sh
. "${W9_LIB_DIR}/common.sh"
. "${W9_LIB_DIR}/detect.sh"
. "${W9_LIB_DIR}/legacy-discovery.sh"
. "${W9_LIB_DIR}/backup.sh"
. "${W9_LIB_DIR}/validate.sh"
. "${W9_LIB_DIR}/install-fresh.sh"
. "${W9_LIB_DIR}/upgrade-modern.sh"
. "${W9_LIB_DIR}/upgrade-legacy.sh"
. "${W9_LIB_DIR}/uninstall.sh"
# <<< WEBSOFT9_LIB_SOURCING <<<

usage() {
  cat <<EOF
Websoft9 Install / Upgrade Tool

Usage:
  sudo bash install.sh [options]

  Auto-detect: fresh install if nothing is running, upgrade if already installed.

Options:
  --channel <release|rc|dev>  Release channel (default: release)
  --console-port <port>       Console port (default: ${DEFAULT_CONSOLE_PORT})
  --dry-run                   Dry run: pre-flight checks only, no changes
  --yes                       Skip all confirmation prompts (CI / automation)
  -h, --help                  Show this help

Advanced options (usually not needed):
  --version <tag>             Image tag (default: latest)
  --path <dir>                Install directory (default: ${DEFAULT_INSTALL_PATH})
  --image-repo <repo>         Image repository (default: ${DEFAULT_IMAGE_REPO})
  --network <name>            Docker network name (default: ${DEFAULT_NETWORK_NAME})
  --force                     Skip non-destructive pre-flight checks

Uninstall: sudo bash uninstall.sh [--purge]
EOF
}

# Default options.
OPT_CHANNEL="release"
OPT_VERSION="$DEFAULT_IMAGE_TAG"
OPT_PATH="$DEFAULT_INSTALL_PATH"
OPT_CONSOLE_PORT="$DEFAULT_CONSOLE_PORT"
OPT_FORCE="0"
OPT_YES="0"
OPT_IMAGE_REPO="$DEFAULT_IMAGE_REPO"
OPT_NETWORK="$DEFAULT_NETWORK_NAME"
_OPT_VERSION_EXPLICIT=""

# Hidden subcommands for diagnostics / operations.
_SUBCMD=""
case "${1:-}" in
  detect|backup) _SUBCMD="$1"; shift ;;
esac

# Parse CLI options.
while [ $# -gt 0 ]; do
  case "$1" in
    --channel)      OPT_CHANNEL="$2"; shift 2 ;;
    --version)      OPT_VERSION="$2"; _OPT_VERSION_EXPLICIT="1"; shift 2 ;;
    --path)         OPT_PATH="$2"; shift 2 ;;
    --console-port) OPT_CONSOLE_PORT="$2"; shift 2 ;;
    --force)        OPT_FORCE="1"; shift ;;
    --dry-run)      W9_DRY_RUN="1"; export W9_DRY_RUN; shift ;;
    --yes)          OPT_YES="1"; shift ;;
    --image-repo)   OPT_IMAGE_REPO="$2"; shift 2 ;;
    --network)      OPT_NETWORK="$2"; shift 2 ;;
    -h|--help)      usage; exit "$EXIT_OK" ;;
    *) die "$EXIT_USAGE" "Unknown option: $1 (use -h for help)" ;;
  esac
done

[ -z "$OPT_VERSION" ] && OPT_VERSION="$DEFAULT_IMAGE_TAG"

# For non-release channels, default the image tag to the channel name
# (for example --channel dev => IMAGE_TAG=dev) unless the user explicitly
# passed --version.
if [ -z "$_OPT_VERSION_EXPLICIT" ] && [ "$OPT_CHANNEL" != "release" ]; then
    OPT_VERSION="$OPT_CHANNEL"
fi

export W9_CHANNEL="$OPT_CHANNEL"

# Interactive confirmation helper.
# Returns 0 for confirm, 1 for reject. --yes auto-confirms.
_confirm() {
  local prompt="$1" default="${2:-n}"
  [ "$OPT_YES" = "1" ] && return 0
  local hint; [ "$default" = "y" ] && hint="[Y/n]" || hint="[y/N]"
  printf "%s %s " "$prompt" "$hint"
  read -r _ans </dev/tty
  case "${_ans:-$default}" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

# Hidden subcommands.
if [ -n "$_SUBCMD" ]; then
  require_root
  case "$_SUBCMD" in
    detect)
      detect_print_signals
      env_kind="$(detect_environment)"
      echo "$env_kind"
      ;;
    backup)
      env_kind="$(detect_environment)"
      case "$env_kind" in
        modern)
          bdir="$(backup_new_dir modern)"
          backup_modern_pre_upgrade "$OPT_PATH" "$bdir"
          log_info "Backup point: $bdir"
          ;;
        legacy)
          bdir="$(backup_new_dir legacy)"
          backup_legacy_pre_migration "$bdir"
          log_info "Backup point: $bdir"
          ;;
        *)
          die "$EXIT_ENV_GUARD" "No installed Websoft9 found, nothing to back up" ;;
      esac
      ;;
  esac
  exit "$EXIT_OK"
fi

require_root

# Main flow: detect the environment and execute the right path.
env_kind="$(detect_environment)"

case "$env_kind" in
  empty)
    log_step "No Websoft9 installation detected. Starting a fresh install"
    run_install "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK"
    ;;

  modern|legacy)
    _cur_ver="$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' \
      "$MODERN_CONTAINER_NAME" 2>/dev/null || true)"
    if [ -n "$_cur_ver" ]; then
      log_info "Websoft9 is already installed (current version: ${_cur_ver})"
    else
      log_info "Websoft9 is already installed"
    fi
    if ! _confirm "Upgrade to the latest version?" "y"; then
      log_info "Cancelled."
      exit "$EXIT_OK"
    fi
    if [ "$env_kind" = "modern" ]; then
      run_upgrade_modern "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK"
    else
      run_upgrade_legacy "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK"
    fi
    ;;

  mixed)
    log_warn "Residual components detected; the environment is inconsistent. Clean it up manually before re-running if possible"
    if [ "$OPT_FORCE" != "1" ]; then
      if ! _confirm "Force continue anyway? This is risky" "n"; then
        log_info "Cancelled."
        exit "$EXIT_OK"
      fi
    fi
    run_upgrade_modern "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK"
    ;;

  *)
    die "$EXIT_ENV_GUARD" "Unknown environment state (${env_kind}), please contact support" ;;
esac

exit "$EXIT_OK"
