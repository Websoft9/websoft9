#!/bin/bash

set -e

trap "sleep 1; continue" ERR

while true; do
    set +e
    docker cp websoft9-git:/var/websoft9/credential /data/websoft9/credential_git
    docker cp /data/websoft9/credential_git websoft9-apphub:/websoft9/credentials
    
    docker cp websoft9-deployment:/var/websoft9/credential /data/websoft9/credential_deployment
    content=$(cat /data/websoft9/credential_deployment)
    username="admin"
    password=$(echo "$content" | awk -F':' '{print $2}')
    json="{\"username\":\"$username\",\"password\":\"$password\"}"
    echo "$json" > /data/websoft9/credential_deployment
    docker cp /data/websoft9/credential_deployment websoft9-apphub:/websoft9/credentials
    
    docker cp websoft9-proxy:/var/websoft9/credential /data/websoft9/credential_proxy
    docker cp /data/websoft9/credential_proxy websoft9-apphub:/websoft9/credentials
    set -e
    sleep 3
done