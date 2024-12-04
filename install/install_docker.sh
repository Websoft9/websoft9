#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# Download docker install script
download_docker_script() {
  local urls=("https://get.docker.com" "https://getdocker.websoft9.com")
  local output="get-docker.sh"
  local retries=10
  local timeout=5

  download_with_tool() {
    local tool=$1
    local url=$2
    local count=0
    until [ $count -ge $retries ]; do
      count=$((count+1))
      echo "[Websoft9] - Attempting to download official Docker install script from: $url using $tool (attempt $count of $retries)"
      if [ "$tool" = "curl" ]; then
        curl -fsSL --max-time $timeout $url -o $output
      else
        wget --timeout=$timeout -O $output $url
      fi
      if verify_download; then
        echo "[Websoft9] - Download official Docker install script succeeded from: $url using $tool"
        return 0
      fi
      sleep 1
    done
    echo "[Websoft9] - Download official Docker install script failed from: $url using $tool after $retries attempts"
    return 1
  }

  verify_download() {
    if [ -f "$output" ] && [ -s "$output" ]; then
      echo "[Websoft9] - Verification official Docker install script succeeded: $output"
      return 0
    else
      echo "[Websoft9] - Verification failed: $output is missing or empty"
      return 1
    fi
  }

  for url in "${urls[@]}"; do
    download_with_tool "curl" $url && break
  done

  if [ $? -ne 0 ]; then
    for url in "${urls[@]}"; do
      download_with_tool "wget" $url && break
    done
  fi

  if [ $? -ne 0 ]; then
    echo "[Websoft9] - Download failed after $retries attempts, please check your network connection."
    exit 1
  fi
}

# install docker by custom
install_docker_custom() {
  if [ -n "$1" ]; then
    lsb_dist=$(echo "$1" | tr '[:upper:]' '[:lower:]')
  else
    if [ -r /etc/os-release ]; then
      lsb_dist="$(. /etc/os-release && echo "$ID" | tr '[:upper:]' '[:lower:]')"
    else
      echo "[Websoft9] - Unable to determine distribution. Exiting."
      exit 1
    fi
  fi

  echo "[Websoft9] - Beginning custom Docker installation for: $lsb_dist"

  local repos_base=("https://download.docker.com/linux" "https://mirrors.aliyun.com/docker-ce/linux" "https://mirror.azure.cn/docker-ce/linux")
  local repos

  install_docker_from_repo() {
    local repo=$1
    if command_exists dnf5; then
      echo "[Websoft9] - Using dnf5 package manager for Docker installation from repo: $repo."
      sudo dnf -y -q install dnf-plugins-core
      sudo dnf5 config-manager addrepo --save-filename=docker-ce.repo --from-repofile=$repo
      sudo dnf makecache
      package_manager="dnf5"
    elif command_exists dnf; then
      echo "[Websoft9] - Using dnf package manager for Docker installation from repo: $repo."
      sudo dnf -y -q install dnf-plugins-core
      sudo dnf config-manager --add-repo $repo
      sudo dnf makecache
      package_manager="dnf"
    else
      echo "[Websoft9] - Using yum package manager for Docker installation from repo: $repo."
      sudo yum -y -q install yum-utils
      sudo yum-config-manager --add-repo $repo
      sudo yum makecache
      package_manager="yum"
    fi
    sudo $package_manager install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  }

  if command_exists dnf5 || command_exists dnf || command_exists yum; then
    if [ "$lsb_dist" = "amzn" ]; then
      sudo yum makecache
      sudo yum install -y docker 
      sudo mkdir -p /usr/local/lib/docker/cli-plugins/
      sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
      sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    else
      repos=("${repos_base[@]/%//${lsb_dist}/docker-ce.repo}")
      sudo dnf remove -y podman || sudo yum remove -y podman

      for repo in "${repos[@]}"; do
        install_docker_from_repo $repo && break
      done

      if [ $? -ne 0 ]; then
        echo "[Websoft9] - Installation failed with ${lsb_dist} repo, retrying with rhel and centos repos."
        for fallback_dist in "rhel" "centos"; do
          repos=("${repos_base[@]/%//${fallback_dist}/docker-ce.repo}")
          for repo in "${repos[@]}"; do
            install_docker_from_repo $repo && break 2
          done
        done
      fi
    fi
  elif command_exists apt; then
    repos=("${repos_base[@]/%//ubuntu}")
    for repo in "${repos[@]}"; do
      sudo apt-get update
      sudo apt-get install ca-certificates curl
      sudo install -m 0755 -d /etc/apt/keyrings
      sudo curl -fsSL $repo/gpg -o /etc/apt/keyrings/docker.asc
      sudo chmod a+r /etc/apt/keyrings/docker.asc

      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] $repo \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

      sudo apt-get update
      if sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
        break
      fi
    done
  else
    echo "[Websoft9] - Unsupported system distribution: $1. Exiting."
    exit 1
  fi

  if sudo systemctl start docker && sudo systemctl enable docker; then
    if command_exists docker && docker compose version >/dev/null 2>&1; then
        echo "[Websoft9] - Docker and Docker Compose installation verified successfully."
        return 0
    else
        echo "[Websoft9] - Docker or Docker Compose installation verification failed."
        exit 1
    fi
  else
    echo "[Websoft9] - Failed to start Docker."
    return 1
  fi
}

# Install docker by official script
install_docker_official() {
  # define install command parameters
  install_params=("" "--mirror Aliyun" "--mirror AzureChinaCloud")
  install_timeout=300  # set timeout for each install attempt in seconds
  
  for param in "${install_params[@]}"; do
    cmd="sh get-docker.sh $param"
    echo "[Websoft9] - Attempting to install Docker with command: $cmd"
    output=$(timeout $install_timeout $cmd 2>&1)
    echo "$output"
    if echo "$output" | grep -q "ERROR: Unsupported distribution"; then
      lsb_dist=$(echo "$output" | grep "ERROR: Unsupported distribution" | awk -F"'" '{print $2}')
      echo "[Websoft9] - Detected unsupported distribution: $lsb_dist. Executing custom operation."
      install_docker_custom "$lsb_dist"
      exit 1
    elif echo "$output" | grep -q "ERROR"; then
      echo "[Websoft9] - Docker installation failed with command: $cmd"
      install_docker_custom "$lsb_dist"
      exit 1
    elif command_exists docker && docker compose version >/dev/null 2>&1; then
      echo "[Websoft9] - Docker installation succeeded with command: $cmd"
      return 0
    elif echo "$output" | grep -q "timeout"; then
      echo "[Websoft9] - Docker installation attempt timed out with command: $cmd. Trying next mirror."
    fi
  done
  
  echo "[Websoft9] - Docker installation failed after use official script. Attempting custom installation."
  install_docker_custom "$lsb_dist"
  exit 1
}

command_exists() {
	command -v "$@" > /dev/null 2>&1
}


# download docker install script
download_docker_script

# install docker
install_docker_official