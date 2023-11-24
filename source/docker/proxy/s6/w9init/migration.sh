#!/bin/bash

set +e 

nginx_proxy(){

    current_time=$(date +%s)
    shadow_modified_time=$(stat -c %Y /etc/shadow)
    time_difference=$((current_time - shadow_modified_time))

    if [ ! -f /data/nginx/proxy_host/initproxy.conf ] || [ $time_difference -le 60 ]
    then
        cp /etc/initproxy.conf /data/nginx/proxy_host/
        echo "Update initproxy.conf to Nginx"
    else
        echo "Don't need to update initproxy.conf to Nginx"
    fi
    
}

nginx_proxy

set -e