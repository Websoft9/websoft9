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
  sudo bash install.sh doctor [options]
  sudo bash install.sh detect [options]
  sudo bash install.sh backup [options]

  Auto-detect: fresh install if nothing is running, upgrade if already installed.

Options:
  --console-port <port>       Console port (default: ${DEFAULT_CONSOLE_PORT})
  --dry-run                   Dry run: pre-flight checks only, no changes
  --execute_mode <mode>       Legacy compatibility option; accepted values: install, upgrade
  --yes                       Skip all confirmation prompts (CI / automation)
  -h, --help                  Show this help

Advanced options (usually not needed):
  --version <tag>             Image tag (default: latest)
  --path <dir>                Install directory (default: ${DEFAULT_INSTALL_PATH})
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
OPT_EXECUTE_MODE=""
_OPT_VERSION_EXPLICIT=""
_OPT_CONSOLE_PORT_EXPLICIT=""

# Hidden subcommands for diagnostics / operations.
_SUBCMD=""
case "${1:-}" in
  detect|backup|doctor|inspect) _SUBCMD="$1"; shift ;;
esac

# Parse CLI options.
while [ $# -gt 0 ]; do
  case "$1" in
    --version)      OPT_VERSION="$2"; _OPT_VERSION_EXPLICIT="1"; shift 2 ;;
    --path)         OPT_PATH="$2"; shift 2 ;;
    --console-port) OPT_CONSOLE_PORT="$2"; _OPT_CONSOLE_PORT_EXPLICIT="1"; shift 2 ;;
    --execute_mode) OPT_EXECUTE_MODE="$2"; shift 2 ;;
    --execute_mode=*) OPT_EXECUTE_MODE="${1#*=}"; shift ;;
    --force)        OPT_FORCE="1"; shift ;;
    --dry-run)      W9_DRY_RUN="1"; export W9_DRY_RUN; shift ;;
    --yes)          OPT_YES="1"; shift ;;
    -h|--help)      usage; exit "$EXIT_OK" ;;
    *) die "$EXIT_USAGE" "Unknown option: $1 (use -h for help)" ;;
  esac
done

case "${OPT_EXECUTE_MODE:-}" in
  ""|install|upgrade) ;;
  *) die "$EXIT_USAGE" "Unsupported --execute_mode: ${OPT_EXECUTE_MODE} (expected install or upgrade)" ;;
esac

[ -z "$OPT_VERSION" ] && OPT_VERSION="$DEFAULT_IMAGE_TAG"

# For non-release artifacts, default the image tag to the baked channel name
# (for example dev install.sh => IMAGE_TAG=dev) unless the user explicitly
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

_read_json_version() {
  local file_path="$1"
  [ -f "$file_path" ] || return 1
  sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$file_path" | head -n1
}

_resolve_latest_version() {
  local install_path="$1"
  local channel="${W9_CHANNEL:-release}"
  local candidates=(
    "${install_path}/version.json"
    "${W9_ROOT_DIR}/../version.json"
    "${W9_ROOT_DIR}/../../version.json"
    "${W9_LIB_DIR}/../../version.json"
  )
  local candidate version remote_version

  remote_version="$(_w9_fetch "${W9_ARTIFACT_BASE:-$DEFAULT_ARTIFACT_BASE}/${channel}/version.json" 2>/dev/null | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
  if [ -n "$remote_version" ]; then
    echo "$remote_version"
    return 0
  fi

  for candidate in "${candidates[@]}"; do
    version="$(_read_json_version "$candidate" 2>/dev/null || true)"
    if [ -n "$version" ]; then
      echo "$version"
      return 0
    fi
  done

  return 1
}

_resolve_current_modern_version() {
  local install_path="$1"
  local compose_file="${install_path}/docker-compose.yml"
  local container_name current_version current_image

  container_name="$(_resolve_container_name "$compose_file")"
  current_version="$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$container_name" 2>/dev/null || true)"
  if [ -n "$current_version" ]; then
    echo "$current_version"
    return 0
  fi

  current_image="$(docker inspect --format '{{.Config.Image}}' "$container_name" 2>/dev/null || true)"
  if [ -n "$current_image" ] && [[ "$current_image" == *:* ]]; then
    echo "${current_image##*:}"
    return 0
  fi

  return 1
}

_confirm_modern_upgrade() {
  local install_path="$1"
  local target_version="$2"
  local current_version

  current_version="$(_resolve_current_modern_version "$install_path" 2>/dev/null || true)"

  log_info "Detected an existing modern Websoft9 runtime"
  log_info "  Current version: ${current_version:-unknown}"
  log_info "  Latest version: ${target_version:-unknown}"
  log_info "  Impact: containers will be recreated and the console will be briefly unavailable during the upgrade"

  _confirm "Proceed with the in-place upgrade?" "y"
}

_confirm_legacy_upgrade() {
  local target_version="$1"

  log_warn "Legacy Cockpit-based Websoft9 architecture detected"
  log_warn "This is a cross-generation migration to the modern single-container runtime, not a routine in-place upgrade"
  log_warn "Potential risks: longer downtime, custom legacy assets may need manual verification, and rollback depends on the retained legacy backup and control plane"
  log_info "  Target modern version: ${target_version:-unknown}"

  if ! _confirm "I understand the risks above and want to continue to the migration confirmation step" "n"; then
    return 1
  fi

  _confirm "Proceed with the legacy-to-modern migration now?" "n"
}

# Hidden subcommands.
if [ -n "$_SUBCMD" ]; then
  case "$_SUBCMD" in
    detect)
      require_root
      detect_print_signals
      env_kind="$(detect_environment)"
      echo "$env_kind"
      ;;
    backup)
      require_root
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
    doctor|inspect)
      doctor_report "$OPT_PATH" "$OPT_CONSOLE_PORT"
      ;;
  esac
  exit "$EXIT_OK"
fi

require_root

# Main flow: detect the environment and execute the right path.
env_kind="$(detect_environment)"

if [ -n "$OPT_EXECUTE_MODE" ]; then
  log_info "Legacy compatibility: --execute_mode=${OPT_EXECUTE_MODE} accepted; environment auto-detection remains authoritative"
fi

case "$env_kind" in
  empty)
    log_step "No Websoft9 installation detected. Starting a fresh install"
    run_install "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_VERSION"
    ;;

  modern|legacy)
    _target_ver="$(_resolve_latest_version "$OPT_PATH" 2>/dev/null || true)"
    if [ -z "$_target_ver" ]; then
      _target_ver="$OPT_VERSION"
    fi

    if [ "$env_kind" = "modern" ]; then
      if ! _confirm_modern_upgrade "$OPT_PATH" "$_target_ver"; then
        log_info "Cancelled."
        exit "$EXIT_OK"
      fi
      run_upgrade_modern "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_VERSION"
    else
      if ! _confirm_legacy_upgrade "$_target_ver"; then
        log_info "Cancelled."
        exit "$EXIT_OK"
      fi
      if [ -n "$_OPT_CONSOLE_PORT_EXPLICIT" ]; then
        export W9_CONSOLE_PORT_EXPLICIT="1"
      else
        unset W9_CONSOLE_PORT_EXPLICIT || true
      fi
      run_upgrade_legacy "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_VERSION"
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
    run_upgrade_modern "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_VERSION"
    ;;

  *)
    die "$EXIT_ENV_GUARD" "Unknown environment state (${env_kind}), please contact support" ;;
esac

exit "$EXIT_OK"
