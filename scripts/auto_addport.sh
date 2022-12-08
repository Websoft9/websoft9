#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

app_port=$(cat /data/apps/$1/.env |grep APP_HTTP_PORT |cut -d= -f2 |sed -n 1p)

while true 
do 
    app_port_lines=$(cat /tmp/port.txt |grep "$app_port" |wc -l)
    if [ "$app_port_lines" -gt 0 ];then
        app_port=`expr $app_port + 1`
    else
        echo $app_port >> /tmp/port.txt
        sed -i "s/APP_HTTP_PORT=.*/APP_HTTP_PORT=$app_port/g" /data/apps/$1/.env
        break
    fi
done
