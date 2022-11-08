#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
new_password=$1
echo "init_without_docker.sh password=$new_password" >> /tmp/init_debug.txt
sudo sed -i "s/admin123/$new_password/g" /data/apps/bt/password.exp
expect /data/apps/bt/password.exp
