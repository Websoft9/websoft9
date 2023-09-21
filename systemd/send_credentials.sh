#!/bin/bash

set -e

trap "sleep 1; continue" ERR

counter=1
while true; do
    
    set +e
    
    echo Try to get credentia for $counter times
    if [ -f "/data/websoft9/credential_git" ]; then
        echo "/data/websoft9/credential_git is exist"
    else
        echo "copy git credential"
        docker cp websoft9-git:/var/websoft9/credential /data/websoft9/credential_git
        docker cp /data/websoft9/credential_git websoft9-apphub:/websoft9/credentials
    fi

    if [ -f "/data/websoft9/credential_deployment" ]; then
        echo "/data/websoft9/credential_deployment is exist"
    else
        echo "copy deployment credential"
        docker cp websoft9-deployment:/var/websoft9/credential /data/websoft9/credential_deployment
        content=$(cat /data/websoft9/credential_deployment)
        username="admin"
        json="{\"username\":\"$username\",\"password\":\"$content\"}"
        echo "$json" > /data/websoft9/credential_deployment
        docker cp /data/websoft9/credential_deployment websoft9-apphub:/websoft9/credentials
    fi

    if [ -f "/data/websoft9/credential_proxy" ]; then
        echo "/data/websoft9/credential_proxy is exist"
    else
        echo "copy nginx credential ..."
        docker cp websoft9-proxy:/var/websoft9/credential /data/websoft9/credential_proxy
        docker cp /data/websoft9/credential_proxy websoft9-apphub:/websoft9/credentials
    fi

    if [ -f "/data/websoft9/credential_git" ] && [ -f "/data/websoft9/credential_deployment" ] && [ -f "/data/websoft9/credential_proxy" ]; then
        break
    else
        if [ $counter -gt 30 ]; then
            echo "Systemd can not get all credentials by excuting 30 times"
            break
        fi
    fi

    set -e
    sleep 3
done
tail -f /dev/null