#!/bin/bash
# install_docker.sh — Install Docker Engine + Docker Compose plugin
# Called by install.sh when Docker is absent; also published as a standalone artifact.
#
# Strategy:
#   1. Try the official get.docker.com script (with mirror fallbacks).
#   2. If the official script reports an unsupported distro, fall back to a
#      distro-specific repo-based installation.
#   3. Start and enable the Docker daemon.

set -o pipefail
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# ---------------------------------------------------------------------------
# Logging (matches Websoft9 format)
# ---------------------------------------------------------------------------
_w9_ts() { date +"%Y-%m-%d %H:%M:%S"; }
log_info()  { echo "[Websoft9][$(_w9_ts)][INFO ] $*"; }
log_warn()  { echo "[Websoft9][$(_w9_ts)][WARN ] $*" >&2; }
log_error() { echo "[Websoft9][$(_w9_ts)][ERROR] $*" >&2; }
log_step()  { echo "[Websoft9][$(_w9_ts)][STEP ] $*"; }

command_exists() { command -v "$@" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# Detect distro
# ---------------------------------------------------------------------------
detect_distro() {
  if [ -r /etc/os-release ]; then
    lsb_dist="$(. /etc/os-release && echo "${ID:-}" | tr '[:upper:]' '[:lower:]')"
  else
    lsb_dist="unknown"
  fi
  echo "$lsb_dist"
}

# ---------------------------------------------------------------------------
# Progress helper — print dots in background while a long operation runs
# Usage: _with_dots <pid> [label]
#   Kills the dot loop when the tracked pid exits.
# ---------------------------------------------------------------------------
_with_dots() {
  local pid="$1" label="${2:-working}"
  printf "[Websoft9] %s " "$label"
  while kill -0 "$pid" 2>/dev/null; do
    printf "."
    sleep 2
  done
  wait "$pid"  # collect exit code
  printf "\n"
  return $?
}

# ---------------------------------------------------------------------------
_download() {
  local url="$1" dest="$2" timeout="${3:-30}"
  if command_exists curl; then
    curl -fsSL --max-time "$timeout" -o "$dest" "$url" 2>/dev/null
  elif command_exists wget; then
    wget -q --timeout="$timeout" -O "$dest" "$url" 2>/dev/null
  else
    log_error "Neither curl nor wget found"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Download official get.docker.com script (with mirror fallbacks)
# ---------------------------------------------------------------------------
download_docker_script() {
  local urls=(
    "https://get.docker.com"
    "https://proxy.websoft9.com/?url=https://get.docker.com"
  )
  local dest="get-docker.sh"
  local attempt max_attempts=5

  for url in "${urls[@]}"; do
    log_info "Downloading Docker install script from: $url"
    for attempt in $(seq 1 "$max_attempts"); do
      log_info "Attempt $attempt/$max_attempts ..."
      # Run download in background so we can show dots
      (_download "$url" "$dest" 30) &
      _with_dots $! "downloading" || true
      if [ -s "$dest" ]; then
        log_info "Download succeeded"
        return 0
      fi
      log_warn "Attempt $attempt/$max_attempts failed, retrying..."
      sleep 2
    done
    log_warn "All attempts failed for: $url"
  done

  log_error "Could not download the Docker install script from any source"
  return 1
}

# ---------------------------------------------------------------------------
# Start and enable Docker daemon
# ---------------------------------------------------------------------------
_start_docker() {
  log_step "Starting and enabling Docker daemon"
  if systemctl start docker && systemctl enable docker >/dev/null 2>&1; then
    if command_exists docker && docker compose version >/dev/null 2>&1; then
      log_info "Docker and Docker Compose are ready"
      return 0
    fi
    log_error "Docker or Docker Compose verification failed after start"
    return 1
  fi
  log_error "Failed to start Docker daemon"
  return 1
}

# ---------------------------------------------------------------------------
# Quick connectivity check — returns 0 if the URL is reachable within N seconds
# ---------------------------------------------------------------------------
_url_reachable() {
  local url="$1" timeout="${2:-2}"
  if command_exists curl; then
    curl -fsS --max-time "$timeout" --connect-timeout "$timeout" "$url" >/dev/null 2>&1
  elif command_exists wget; then
    wget -q --timeout="$timeout" --spider "$url" 2>/dev/null
  else
    return 1
  fi
}

# Decide repo ordering: China mirrors first if docker.com is slow/unreachable
_build_repo_list() {
  local dist="$1"
  local docker_com="https://download.docker.com/linux"
  local aliyun="https://mirrors.aliyun.com/docker-ce/linux"
  local azure_cn="https://mirror.azure.cn/docker-ce/linux"

  # Quick probe (2s) — if docker.com responds, prefer it first (faster overseas)
  if _url_reachable "$docker_com" 2; then
    log_info "Docker official repo is reachable, preferring it"
    printf '%s\n' "$docker_com" "$aliyun" "$azure_cn"
  else
    log_info "Docker official repo is slow/unreachable, using mirrors first"
    printf '%s\n' "$aliyun" "$azure_cn" "$docker_com"
  fi
}

# ---------------------------------------------------------------------------
# Repo-based installation helper
# ---------------------------------------------------------------------------
_install_from_repo() {
  local repo="$1"
  log_info "Adding Docker repo: $repo"

  if command_exists dnf5; then
    dnf -y -q install dnf-plugins-core >/dev/null 2>&1 || true
    dnf5 config-manager addrepo --save-filename=docker-ce.repo --from-repofile="$repo" >/dev/null 2>&1
    dnf makecache -q >/dev/null 2>&1 || true
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  elif command_exists dnf; then
    dnf -y -q install dnf-plugins-core >/dev/null 2>&1 || true
    dnf config-manager --add-repo "$repo" >/dev/null 2>&1
    dnf makecache -q >/dev/null 2>&1 || true
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    yum -y -q install yum-utils >/dev/null 2>&1 || true
    yum-config-manager --add-repo "$repo" >/dev/null 2>&1
    yum makecache -q >/dev/null 2>&1 || true
    yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi
}

# ---------------------------------------------------------------------------
# Custom distro-specific installation (fallback)
# ---------------------------------------------------------------------------
install_docker_custom() {
  local lsb_dist="${1:-$(detect_distro)}"
  log_step "Custom repo-based Docker installation for: $lsb_dist"

  # Build repo list ordered by network reachability (domestic vs overseas)
  local repos_base=()
  mapfile -t repos_base < <(_build_repo_list "$lsb_dist")

  # Amazon Linux
  if [ "$lsb_dist" = "amzn" ]; then
    log_info "Detected Amazon Linux, using yum"
    yum makecache -q >/dev/null 2>&1 || true
    yum install -y docker
    mkdir -p /usr/local/lib/docker/cli-plugins/
    log_info "Downloading Docker Compose plugin for Amazon Linux..."
    _download \
      "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
      "/usr/local/lib/docker/cli-plugins/docker-compose" 120 \
      || log_warn "Compose plugin download failed; install manually if needed"
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
    _start_docker && return 0
    return 1
  fi

  # OpenEuler
  if [ "$lsb_dist" = "openeuler" ]; then
    log_info "Detected OpenEuler, using Aliyun mirror"
    dnf update -y -q >/dev/null 2>&1 || true
    dnf -y install dnf-plugins-core >/dev/null 2>&1 || true
    dnf config-manager --add-repo=https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo >/dev/null 2>&1
    sed -i 's+$releasever+8+' /etc/yum.repos.d/docker-ce.repo 2>/dev/null || true
    dnf makecache -q >/dev/null 2>&1 || true
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    _start_docker && return 0
    return 1
  fi

  # RPM-based (RHEL, CentOS, Rocky, Fedora, Oracle Linux ...)
  if command_exists dnf5 || command_exists dnf || command_exists yum; then
    # Oracle Linux 7 special case
    if [ "$lsb_dist" = "ol" ] && grep -q 'VERSION_ID="7' /etc/os-release 2>/dev/null; then
      log_info "Detected Oracle Linux 7, enabling preview repo"
      yum install -y oraclelinux-developer-release-el7
      yum-config-manager --enable ol7_preview >/dev/null 2>&1
    fi

    dnf remove -y podman 2>/dev/null || yum remove -y podman 2>/dev/null || true

    local repo dist
    for dist in "$lsb_dist" rhel centos; do
      for base in "${repos_base[@]}"; do
        repo="${base}/${dist}/docker-ce.repo"
        if _install_from_repo "$repo"; then
          _start_docker && return 0
          return 1
        fi
      done
    done

    log_error "All repo-based install attempts failed for: $lsb_dist"
    return 1
  fi

  # Debian / Ubuntu (APT)
  if command_exists apt || command_exists apt-get; then
    local repo base
    for base in "${repos_base[@]}"; do
      repo="${base}/ubuntu"
      log_info "Trying APT repo: $repo"
      apt-get update -qq >/dev/null 2>&1 || true
      apt-get install -y -q ca-certificates curl >/dev/null 2>&1
      install -m 0755 -d /etc/apt/keyrings
      if _download "${repo}/gpg" /etc/apt/keyrings/docker.asc 30; then
        chmod a+r /etc/apt/keyrings/docker.asc
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] $repo \
          $(. /etc/os-release && echo "${VERSION_CODENAME:-stable}") stable" | \
          tee /etc/apt/sources.list.d/docker.list >/dev/null
        apt-get update -qq >/dev/null 2>&1 || true
        if apt-get install -y docker-ce docker-ce-cli containerd.io \
             docker-buildx-plugin docker-compose-plugin; then
          _start_docker && return 0
          return 1
        fi
      fi
      log_warn "APT install failed from $repo, trying next"
    done
    log_error "APT-based Docker installation failed"
    return 1
  fi

  log_error "Unsupported distribution: $lsb_dist"
  return 1
}

# ---------------------------------------------------------------------------
# Official script install (primary path)
# ---------------------------------------------------------------------------
install_docker_official() {
  local mirrors=("" "--mirror Aliyun" "--mirror AzureChinaCloud")
  local install_timeout=600
  local lsb_dist
  lsb_dist="$(detect_distro)"

  for mirror in "${mirrors[@]}"; do
    local cmd="sh get-docker.sh${mirror:+ $mirror}"
    log_step "Running: $cmd  (up to ${install_timeout}s)"

    # Run in background, pipe output to a temp log AND a small exit-code file
    local tmplog exit_file exit_code
    tmplog="$(mktemp)"
    exit_file="$(mktemp)"
    (
      timeout "$install_timeout" sh -c "$cmd"
      echo $? > "$exit_file"
    ) 2>&1 | tee "$tmplog" &

    _with_dots $! "Installing Docker"

    exit_code="$(cat "$exit_file" 2>/dev/null || echo unknown)"
    rm -f "$exit_file"

    if [ "$exit_code" = "124" ] || [ "$exit_code" = "unknown" ]; then
      rm -f "$tmplog"
      log_warn "Timed out after ${install_timeout}s, trying next mirror"
      continue
    fi

    if grep -q "ERROR: Unsupported distribution" "$tmplog" 2>/dev/null; then
      local unsupported_dist
      unsupported_dist="$(grep "ERROR: Unsupported distribution" "$tmplog" | awk -F"'" '{print $2}')"
      rm -f "$tmplog"
      log_warn "Distribution '${unsupported_dist:-$lsb_dist}' not supported by official script; switching to custom install"
      install_docker_custom "${unsupported_dist:-$lsb_dist}"
      return $?
    fi

    rm -f "$tmplog"

    if command_exists docker && docker compose version >/dev/null 2>&1; then
      log_info "Docker installation succeeded via official script"
      _start_docker
      return $?
    fi

    log_warn "Official script finished but Docker is not available; trying next mirror"
  done

  log_warn "Official script exhausted all mirrors, falling back to custom installation"
  install_docker_custom "$lsb_dist"
  return $?
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
log_step "Installing Docker Engine"

if command_exists docker && docker compose version >/dev/null 2>&1; then
  log_info "Docker is already installed: $(docker --version)"
  exit 0
fi

# Strategy:
#   1. Primary: download and run the official get.docker.com script.
#      The script supports --mirror Aliyun / --mirror AzureChinaCloud, so
#      overseas vs domestic connectivity is handled by retrying with mirrors.
#   2. Fallback: if the official script reports an unsupported distro, or
#      exhausts all mirrors, switch to distro-specific repo-based installation
#      (install_docker_custom) as a last resort.

lsb_dist="$(detect_distro)"
log_info "Detected distribution: $lsb_dist"

log_step "Trying official Docker install script (with mirror fallbacks)"
if download_docker_script; then
  install_docker_official
  exit $?
fi

log_warn "Could not download official script, falling back to custom repo-based install"
if [ "$lsb_dist" != "unknown" ]; then
  if install_docker_custom "$lsb_dist"; then
    log_info "Docker installed successfully via custom repo path"
    exit 0
  fi
  log_error "All Docker installation methods failed"
  exit 1
fi

log_error "Unsupported distribution and official script unavailable"
exit 1
