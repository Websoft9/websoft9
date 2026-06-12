#!/bin/bash
set -Eeuo pipefail

KEEP_DATA=false
PURGE=false
DISABLE_ONLY=false
PURGE_LEGACY_ASSETS=false
INSTALL_PATH="/opt/websoft9"

readonly LEGACY_DEFAULT_PATH="/data/websoft9/source"
readonly LEGACY_CONTAINER_NAMES=("websoft9-apphub" "websoft9-deployment" "websoft9-git" "websoft9-proxy")
readonly LEGACY_VOLUME_NAMES=("apphub_logs" "apphub_config" "portainer" "gitea" "nginx_data" "nginx_letsencrypt" "nginx_modsec" "nginx_var")
readonly MODERN_VOLUME_NAMES=("product_data" "product_custom" "product_letsencrypt" "product_modsec" "product_logs")

ENV_KIND="unknown"
LEGACY_INSTALL_PATH=""
LEGACY_DOCKER_DIR=""

show_error() {
    echo "[ERR] $*" >&2
}

show_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --disable                Stop runtime only, keep data and deployment files
  --keep-data              Remove runtime, preserve volumes and certificates
  --purge                  Remove runtime, data, images, and known platform assets
  --purge-legacy-assets    Remove Cockpit/systemd/plugin leftovers during legacy purge
  --path                   Install path for modern runtime (default: /opt/websoft9)
  -h, --help               Show this help
EOF
    exit 0
}

require_arg() {
    local option="$1"
    local value="${2:-}"
    if [[ -z "$value" ]] || [[ "$value" == --* ]]; then
        show_error "Missing value for ${option}"
        exit 1
    fi
}

validate_options() {
    if $DISABLE_ONLY && { $KEEP_DATA || $PURGE || $PURGE_LEGACY_ASSETS; }; then
        show_error "--disable cannot be combined with --keep-data, --purge, or --purge-legacy-assets"
        exit 1
    fi

    if $KEEP_DATA && $PURGE; then
        show_error "--keep-data and --purge cannot be used together"
        exit 1
    fi

    if $PURGE_LEGACY_ASSETS && ! $PURGE; then
        show_error "--purge-legacy-assets requires --purge"
        exit 1
    fi
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

has_container() {
    command_exists docker || return 1
    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

has_volume() {
    command_exists docker || return 1
    docker volume inspect "$1" >/dev/null 2>&1
}

has_systemd_unit() {
    command_exists systemctl || return 1
    systemctl list-unit-files --type=service --type=socket 2>/dev/null | awk '{print $1}' | grep -qx "$1"
}

find_legacy_install_path() {
    local candidate
    for candidate in "$LEGACY_DEFAULT_PATH" "$INSTALL_PATH"; do
        [[ -f "$candidate/docker/docker-compose.yml" ]] && { echo "$candidate"; return 0; }
    done
    return 1
}

detect_environment() {
    local modern_signals=0
    local legacy_signals=0
    local legacy_container
    local legacy_volume

    if has_container "websoft9" || has_volume "product_data" || [[ -f "$INSTALL_PATH/docker-compose.yml" ]]; then
        modern_signals=$((modern_signals + 1))
    fi

    for legacy_container in "${LEGACY_CONTAINER_NAMES[@]}"; do
        if has_container "$legacy_container"; then
            legacy_signals=$((legacy_signals + 1))
        fi
    done

    for legacy_volume in "${LEGACY_VOLUME_NAMES[@]}"; do
        if has_volume "$legacy_volume"; then
            legacy_signals=$((legacy_signals + 1))
            break
        fi
    done

    if has_systemd_unit "cockpit.socket" || has_systemd_unit "websoft9.service"; then
        legacy_signals=$((legacy_signals + 1))
    fi

    LEGACY_INSTALL_PATH="$(find_legacy_install_path || true)"
    [[ -n "$LEGACY_INSTALL_PATH" ]] && LEGACY_DOCKER_DIR="${LEGACY_INSTALL_PATH}/docker"

    if (( modern_signals == 0 && legacy_signals == 0 )); then
        ENV_KIND="empty"
    elif (( modern_signals > 0 && legacy_signals == 0 )); then
        ENV_KIND="modern"
    elif (( modern_signals == 0 && legacy_signals > 0 )); then
        ENV_KIND="legacy"
    elif (( modern_signals > 0 && legacy_signals > 0 )); then
        ENV_KIND="mixed"
    else
        ENV_KIND="unknown"
    fi
}

validate_environment_strategy() {
    case "$ENV_KIND" in
        empty)
            echo "No recognized Websoft9 installation found"
            exit 0
            ;;
        unknown)
            show_error "Unable to classify current environment; refusing uninstall"
            exit 1
            ;;
        mixed)
            show_error "Refusing to uninstall automatically because legacy and modern runtimes are mixed"
            exit 1
            ;;
        modern)
            if $PURGE_LEGACY_ASSETS; then
                show_error "--purge-legacy-assets is only valid for legacy uninstall"
                exit 1
            fi
            ;;
        legacy)
            ;;
    esac
}

remove_volume_if_exists() {
    local volume_name="$1"
    has_volume "$volume_name" && docker volume rm -f "$volume_name" >/dev/null 2>&1 || true
}

stop_legacy_runtime() {
    if [[ -n "$LEGACY_DOCKER_DIR" ]] && [[ -f "$LEGACY_DOCKER_DIR/docker-compose.yml" ]]; then
        (cd "$LEGACY_DOCKER_DIR" && docker compose -p websoft9 down >/dev/null 2>&1) || true
    fi
    local legacy_container
    for legacy_container in "${LEGACY_CONTAINER_NAMES[@]}"; do
        docker rm -f "$legacy_container" >/dev/null 2>&1 || true
    done
    if command_exists systemctl; then
        systemctl stop websoft9 cockpit.socket cockpit >/dev/null 2>&1 || true
    fi
}

remove_legacy_assets() {
    if command_exists systemctl; then
        systemctl disable websoft9 cockpit.socket cockpit >/dev/null 2>&1 || true
    fi
    rm -f /lib/systemd/system/websoft9.service >/dev/null 2>&1 || true
    rm -rf /etc/cockpit/* >/dev/null 2>&1 || true
    rm -rf /usr/share/cockpit/* >/dev/null 2>&1 || true
}

stop_modern_runtime() {
    if [[ -f "$INSTALL_PATH/docker-compose.yml" ]]; then
        (cd "$INSTALL_PATH" && docker compose down >/dev/null 2>&1) || true
    fi
    docker rm -f websoft9 >/dev/null 2>&1 || true
}

remove_login_banner() {
    if grep -q "Websoft9" /etc/issue 2>/dev/null; then
        rm -f /etc/issue
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --disable) DISABLE_ONLY=true; shift ;;
        --keep-data) KEEP_DATA=true; shift ;;
        --purge) PURGE=true; shift ;;
        --purge-legacy-assets) PURGE_LEGACY_ASSETS=true; shift ;;
        --path) require_arg "$1" "${2:-}"; INSTALL_PATH="$2"; shift 2 ;;
        -h|--help) show_help ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

validate_options

if [[ $(id -u) -ne 0 ]]; then
    echo "This script must be run as root or with sudo."
    exit 1
fi

echo
echo "=========================================="
echo " Websoft9 lifecycle uninstaller"
echo "=========================================="

detect_environment
echo "Detected environment: ${ENV_KIND}"
validate_environment_strategy

case "$ENV_KIND" in
    modern)
        stop_modern_runtime
        if ! $DISABLE_ONLY; then
            if ! $KEEP_DATA; then
                volume_name=""
                for volume_name in "${MODERN_VOLUME_NAMES[@]}"; do
                    remove_volume_if_exists "$volume_name"
                done
            fi
            rm -rf "$INSTALL_PATH" >/dev/null 2>&1 || true
            if $PURGE; then
                docker images websoft9dev/websoft9 -q | xargs -r docker rmi -f >/dev/null 2>&1 || true
            fi
            remove_login_banner
        fi
        ;;
    legacy)
        stop_legacy_runtime
        if ! $DISABLE_ONLY; then
            if ! $KEEP_DATA; then
                volume_name=""
                for volume_name in "${LEGACY_VOLUME_NAMES[@]}"; do
                    remove_volume_if_exists "$volume_name"
                done
            fi
            [[ -n "$LEGACY_INSTALL_PATH" ]] && rm -rf "$LEGACY_INSTALL_PATH" >/dev/null 2>&1 || true
            if $PURGE || $PURGE_LEGACY_ASSETS; then
                remove_legacy_assets
            fi
            remove_login_banner
        fi
        ;;
esac

echo "=========================================="
if $DISABLE_ONLY; then
    echo "Runtime stopped; data and deployment files preserved"
elif $KEEP_DATA; then
    echo "Runtime removed; data preserved"
elif $PURGE; then
    echo "Runtime, data, and known images removed"
else
    echo "Standard uninstall completed"
fi
echo "=========================================="
