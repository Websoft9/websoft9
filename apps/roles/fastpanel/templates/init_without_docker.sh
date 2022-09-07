#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

newpassword=$1
echo $newpassword |passwd --stdin fastuser

internal_ip=$(ip addr show dev eth0|grep inet |grep eth0|cut -d/ -f1|cut -d" " -f6)
sed -i '/$internal_ip/d' /etc/nginx/conf.d/parking.conf

old_ip=$(cat /etc/nginx/conf.d/parking.conf |grep default_server|grep ssl |cut -d: -f1|cut -d" " -f2)
sed -i "s/$old_ip/$internal_ip/g" /etc/nginx/conf.d/parking.conf
systemctl restart nginx

