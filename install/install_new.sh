#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH

# Define error_exit function
function error_exit {
  echo "$1" 1>&2
  exit 1
}

# Trap ERR signal and call error_exit function
trap 'error_exit "Please push issue to: https://github.com/Websoft9/stackhub/issues"' ERR

# Define vars
install_path="/data/websoft9"
urls="https://w9artifact.blob.core.windows.net/release/websoft9"
if [[ "$1" == "dev" ]]; then
    echo "update by dev artifact"
    urls="https://w9artifact.blob.core.windows.net/dev/websoft9"
fi

# Download and extract source code
wget $urls/websoft9.latest && unzip websoft9.latest  $install_path

# Install runtime
curl https://websoft9.github.io/websoft9/install/install_tools.sh | bash
curl https://websoft9.github.io/websoft9/install/install_docker.sh | bash

# Install Cockpit and plugins
curl https://websoft9.github.io/websoft9/install/install_cockpit.sh | bash
curl https://websoft9.github.io/websoft9/install/install_plugins.sh | bash

# Install backend service
cd $install_path/docker
sudo docker network create websoft9
sudo docker-compose -p websoft9 up -d

# Install Systemd service
cd $install_path/websoft9/systemd
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9