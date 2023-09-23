#!/bin/bash

set -e

trap "sleep 1; continue" ERR

try_times=30
counter=1
portainer_username="admin"

copy_credential() {
    source_container=$1
    source_path=$2
    destination_container=$3
    destination_path=$4

    if docker exec "$destination_container" [ -f "$destination_path" ]; then
        printf "%s already exists\n" "$destination_path"
    else
        temp_file=$(mktemp)
        docker cp "$source_container:$source_path" "$temp_file"

        # Check if temp_file is JSON format
        if jq -e . >/dev/null 2>&1 <<< "$(cat "$temp_file")"; then
            # If it is JSON format, use it directly
            docker cp "$temp_file" "$destination_container:$destination_path"
        else
            # If it is not JSON format, get the content and convert it to JSON
            content=$(cat "$temp_file")
            json="{\"username\":\"$portainer_username\",\"password\":\"$content\"}"
            echo "$json" > "$temp_file"
            docker cp "$temp_file" "$destination_container:$destination_path"
        fi

        rm -f "$temp_file"
    fi
}

while true; do
    set +e

    printf "Try to get credentials for %d times\n" "$counter"

    copy_credential "websoft9-git" "/var/websoft9/credential" "websoft9-apphub" "/websoft9/credentials/credential_git"
    copy_credential "websoft9-deployment" "/var/websoft9/credential" "websoft9-apphub" "/websoft9/credentials/credential_deployment"
    copy_credential "websoft9-proxy" "/var/websoft9/credential" "websoft9-apphub" "/websoft9/credentials/credential_proxy"

    if docker exec "websoft9-apphub" [ -f "/websoft9/credentials/credential_git" ] && \
       docker exec "websoft9-apphub" [ -f "/websoft9/credentials/credential_deployment" ] && \
       docker exec "websoft9-apphub" [ -f "/websoft9/credentials/credential_proxy" ]; then
        break
    else
        if [ $counter -gt $try_times ]; then
            printf "Systemd cannot get all credentials after executing %d times\n" "$try_times"
            break
        fi
    fi

    sleep 3
    set -e

    counter=$((counter + 1))
done

tail -f /dev/null