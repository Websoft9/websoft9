#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/stackhub/issues"' ERR

# Define environments
install_path="/data"
urls="https://w9artifact.blob.core.windows.net/release/websoft9"
if [[ "$1" == "dev" ]]; then
    echo "update by dev artifacts"
    urls="https://w9artifact.blob.core.windows.net/dev/websoft9"
fi

# Install runtime
curl https://websoft9.github.io/websoft9/install/install_tools.sh | bash
curl https://websoft9.github.io/websoft9/install/install_docker.sh | bash


# Install Cockpit and plugins
curl https://websoft9.github.io/websoft9/install/install_cockpit.sh | bash
curl https://websoft9.github.io/websoft9/install/install_plugins.sh | bash


# Install backend service
wget $urls/websoft9.latest && unzip websoft9.latest  $install_path
cd websoft9/docker
sudo docker network create websoft9
sudo docker compose -p websoft9 up -d

# Install Systemd service
