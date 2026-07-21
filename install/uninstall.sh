#!/bin/bash
# uninstall.sh — Websoft9 standalone uninstall entry
# Preserves the historical artifact contract: users can download and run this file directly.
# At publish time (install/build-bundle.sh) the lib/ files are inlined into a self-contained single file.
#
# Options:
#   --mode <stop|standard|purge>   uninstall mode (default: standard)
#   --path <dir>                   install directory (default: /opt/websoft9)
#   --keep-data [true|false]       retain data volume (default: true; bare flag = true)
#   --purge                        shortcut for --mode purge
#   --yes                          skip confirmations
#   --dry-run                      plan only, no destructive actions
#   --remove-legacy-controlplane   also clean up legacy Cockpit/systemd remnants

set -o pipefail

# Resolve the script directory and bundled libs.
W9_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
W9_ROOT_DIR="$(dirname "$W9_SCRIPT")"
W9_LIB_DIR="${W9_ROOT_DIR}/lib"
export W9_LIB_DIR

# Load libraries. This block is replaced during bundle generation
# so the release artifact becomes a single self-contained script.
# >>> WEBSOFT9_LIB_SOURCING >>>
# shellcheck source=lib/common.sh
. "${W9_LIB_DIR}/common.sh"
. "${W9_LIB_DIR}/detect.sh"
. "${W9_LIB_DIR}/backup.sh"
. "${W9_LIB_DIR}/validate.sh"
. "${W9_LIB_DIR}/uninstall.sh"
# <<< WEBSOFT9_LIB_SOURCING <<<

usage() {
  cat <<EOF
Websoft9 Uninstall Tool

Usage:
  sudo bash uninstall.sh [options]

Options:
  --mode <stop|standard|purge>   Uninstall mode (default: standard)
  --path <dir>                   Install directory (default: ${DEFAULT_INSTALL_PATH})
  --keep-data <true|false>       Retain runtime data (default: true)
  --yes                          Auto-confirm destructive actions
  --dry-run                      Plan only; make no destructive changes
  --remove-legacy-controlplane   Also remove legacy Cockpit/systemd remnants
  -h, --help                     Show this help
EOF
}

OPT_MODE="standard"
OPT_PATH="$DEFAULT_INSTALL_PATH"
OPT_KEEP_DATA="1"
OPT_YES="0"
OPT_REMOVE_CONTROLPLANE="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)           OPT_MODE="$2"; shift 2 ;;
    --path)           OPT_PATH="$2"; shift 2 ;;
    --keep-data)
      case "${2:-}" in
        true|TRUE|1)   OPT_KEEP_DATA="1"; shift 2 ;;
        false|FALSE|0) OPT_KEEP_DATA="0"; shift 2 ;;
        *)             OPT_KEEP_DATA="1"; shift ;;   # Bare --keep-data means retain data.
      esac
      ;;
    --purge)          OPT_MODE="purge"; shift ;;
    --yes)            OPT_YES="1"; shift ;;
    --dry-run)        W9_DRY_RUN="1"; export W9_DRY_RUN; shift ;;
    --remove-legacy-controlplane) OPT_REMOVE_CONTROLPLANE="1"; shift ;;
    -h|--help)        usage; exit "$EXIT_OK" ;;
    *) die "$EXIT_USAGE" "Unknown option: $1 (use -h for help)" ;;
  esac
done

require_root

export W9_INSTALL_PATH="$OPT_PATH"
env_kind="$(detect_environment)"
log_info "Environment: ${env_kind}"
run_uninstall "$env_kind" "$OPT_MODE" "$OPT_PATH" "$OPT_KEEP_DATA" "$OPT_YES" "$OPT_REMOVE_CONTROLPLANE"
exit "$EXIT_OK"
