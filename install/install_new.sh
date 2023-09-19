#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


# Define global vars
export http_port=80
export https_port=443
export cockpit_port=9000
export install_path="/data/websoft9"
export urls="https://w9artifact.blob.core.windows.net/release/websoft9"
if [[ "$1" == "dev" ]]; then
    echo "update by dev artifact"
    export urls="https://w9artifact.blob.core.windows.net/dev/websoft9"
fi

# Install runtime
bash install_tools.sh
bash install_docker.sh

# Install Cockpit and plugins
bash install_cockpit.sh
bash install_plugins.sh

# Install backend services
cd $install_path/docker
sudo docker network create websoft9
sudo docker compose -p websoft9 up -d

# Install Systemd service
cp $install_path/systemd/websoft9.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9