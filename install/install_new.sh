#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


# Define vars
install_path="/data/websoft9"
urls="https://w9artifact.blob.core.windows.net/release/websoft9"
if [[ "$1" == "dev" ]]; then
    echo "update by dev artifact"
    urls="https://w9artifact.blob.core.windows.net/dev/websoft9"
fi

# Install runtime
bash install_tools.sh
bash install_docker.sh

# Install Cockpit and plugins
bash install_cockpit.sh
bash install_plugins.sh

# Install backend service
cd $install_path/docker
sudo docker network create websoft9
sudo docker compose -p websoft9 up -d

# Install Systemd service
cd $install_path/systemd
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9