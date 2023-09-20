#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH
export install_path="/data/websoft9"

chmod +x $install_path/systemd/send_credentials.sh
cp $install_path/systemd/websoft9.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9