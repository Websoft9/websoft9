#!/bin/bash

set -e

trap "sleep 1; continue" ERR

while true; do
    set +e
    
    echo "copy git credential"
    docker cp websoft9-git:/var/websoft9/credential /data/websoft9/credential_git
    docker cp /data/websoft9/credential_git websoft9-apphub:/websoft9/credentials
    
    echo "copy deployment credential"
    docker cp websoft9-deployment:/var/websoft9/credential /data/websoft9/credential_deployment
    content=$(cat /data/websoft9/credential_deployment)
    username="admin"
    json="{\"username\":\"$username\",\"password\":\"$content\"}"
    echo "$json" > /data/websoft9/credential_deployment
    docker cp /data/websoft9/credential_deployment websoft9-apphub:/websoft9/credentials
    
    echo "wait nginx..."
    docker cp websoft9-proxy:/var/websoft9/credential /data/websoft9/credential_proxy
    docker cp /data/websoft9/credential_proxy websoft9-apphub:/websoft9/credentials
    set -e
    sleep 3
done