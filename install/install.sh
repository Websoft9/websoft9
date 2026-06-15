#!/bin/bash
set -Eeuo pipefail


if [[ $(id -u) -eq 0 ]]; then
	readonly LOG_DIR="/var/log/websoft9"
	readonly BACKUP_ROOT="/var/backups/websoft9"
	readonly MODERN_DEFAULT_PATH="/opt/websoft9"
else
	readonly USER_STATE_ROOT="${XDG_STATE_HOME:-${HOME}/.local/state}/websoft9"
	readonly USER_DATA_ROOT="${XDG_DATA_HOME:-${HOME}/.local/share}/websoft9"
	readonly LOG_DIR="${USER_STATE_ROOT}"
	readonly BACKUP_ROOT="${USER_DATA_ROOT}/backups"
	readonly MODERN_DEFAULT_PATH="${USER_DATA_ROOT}"
fi


readonly LOG_FILE="${LOG_DIR}/install.log"
readonly IMAGE_REPO="websoft9dev/websoft9"
readonly ARTIFACT_BASE="https://artifact.websoft9.com"
readonly PAGES_BASE="https://websoft9.github.io/websoft9"
readonly ARTIFACT_PROGRAM_ROOT="websoft9"
readonly LEGACY_DEFAULT_PATH="/data/websoft9/source"
readonly MODERN_CONTAINER_NAME="websoft9"
readonly LEGACY_CONTAINER_NAMES=("websoft9-apphub" "websoft9-deployment" "websoft9-git" "websoft9-proxy")
readonly LEGACY_VOLUME_NAMES=("apphub_logs" "apphub_config" "portainer" "gitea" "nginx_data" "nginx_letsencrypt" "nginx_modsec" "nginx_var")
readonly MODERN_VOLUME_NAMES=("product_data" "product_custom" "product_letsencrypt" "product_modsec" "product_logs")

VALIDATION_REPORT_FILE=""
LEGACY_MIGRATION_PLAN_FILE=""
LEGACY_SNAPSHOT_FILE=""
HEALTHCHECK_WAIT_SECONDS=""

VERSION="latest"
CHANNEL="release"
MODE="install"
CHECK_ONLY=false
INSTALL_PATH="${MODERN_DEFAULT_PATH}"
LEGACY_PATH=""
CONSOLE_PORT="9000"
APP_HTTP_GATEWAY="80"
APP_HTTPS_GATEWAY="443"
MIRRORS=""
PROXY=""

INSTALL_PATH_SET=false
CONSOLE_PORT_SET=false
HTTP_GATEWAY_SET=false
HTTPS_GATEWAY_SET=false

ENV_KIND="unknown"
LEGACY_INSTALL_PATH=""
LEGACY_DOCKER_DIR=""
LEGACY_ENV_FILE=""
LEGACY_COMPOSE_FILE=""
LEGACY_COCKPIT_PORT=""
BACKUP_DIR=""
IMAGE_TAG=""
WORK_IMAGE=""
OLD_COCKPIT_ACTIVE=false
OLD_COCKPIT_SOCKET_ACTIVE=false
OLD_WEBSOFT9_SERVICE_ACTIVE=false
START_TIME=$(date +%s)
STEP_NUM=0
ENTRYPOINT_NAME="$(basename "$0")"

is_root() {
	[[ $(id -u) -eq 0 ]]
}

init_logging() {
	mkdir -p "$LOG_DIR"
	if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt 1048576 ]]; then
		mv "$LOG_FILE" "${LOG_FILE}.1"
	fi
	printf '\n========== %s | install.sh lifecycle ==========%s' "$(date '+%Y-%m-%d %H:%M:%S')" $'\n' >> "$LOG_FILE"
}

log_info() {
	printf '  [OK] %s\n' "$*" | tee -a "$LOG_FILE"
}

log_warn() {
	printf '  [WARN] %s\n' "$*" | tee -a "$LOG_FILE"
}

log_error() {
	printf '  [ERR] %s\n' "$*" | tee -a "$LOG_FILE" >&2
}

log_step() {
	STEP_NUM=$((STEP_NUM + 1))
	printf '\n-- Step %s: %s\n' "$STEP_NUM" "$*" | tee -a "$LOG_FILE"
}

on_error() {
	local exit_code=$?
	log_error "Failed at line ${1} (exit code: ${exit_code})"
	log_error "See full log: ${LOG_FILE}"
	exit "$exit_code"
}

show_help() {
	cat <<EOF
Usage: ${ENTRYPOINT_NAME} [OPTIONS]

Options:
  --mode              install | upgrade (default: install)
  --check             Run lifecycle checks only
  --version           Image version tag (default: latest)
  --channel           release | rc | dev (default: release)
  --console_port      Console web port (default: 9000)
  --app_http_gateway  HTTP gateway port (default: 80)
  --app_https_gateway HTTPS gateway port (default: 443)
  --path              Modern install directory (default: ${MODERN_DEFAULT_PATH})
  --legacy_path       Legacy install directory override
  --mirrors           Docker registry mirrors, comma-separated
  --proxy             HTTP/HTTPS proxy

Examples:
	curl -fsSL https://artifact.websoft9.com/websoft9/release/install.sh | bash
  bash install.sh --check
  bash install.sh --mode upgrade --version 3.0.0

Notes:
  - New install and modern-to-modern upgrade support non-root execution when Docker is already installed and your user can access Docker.
  - Legacy Cockpit-based migration upgrade still requires root.
EOF
	exit 0
}

require_arg() {
	local option="$1"
	local value="${2:-}"
	if [[ -z "$value" ]] || [[ "$value" == --* ]]; then
		echo "Missing value for ${option}" >&2
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

find_modern_install_path() {
	local working_dir=""
	local config_files=""
	local primary_config=""
	local candidate=""
	local candidates=(
		"$MODERN_DEFAULT_PATH"
		"/opt/websoft9"
		"${XDG_DATA_HOME:-${HOME}/.local/share}/websoft9"
	)

	if command_exists docker && has_container "$MODERN_CONTAINER_NAME"; then
		working_dir=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$MODERN_CONTAINER_NAME" 2>/dev/null || true)
		if [[ -n "$working_dir" ]] && [[ "$working_dir" != "<no value>" ]] && [[ -f "$working_dir/docker-compose.yml" ]]; then
			echo "$working_dir"
			return 0
		fi

		config_files=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$MODERN_CONTAINER_NAME" 2>/dev/null || true)
		primary_config="${config_files%%,*}"
		if [[ -n "$primary_config" ]] && [[ "$primary_config" != "<no value>" ]]; then
			working_dir="$(dirname "$primary_config")"
			if [[ -f "$working_dir/docker-compose.yml" ]]; then
				echo "$working_dir"
				return 0
			fi
		fi
	fi

	for candidate in "${candidates[@]}"; do
		if [[ -f "$candidate/docker-compose.yml" ]]; then
			echo "$candidate"
			return 0
		fi
	done

	return 1
}

resolve_modern_install_path() {
	local detected_install_path=""

	if $INSTALL_PATH_SET || [[ "$ENV_KIND" != "modern" ]]; then
		return 0
	fi

	detected_install_path="$(find_modern_install_path || true)"
	if [[ -n "$detected_install_path" ]]; then
		INSTALL_PATH="$detected_install_path"
		log_info "Detected modern install path: ${INSTALL_PATH}"
	fi
}

ensure_install_path_access() {
	local probe_path="$INSTALL_PATH"

	while [[ ! -e "$probe_path" && "$probe_path" != "/" ]]; do
		probe_path="$(dirname "$probe_path")"
	done

	if [[ ! -w "$probe_path" ]]; then
		if $CHECK_ONLY; then
			log_warn "Install path is not writable for current user: ${INSTALL_PATH}"
			return 0
		fi
		log_error "Install path is not writable for current user: ${INSTALL_PATH}"
		exit 1
	fi
}

ensure_docker_access() {
	if ! docker info >/dev/null 2>&1; then
		log_error "Docker is not accessible for current user. Ensure Docker is running and your account can access the Docker daemon."
		exit 1
	fi
}

validate_execution_permissions() {
	if ! is_root && ! $CHECK_ONLY && [[ "$MODE" == "upgrade" && "$ENV_KIND" == "legacy" ]]; then
		log_error "Legacy Cockpit-based migration upgrade must run as root"
		exit 1
	fi
}

assess_runtime_capabilities() {
	ensure_install_path_access

	if command_exists docker; then
		if docker info >/dev/null 2>&1; then
			log_info "Docker daemon: accessible"
		else
			if ! is_root; then
				log_warn "Docker is installed but current user cannot access the Docker daemon"
			fi
		fi
	else
		if is_root; then
			log_warn "Docker is not installed; root mode can attempt installation"
		else
			log_warn "Docker is not installed; non-root mode requires Docker to be preinstalled"
		fi
	fi
}

read_env_value() {
	local file_path="$1"
	local key="$2"
	[[ -f "$file_path" ]] || return 1
	grep -E "^${key}=" "$file_path" | tail -n 1 | cut -d '=' -f 2-
}

find_legacy_install_path() {
	local candidate
	for candidate in "$LEGACY_PATH" "$LEGACY_DEFAULT_PATH" "/data/websoft9" "$INSTALL_PATH"; do
		[[ -n "$candidate" ]] || continue
		if [[ -f "$candidate/docker/docker-compose.yml" ]]; then
			echo "$candidate"
			return 0
		fi
	done
	return 1
}

load_legacy_context() {
	LEGACY_INSTALL_PATH="$(find_legacy_install_path || true)"
	if [[ -n "$LEGACY_INSTALL_PATH" ]]; then
		LEGACY_DOCKER_DIR="${LEGACY_INSTALL_PATH}/docker"
		LEGACY_ENV_FILE="${LEGACY_INSTALL_PATH}/.env"
		LEGACY_COMPOSE_FILE="${LEGACY_DOCKER_DIR}/docker-compose.yml"
	fi

	if [[ -n "$LEGACY_ENV_FILE" ]] && [[ -f "$LEGACY_ENV_FILE" ]]; then
		if ! $CONSOLE_PORT_SET; then
			LEGACY_COCKPIT_PORT="$(read_env_value "$LEGACY_ENV_FILE" "CONSOLE_PORT" || true)"
			[[ -n "$LEGACY_COCKPIT_PORT" ]] && CONSOLE_PORT="$LEGACY_COCKPIT_PORT"
		fi
		if ! $HTTP_GATEWAY_SET; then
			APP_HTTP_GATEWAY="$(read_env_value "$LEGACY_ENV_FILE" "APP_HTTP_GATEWAY" || echo "$APP_HTTP_GATEWAY")"
		fi
		if ! $HTTPS_GATEWAY_SET; then
			APP_HTTPS_GATEWAY="$(read_env_value "$LEGACY_ENV_FILE" "APP_HTTPS_GATEWAY" || echo "$APP_HTTPS_GATEWAY")"
		fi
	fi

	if [[ -z "$LEGACY_COCKPIT_PORT" ]] && [[ -f /usr/lib/systemd/system/cockpit.socket ]] && ! $CONSOLE_PORT_SET; then
		LEGACY_COCKPIT_PORT="$(sed -nE 's|ListenStream=([0-9]+)|\1|p' /usr/lib/systemd/system/cockpit.socket 2>/dev/null || true)"
		[[ -n "$LEGACY_COCKPIT_PORT" ]] && CONSOLE_PORT="$LEGACY_COCKPIT_PORT"
	fi
}

detect_environment() {
	local modern_signals=0
	local legacy_signals=0
	local legacy_container
	local legacy_volume

	if has_container "$MODERN_CONTAINER_NAME" || has_volume "product_data" || [[ -f "$INSTALL_PATH/docker-compose.yml" ]]; then
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

	if find_legacy_install_path >/dev/null 2>&1; then
		legacy_signals=$((legacy_signals + 1))
	fi

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

resolve_mode() {
	case "$MODE" in
		install)
			[[ "$ENV_KIND" == "empty" ]] || {
				log_error "Install mode requires an empty environment. Detected: ${ENV_KIND}. Use --mode upgrade for upgrade or migration."
				exit 1
			}
			;;
		upgrade)
			[[ "$ENV_KIND" != "empty" ]] || {
				log_error "Upgrade mode requires an existing environment"
				exit 1
			}
			[[ "$ENV_KIND" != "mixed" && "$ENV_KIND" != "unknown" ]] || {
				log_error "Upgrade mode is blocked for environment type: ${ENV_KIND}"
				exit 1
			}
			;;
		*)
			log_error "Invalid mode: ${MODE}. Use install | upgrade"
			exit 1
			;;
	esac
}

show_banner() {
	echo
	echo "============================================"
	echo "Websoft9 lifecycle installer"
	echo "============================================"
	echo "Environment:  ${ENV_KIND}"
	echo "Mode:         ${MODE}"
	echo "Version:      ${VERSION}"
	echo "Channel:      ${CHANNEL}"
	echo "Console Port: ${CONSOLE_PORT}"
	echo "HTTP Port:    ${APP_HTTP_GATEWAY}"
	echo "HTTPS Port:   ${APP_HTTPS_GATEWAY}"
	echo "Install Path: ${INSTALL_PATH}"
	[[ -n "$LEGACY_INSTALL_PATH" ]] && echo "Legacy Path:  ${LEGACY_INSTALL_PATH}"
	echo "Log:          ${LOG_FILE}"
	echo
}

ensure_supported_os() {
	[[ -f /etc/os-release ]] || {
		log_error "Unsupported OS"
		exit 1
	}
	. /etc/os-release
	log_info "OS: ${PRETTY_NAME}"
}

check_disk() {
	local available_kb
	available_kb=$(df -P / | awk 'NR==2 {print $4}')
	if [[ "$available_kb" -lt 2097152 ]]; then
		log_error "Insufficient disk space. Need at least 2GB free"
		exit 1
	fi
	log_info "Disk: $((available_kb / 1024 / 1024))GB free"
}

check_target_ports() {
	local ports=()
	local port

	if [[ "$MODE" == "install" || "$ENV_KIND" == "legacy" ]]; then
		ports=("$CONSOLE_PORT" "$APP_HTTP_GATEWAY" "$APP_HTTPS_GATEWAY")
	fi

	for port in "${ports[@]}"; do
		if ss -tuln 2>/dev/null | grep -q ":${port} "; then
			log_warn "Port ${port} is currently in use; installer will need to reclaim it"
		else
			log_info "Port ${port}: available"
		fi
	done
}

install_pkg() {
	local pkg="$1"
	command_exists "$pkg" && return 0
	if ! is_root; then
		log_error "Missing required package ${pkg}. Install it first or rerun as root."
		exit 1
	fi
	if command_exists apt-get; then
		apt-get update -qq >/dev/null 2>&1
		apt-get install -y -qq "$pkg" >> "$LOG_FILE" 2>&1
	elif command_exists dnf; then
		dnf install -y -q "$pkg" >> "$LOG_FILE" 2>&1
	elif command_exists yum; then
		yum install -y -q "$pkg" >> "$LOG_FILE" 2>&1
	else
		log_error "No supported package manager found"
		exit 1
	fi
}

install_prereqs() {
	log_step "Installing prerequisites"
	install_pkg curl
	install_pkg jq
	install_pkg tar
}

setup_docker() {
	log_step "Setting up Docker"
	if command_exists docker; then
		log_info "Docker: $(docker --version | awk '{print $3}' | sed 's/,//')"
	else
		if ! is_root; then
			log_error "Docker is not installed. Install Docker first or rerun as root."
			exit 1
		fi
		log_info "Installing Docker"
		curl -fsSL https://get.docker.com | bash >> "$LOG_FILE" 2>&1
		systemctl enable docker >> "$LOG_FILE" 2>&1 || true
		systemctl start docker >> "$LOG_FILE" 2>&1
	fi

	ensure_docker_access

	if ! docker compose version >/dev/null 2>&1; then
		if ! is_root; then
			log_error "Docker Compose plugin is required. Install it first or rerun as root."
			exit 1
		fi
		log_error "Docker Compose plugin is required"
		exit 1
	fi

	if [[ -n "$MIRRORS" ]]; then
		if ! is_root; then
			log_error "Configuring Docker registry mirrors requires root"
			exit 1
		fi
		local json='['
		local first=true
		local mirror
		IFS=',' read -ra mirrors_array <<< "$MIRRORS"
		for mirror in "${mirrors_array[@]}"; do
			$first || json+=','
			json+="\"${mirror}\""
			first=false
		done
		json+=']'
		mkdir -p /etc/docker
		printf '{"registry-mirrors": %s}\n' "$json" > /etc/docker/daemon.json
		systemctl restart docker >> "$LOG_FILE" 2>&1
	fi
}

prepare_backup_dir() {
	BACKUP_DIR="${BACKUP_ROOT}/$(date '+%Y%m%d-%H%M%S')-${ENV_KIND}-${MODE}"
	mkdir -p "$BACKUP_DIR"
	log_info "Backup directory: ${BACKUP_DIR}"
}

capture_runtime_metadata() {
	command_exists docker || return 0
	docker ps -a > "${BACKUP_DIR}/docker-ps.txt" 2>&1 || true
	docker volume ls > "${BACKUP_DIR}/docker-volumes.txt" 2>&1 || true
	docker images > "${BACKUP_DIR}/docker-images.txt" 2>&1 || true
}

backup_file_if_exists() {
	local source_path="$1"
	local dest_name="$2"
	[[ -f "$source_path" ]] || return 0
	cp "$source_path" "${BACKUP_DIR}/${dest_name}"
}

backup_named_volume() {
	local volume_name="$1"
	local archive_name="$2"
	has_volume "$volume_name" || return 0
	docker run --rm \
		-v "${volume_name}:/from:ro" \
		-v "${BACKUP_DIR}:/backup" \
		--entrypoint sh \
		alpine \
		-c "cd /from && tar cf /backup/${archive_name} ." >> "$LOG_FILE" 2>&1
}

restore_archive_to_volume() {
	local archive_name="$1"
	local volume_name="$2"
	local subdir="$3"
	[[ -f "${BACKUP_DIR}/${archive_name}" ]] || return 0
	docker volume create "$volume_name" >/dev/null 2>&1 || true
	docker run --rm \
		-v "${volume_name}:/to" \
		-v "${BACKUP_DIR}:/backup:ro" \
		--entrypoint sh \
		alpine \
		-c "mkdir -p /to/${subdir} && cd /to/${subdir} && tar xf /backup/${archive_name}" >> "$LOG_FILE" 2>&1
}

backup_modern_state() {
	log_step "Backing up modern runtime state"
	prepare_backup_dir
	capture_runtime_metadata
	backup_file_if_exists "${INSTALL_PATH}/docker-compose.yml" "modern-docker-compose.yml"
	backup_file_if_exists "${INSTALL_PATH}/.env" "modern.env"
	backup_named_volume "product_data" "product_data.tar"
	backup_named_volume "product_custom" "product_custom.tar"
	backup_named_volume "product_letsencrypt" "product_letsencrypt.tar"
	backup_named_volume "product_modsec" "product_modsec.tar"
	backup_named_volume "product_logs" "product_logs.tar"
}

backup_legacy_state() {
	log_step "Backing up legacy runtime state"
	prepare_backup_dir
	capture_runtime_metadata
	backup_file_if_exists "$LEGACY_COMPOSE_FILE" "legacy-docker-compose.yml"
	backup_file_if_exists "$LEGACY_ENV_FILE" "legacy.env"
	backup_named_volume "apphub_logs" "apphub_logs.tar"
	backup_named_volume "apphub_config" "apphub_config.tar"
	backup_named_volume "portainer" "portainer.tar"
	backup_named_volume "gitea" "gitea.tar"
	backup_named_volume "nginx_data" "nginx_data.tar"
	backup_named_volume "nginx_letsencrypt" "nginx_letsencrypt.tar"
	backup_named_volume "nginx_modsec" "nginx_modsec.tar"
	backup_named_volume "nginx_var" "nginx_var.tar"
}

download_compose() {
	mkdir -p "$INSTALL_PATH"
	local url
	local compose_urls=(
		"${ARTIFACT_BASE}/${ARTIFACT_PROGRAM_ROOT}/${CHANNEL}/docker-compose.yml"
		"${ARTIFACT_BASE}/${ARTIFACT_PROGRAM_ROOT}/${CHANNEL}/platform/docker-compose.yml"
	)

	if [[ "$CHANNEL" == "release" ]]; then
		compose_urls+=(
			"${PAGES_BASE}/docker/docker-compose.yml"
			"${ARTIFACT_BASE}/${ARTIFACT_PROGRAM_ROOT}/release/platform/docker-compose.yml"
			"${ARTIFACT_BASE}/${ARTIFACT_PROGRAM_ROOT}/release/websoft9/docker-compose.yml"
		)
	fi

	for url in "${compose_urls[@]}"; do
		log_info "Trying: ${url}"
		if curl -fsSL --retry 2 --retry-delay 2 --connect-timeout 10 -o "${INSTALL_PATH}/docker-compose.yml" "$url" 2>/dev/null; then
			log_info "Downloaded from: ${url}"
			return 0
		fi
	done
	return 1
}

patch_compose_ports() {
	sed -i \
		-e "s|- \"80:80\"|- \"${APP_HTTP_GATEWAY}:80\"|" \
		-e "s|- \"443:443\"|- \"${APP_HTTPS_GATEWAY}:443\"|" \
		"${INSTALL_PATH}/docker-compose.yml"
}

determine_image_tag() {
	case "$CHANNEL" in
		release) IMAGE_TAG="$VERSION" ;;
		rc) IMAGE_TAG="$VERSION" ;;
		dev) IMAGE_TAG="${VERSION}-dev" ;;
		*) log_error "Unknown channel: ${CHANNEL}"; exit 1 ;;
	esac

	if [[ "$VERSION" == "latest" ]]; then
		case "$CHANNEL" in
			release) IMAGE_TAG="latest" ;;
			rc) IMAGE_TAG="rc" ;;
			dev) IMAGE_TAG="dev" ;;
		esac
	fi

	WORK_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"
	log_info "Image: ${WORK_IMAGE}"
}

pull_target_image() {
	log_step "Pulling target image"
	(cd "$INSTALL_PATH" && docker compose pull >> "$LOG_FILE" 2>&1)
}

write_modern_env() {
	cat > "${INSTALL_PATH}/.env" <<EOF
IMAGE_REPO=${IMAGE_REPO}
IMAGE_TAG=${IMAGE_TAG}
CONSOLE_PORT=${CONSOLE_PORT}
APP_HTTP_GATEWAY=${APP_HTTP_GATEWAY}
APP_HTTPS_GATEWAY=${APP_HTTPS_GATEWAY}
NETWORK_NAME=websoft9
WEBSOFT9_PRODUCT_VERSION=${VERSION}
EOF
}

prepare_modern_runtime_artifacts() {
	log_step "Preparing deployment artifacts"
	download_compose || {
		log_error "Failed to download docker-compose.yml"
		exit 1
	}
	patch_compose_ports
	determine_image_tag
	write_modern_env
}

record_legacy_service_state() {
	command_exists systemctl || return 0
	systemctl is-active cockpit >/dev/null 2>&1 && OLD_COCKPIT_ACTIVE=true || true
	systemctl is-active cockpit.socket >/dev/null 2>&1 && OLD_COCKPIT_SOCKET_ACTIVE=true || true
	systemctl is-active websoft9 >/dev/null 2>&1 && OLD_WEBSOFT9_SERVICE_ACTIVE=true || true
}

validate_legacy_upgrade_context() {
	log_step "Validating legacy migration context"

	if [[ -z "$LEGACY_INSTALL_PATH" ]] && [[ -z "$LEGACY_DOCKER_DIR" ]]; then
		log_error "Legacy migration requires a detected legacy install path"
		exit 1
	fi

	if [[ ! -f "$LEGACY_COMPOSE_FILE" ]]; then
		log_warn "Legacy compose file was not found at ${LEGACY_COMPOSE_FILE}; container-only migration fallback will be used if legacy containers exist"
	fi

	local legacy_runtime_detected=false
	local legacy_container
	local legacy_volume

	for legacy_container in "${LEGACY_CONTAINER_NAMES[@]}"; do
		if has_container "$legacy_container"; then
			legacy_runtime_detected=true
			break
		fi
	done

	for legacy_volume in "${LEGACY_VOLUME_NAMES[@]}"; do
		if has_volume "$legacy_volume"; then
			legacy_runtime_detected=true
			break
		fi
	done

	[[ -f "$LEGACY_COMPOSE_FILE" ]] && legacy_runtime_detected=true

	$legacy_runtime_detected || {
		log_error "No legacy runtime assets were detected for migration"
		exit 1
	}
}

validate_legacy_backup_payload() {
	log_step "Validating legacy backup payload"

	local required_assets=(
		"apphub_config.tar:product_data/legacy/apphub-config:required"
		"apphub_logs.tar:product_logs/legacy-apphub:required"
		"nginx_data.tar:product_data/nginx-proxy-manager:required"
	)
	local optional_assets=(
		"gitea.tar:product_data/gitea:optional"
		"portainer.tar:product_data/portainer:optional"
		"nginx_letsencrypt.tar:product_letsencrypt/:optional"
		"nginx_modsec.tar:product_modsec/:optional"
		"nginx_var.tar:product_custom/:optional"
	)
	local asset_spec
	local archive_name
	local target_path
	local missing_required=()
	local available_required=0

	for asset_spec in "${required_assets[@]}"; do
		archive_name="${asset_spec%%:*}"
		target_path="${asset_spec#*:}"
		target_path="${target_path%%:*}"
		if [[ -f "${BACKUP_DIR}/${archive_name}" ]]; then
			log_info "Legacy required asset ready: ${archive_name} -> ${target_path}"
			available_required=$((available_required + 1))
		else
			log_error "Legacy required asset missing: ${archive_name} -> ${target_path}"
			missing_required+=("${archive_name}")
		fi
	done

	for asset_spec in "${optional_assets[@]}"; do
		archive_name="${asset_spec%%:*}"
		target_path="${asset_spec#*:}"
		target_path="${target_path%%:*}"
		if [[ -f "${BACKUP_DIR}/${archive_name}" ]]; then
			log_info "Legacy optional asset ready: ${archive_name} -> ${target_path}"
		else
			log_warn "Legacy optional asset missing: ${archive_name} -> ${target_path}"
		fi
	done

	(( available_required > 0 )) || {
		log_error "Legacy backup does not contain any required migration payload"
		exit 1
	}

	if [[ ${#missing_required[@]} -gt 0 ]]; then
		log_error "Legacy migration is blocked because required assets are missing: ${missing_required[*]}"
		exit 1
	fi
}

write_legacy_environment_snapshot() {
	log_step "Recording legacy environment snapshot"

	local snapshot_file="${BACKUP_DIR}/legacy-environment-snapshot.txt"
	local legacy_container
	local legacy_volume

	LEGACY_SNAPSHOT_FILE="$snapshot_file"

	cat > "$snapshot_file" <<EOF
source_environment=${ENV_KIND}
legacy_install_path=${LEGACY_INSTALL_PATH:-unknown}
legacy_compose_file=${LEGACY_COMPOSE_FILE:-missing}
legacy_console_port=${LEGACY_COCKPIT_PORT:-unknown}

[containers]
EOF

	for legacy_container in "${LEGACY_CONTAINER_NAMES[@]}"; do
		if has_container "$legacy_container"; then
			printf '%s=present\n' "$legacy_container" >> "$snapshot_file"
		else
			printf '%s=missing\n' "$legacy_container" >> "$snapshot_file"
		fi
	done

	printf '\n[volumes]\n' >> "$snapshot_file"
	for legacy_volume in "${LEGACY_VOLUME_NAMES[@]}"; do
		if has_volume "$legacy_volume"; then
			printf '%s=present\n' "$legacy_volume" >> "$snapshot_file"
		else
			printf '%s=missing\n' "$legacy_volume" >> "$snapshot_file"
		fi
	done

	printf '\n[systemd]\n' >> "$snapshot_file"
	if has_systemd_unit "cockpit.socket"; then
		printf 'cockpit.socket=known\n' >> "$snapshot_file"
	else
		printf 'cockpit.socket=missing\n' >> "$snapshot_file"
	fi
	if has_systemd_unit "websoft9.service"; then
		printf 'websoft9.service=known\n' >> "$snapshot_file"
	else
		printf 'websoft9.service=missing\n' >> "$snapshot_file"
	fi
}

write_legacy_migration_plan() {
	log_step "Writing legacy migration plan"

	local migration_assets=(
		"apphub_config.tar:product_data/legacy/apphub-config:required"
		"apphub_logs.tar:product_logs/legacy-apphub:required"
		"nginx_data.tar:product_data/nginx-proxy-manager:required"
		"gitea.tar:product_data/gitea:optional"
		"portainer.tar:product_data/portainer:optional"
		"nginx_letsencrypt.tar:product_letsencrypt/:optional"
		"nginx_modsec.tar:product_modsec/:optional"
		"nginx_var.tar:product_custom/:optional"
	)
	local asset_spec
	local archive_name
	local target_path
	local requirement_level

	LEGACY_MIGRATION_PLAN_FILE="${BACKUP_DIR}/legacy-migration-plan.txt"

	cat > "$LEGACY_MIGRATION_PLAN_FILE" <<EOF
mode=legacy-upgrade
source_environment=${ENV_KIND}
legacy_install_path=${LEGACY_INSTALL_PATH:-unknown}
legacy_compose_file=${LEGACY_COMPOSE_FILE:-missing}
target_install_path=${INSTALL_PATH}
target_image=${WORK_IMAGE}
target_console_port=${CONSOLE_PORT}
target_http_port=${APP_HTTP_GATEWAY}
target_https_port=${APP_HTTPS_GATEWAY}

[asset-map]
gitea=product_data/gitea
portainer=product_data/portainer
nginx_data=product_data/nginx-proxy-manager
nginx_letsencrypt=product_letsencrypt/
nginx_modsec=product_modsec/
nginx_var=product_custom/
apphub_logs=product_logs/legacy-apphub
apphub_config=product_data/legacy/apphub-config

[rollback]
legacy_runtime_restore=enabled
modern_runtime_restore=not_applicable_for_legacy_source
EOF

	printf '\n[backup-status]\n' >> "$LEGACY_MIGRATION_PLAN_FILE"
	for asset_spec in "${migration_assets[@]}"; do
		archive_name="${asset_spec%%:*}"
		target_path="${asset_spec#*:}"
		requirement_level="${target_path##*:}"
		target_path="${target_path%%:*}"
		if [[ -f "${BACKUP_DIR}/${archive_name}" ]]; then
			printf '%s=%s ready -> %s\n' "$archive_name" "$requirement_level" "$target_path" >> "$LEGACY_MIGRATION_PLAN_FILE"
		else
			printf '%s=%s missing -> %s\n' "$archive_name" "$requirement_level" "$target_path" >> "$LEGACY_MIGRATION_PLAN_FILE"
		fi
	done
}

migrate_legacy_assets() {
	log_step "Migrating legacy assets"
	local migration_assets=(
		"apphub_config.tar:product_data:legacy/apphub-config:required"
		"apphub_logs.tar:product_logs:legacy-apphub:required"
		"nginx_data.tar:product_data:nginx-proxy-manager:required"
		"gitea.tar:product_data:gitea:optional"
		"portainer.tar:product_data:portainer:optional"
		"nginx_letsencrypt.tar:product_letsencrypt::optional"
		"nginx_modsec.tar:product_modsec::optional"
		"nginx_var.tar:product_custom::optional"
	)
	local asset_spec
	local archive_name
	local volume_name
	local subdir
	local requirement_level

	for asset_spec in "${migration_assets[@]}"; do
		archive_name="${asset_spec%%:*}"
		volume_name="${asset_spec#*:}"
		subdir="${volume_name#*:}"
		requirement_level="${subdir##*:}"
		volume_name="${volume_name%%:*}"
		subdir="${subdir%%:*}"

		if [[ -f "${BACKUP_DIR}/${archive_name}" ]]; then
			restore_archive_to_volume "$archive_name" "$volume_name" "$subdir"
		elif [[ "$requirement_level" == "required" ]]; then
			log_error "Required legacy archive disappeared before migration: ${archive_name}"
			exit 1
		fi
	done
}

stop_legacy_runtime() {
	log_step "Stopping legacy runtime"
	record_legacy_service_state
	if [[ -n "$LEGACY_DOCKER_DIR" && -f "$LEGACY_COMPOSE_FILE" ]]; then
		(cd "$LEGACY_DOCKER_DIR" && docker compose -p websoft9 down >> "$LOG_FILE" 2>&1) || true
	else
		local legacy_container
		for legacy_container in "${LEGACY_CONTAINER_NAMES[@]}"; do
			docker stop "$legacy_container" >> "$LOG_FILE" 2>&1 || true
		done
	fi
	if command_exists systemctl; then
		systemctl stop cockpit.socket >> "$LOG_FILE" 2>&1 || true
		systemctl stop cockpit >> "$LOG_FILE" 2>&1 || true
		systemctl stop websoft9 >> "$LOG_FILE" 2>&1 || true
	fi
}

restore_legacy_runtime() {
	log_warn "Restoring legacy runtime"
	docker rm -f "$MODERN_CONTAINER_NAME" >> "$LOG_FILE" 2>&1 || true
	if [[ -n "$LEGACY_DOCKER_DIR" && -f "$LEGACY_COMPOSE_FILE" ]]; then
		(cd "$LEGACY_DOCKER_DIR" && docker compose -p websoft9 up -d >> "$LOG_FILE" 2>&1) || true
	fi
	if command_exists systemctl; then
		$OLD_COCKPIT_SOCKET_ACTIVE && systemctl start cockpit.socket >> "$LOG_FILE" 2>&1 || true
		$OLD_COCKPIT_ACTIVE && systemctl start cockpit >> "$LOG_FILE" 2>&1 || true
		$OLD_WEBSOFT9_SERVICE_ACTIVE && systemctl start websoft9 >> "$LOG_FILE" 2>&1 || true
	fi
}

restore_modern_runtime() {
	log_warn "Restoring previous modern runtime"
	docker rm -f "$MODERN_CONTAINER_NAME" >> "$LOG_FILE" 2>&1 || true
	[[ -f "${BACKUP_DIR}/modern.env" ]] && cp "${BACKUP_DIR}/modern.env" "${INSTALL_PATH}/.env"
	[[ -f "${BACKUP_DIR}/modern-docker-compose.yml" ]] && cp "${BACKUP_DIR}/modern-docker-compose.yml" "${INSTALL_PATH}/docker-compose.yml"
	restore_archive_to_volume "product_data.tar" "product_data" ""
	restore_archive_to_volume "product_custom.tar" "product_custom" ""
	restore_archive_to_volume "product_letsencrypt.tar" "product_letsencrypt" ""
	restore_archive_to_volume "product_modsec.tar" "product_modsec" ""
	restore_archive_to_volume "product_logs.tar" "product_logs" ""
	(cd "$INSTALL_PATH" && docker compose up -d >> "$LOG_FILE" 2>&1) || true
}

start_modern_runtime() {
	log_step "Starting modern runtime"
	(cd "$INSTALL_PATH" && docker compose up -d >> "$LOG_FILE" 2>&1)
}

health_check() {
	log_step "Health check"
	local waited=0
	local max_wait=180
	while (( waited < max_wait )); do
		if docker exec "$MODERN_CONTAINER_NAME" /websoft9/script/platform-healthcheck.sh --readiness >/dev/null 2>&1; then
			HEALTHCHECK_WAIT_SECONDS="$waited"
			log_info "Healthy after ${waited}s"
			return 0
		fi
		sleep 3
		waited=$((waited + 3))
	done
	return 1
}

write_runtime_validation_report() {
	log_step "Writing validation report"

	local report_dir="$INSTALL_PATH"
	local container_image="unknown"
	local container_status="missing"

	if [[ -n "$BACKUP_DIR" ]]; then
		report_dir="$BACKUP_DIR"
	fi

	VALIDATION_REPORT_FILE="${report_dir}/runtime-validation-report.txt"

	if command_exists docker && has_container "$MODERN_CONTAINER_NAME"; then
		container_status="$(docker inspect -f '{{.State.Status}}' "$MODERN_CONTAINER_NAME" 2>/dev/null || echo running)"
		container_image="$(docker inspect -f '{{.Config.Image}}' "$MODERN_CONTAINER_NAME" 2>/dev/null || echo "$WORK_IMAGE")"
	fi

	cat > "$VALIDATION_REPORT_FILE" <<EOF
mode=${MODE}
source_environment=${ENV_KIND}
target_install_path=${INSTALL_PATH}
target_image=${container_image}
target_container=${MODERN_CONTAINER_NAME}
target_container_status=${container_status}
console_port=${CONSOLE_PORT}
http_port=${APP_HTTP_GATEWAY}
https_port=${APP_HTTPS_GATEWAY}
healthcheck_wait_seconds=${HEALTHCHECK_WAIT_SECONDS:-unknown}
backup_dir=${BACKUP_DIR:-none}

[artifacts]
validation_report=${VALIDATION_REPORT_FILE}
legacy_migration_plan=${LEGACY_MIGRATION_PLAN_FILE:-none}
legacy_environment_snapshot=${LEGACY_SNAPSHOT_FILE:-none}
EOF

	if [[ "$MODE" == "upgrade" && "$ENV_KIND" == "legacy" ]]; then
		printf '\n[legacy-migration]\n' >> "$VALIDATION_REPORT_FILE"
		printf 'migration_plan_recorded=%s\n' "${LEGACY_MIGRATION_PLAN_FILE:-none}" >> "$VALIDATION_REPORT_FILE"
		printf 'environment_snapshot_recorded=%s\n' "${LEGACY_SNAPSHOT_FILE:-none}" >> "$VALIDATION_REPORT_FILE"
	fi
}

write_login_banner() {
	log_step "Generating login banner"
	if ! is_root; then
		log_info "Skipping /etc/issue banner update for non-root execution"
		return 0
	fi
	local host_ip
	host_ip=$(hostname -I 2>/dev/null | awk '{print $1}') || host_ip="<your-server-ip>"
	cat > /etc/issue <<EOF
==========================================
  Welcome to Websoft9
  Console: http://${host_ip}:${CONSOLE_PORT}
==========================================
  OS: \s \v  (\r \m)
  Hostname: \n
  Time: \d \t
==========================================
\l
EOF
	chmod 644 /etc/issue
}

print_summary() {
	local elapsed
	elapsed=$(($(date +%s) - START_TIME))
	echo
	echo "============================================"
	echo "Complete"
	echo "============================================"
	echo "Environment: ${ENV_KIND}"
	echo "Mode:        ${MODE}"
	echo "Directory:   ${INSTALL_PATH}"
	[[ -n "$BACKUP_DIR" ]] && echo "Backup:      ${BACKUP_DIR}"
	[[ -n "$VALIDATION_REPORT_FILE" ]] && echo "Validation:  ${VALIDATION_REPORT_FILE}"
	echo "Log:         ${LOG_FILE}"
	echo "Time:        ${elapsed}s"
	echo "============================================"
}

run_install_flow() {
	prepare_modern_runtime_artifacts
	pull_target_image
	start_modern_runtime
	health_check || {
		log_error "Modern install health check failed"
		exit 1
	}
	write_runtime_validation_report
}

run_modern_upgrade_flow() {
	backup_modern_state
	prepare_modern_runtime_artifacts
	pull_target_image
	start_modern_runtime || {
		restore_modern_runtime
		log_error "Modern upgrade failed"
		exit 1
	}
	if ! health_check; then
		restore_modern_runtime
		log_error "Modern upgrade health check failed"
		exit 1
	fi
	write_runtime_validation_report
}

run_legacy_upgrade_flow() {
	backup_legacy_state
	validate_legacy_upgrade_context
	validate_legacy_backup_payload
	write_legacy_environment_snapshot
	prepare_modern_runtime_artifacts
	write_legacy_migration_plan
	pull_target_image
	migrate_legacy_assets
	stop_legacy_runtime
	start_modern_runtime || {
		restore_legacy_runtime
		log_error "Legacy migration failed during start"
		exit 1
	}
	if ! health_check; then
		restore_legacy_runtime
		log_error "Legacy migration health check failed"
		exit 1
	fi
	write_runtime_validation_report
}

lifecycle_parse_args() {
	while [[ $# -gt 0 ]]; do
		case "$1" in
			--mode) require_arg "$1" "${2:-}"; MODE="$2"; shift 2 ;;
			--check) CHECK_ONLY=true; shift ;;
			--version) require_arg "$1" "${2:-}"; VERSION="$2"; shift 2 ;;
			--channel) require_arg "$1" "${2:-}"; CHANNEL="$2"; shift 2 ;;
			--console_port|--port) require_arg "$1" "${2:-}"; CONSOLE_PORT="$2"; CONSOLE_PORT_SET=true; shift 2 ;;
			--app_http_gateway) require_arg "$1" "${2:-}"; APP_HTTP_GATEWAY="$2"; HTTP_GATEWAY_SET=true; shift 2 ;;
			--app_https_gateway) require_arg "$1" "${2:-}"; APP_HTTPS_GATEWAY="$2"; HTTPS_GATEWAY_SET=true; shift 2 ;;
			--path) require_arg "$1" "${2:-}"; INSTALL_PATH="$2"; INSTALL_PATH_SET=true; shift 2 ;;
			--legacy_path) require_arg "$1" "${2:-}"; LEGACY_PATH="$2"; shift 2 ;;
			--mirrors) require_arg "$1" "${2:-}"; MIRRORS="$2"; shift 2 ;;
			--proxy) require_arg "$1" "${2:-}"; PROXY="$2"; shift 2 ;;
			-h|--help) show_help ;;
			*) echo "Unknown option: $1. Use --help." >&2; exit 1 ;;
		esac
	done
}

execute_lifecycle_flow() {
	if [[ "$MODE" == "install" ]]; then
		run_install_flow
		return 0
	fi

	case "$ENV_KIND" in
		modern)
			run_modern_upgrade_flow
			;;
		legacy)
			run_legacy_upgrade_flow
			;;
		*)
			log_error "Unhandled environment type: ${ENV_KIND}"
			exit 1
			;;
	esac
}

lifecycle_main() {
	trap 'on_error ${LINENO}' ERR

	[[ -n "$PROXY" ]] && export http_proxy="$PROXY" https_proxy="$PROXY"

	init_logging
	detect_environment
	resolve_modern_install_path
	load_legacy_context
	resolve_mode
	validate_execution_permissions
	show_banner

	log_step "Checking system"
	ensure_supported_os
	check_disk
	check_target_ports
	assess_runtime_capabilities

	if $CHECK_ONLY; then
		echo
		echo "Environment: ${ENV_KIND}"
		echo "Mode:        ${MODE}"
		[[ -n "$LEGACY_INSTALL_PATH" ]] && echo "Legacy Path: ${LEGACY_INSTALL_PATH}"
		echo "Checks passed"
		return 0
	fi

	install_prereqs
	setup_docker
	execute_lifecycle_flow
	write_login_banner
	print_summary
}

lifecycle_parse_args "$@"
lifecycle_main
