#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
new_password=$1
echo "init_without_docker.sh password=$new_password" >> /tmp/init_debug.txt
sudo su && cd /www/server/panel && python tools.py panel $new_password
