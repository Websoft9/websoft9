#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

deployment_username="admin"
credential_path="/var/websoft9/credential"
containers=("websoft9-git" "websoft9-deployment" "websoft9-proxy")
max_retries=20

declare -A usernames passwords

set +e  # Ignore errors

for container in ${containers[@]}; do
    echo "Processing $container"
    success=false
    counter=0
    while [[ $success == false && $counter -lt $max_retries ]]; do
        temp_file=$(mktemp)
        echo "Attempt $((counter+1)) to copy $credential_path from $container to $temp_file"
        if docker cp $container:$credential_path $temp_file; then
            # Check if temp_file is JSON format
            if jq -e . >/dev/null 2>&1 <<< "$(cat "$temp_file")"; then
                # If it is JSON format, use it directly
                username=$(jq -r '.username' $temp_file)
                password=$(jq -r '.password' $temp_file)
                if [[ -n $username && -n $password ]]; then
                    usernames[$container]=$username
                    passwords[$container]=$password
                    success=true
                fi
            else
                # If it is not JSON format, get the content and convert it to JSON
                content=$(cat "$temp_file")
                username="$deployment_username"
                password="$content"
                if [[ -n $username && -n $password ]]; then
                    usernames[$container]=$username
                    passwords[$container]=$password
                    success=true
                fi
            fi
        fi
        rm -f "$temp_file"
        if [[ $success == false ]]; then
            echo "Waiting for 3 seconds before next attempt..."
            sleep 3
        fi
        ((counter++))
    done
    if [[ $success == true ]]; then
        echo "Successfully retrieved credentials for $container"
    else
        echo "Failed to retrieve credentials for $container after $max_retries attempts"
    fi
done

set -e  # Stop ignoring errors

# Set credentials to config.ini
for container in ${containers[@]}; do
    echo "$container:"
    echo "Username: ${usernames[$container]}"
    echo "Password: ${passwords[$container]}"
    docker exec -it websoft9-apphub apphub getconfig cockpit port
done