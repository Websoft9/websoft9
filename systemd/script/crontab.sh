#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

# monitor config.ini, make sure port is the same with cockpit.socket

cockpit_port=from config.ini
echo "Change cockpit default port to $cockpit_port ..." 
sudo sed -i "s/ListenStream=9090/ListenStream=$cockpit_port/" /lib/systemd/system/cockpit.socket



