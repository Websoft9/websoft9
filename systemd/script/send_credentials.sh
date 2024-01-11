#!/bin/bash

# Websoft9 microservices container(git,deployment,proxy)  have credential info inside the container 
# send_credentials.sh: copy credential from these container, and save it into apphub by apphub cli, it will retry 20 times in every 3 seconds interval

PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
deployment_username="admin"
credentials=("/data/gitea/credential" "/data/credential" "/data/credential")
containers=("websoft9-git" "websoft9-deployment" "websoft9-proxy")
sections=("gitea" "portainer" "nginx_proxy_manager")
max_retries=20

declare -A usernames passwords

set +e  # Ignore errors

for i in ${!containers[@]}; do
    container=${containers[$i]}
    credential_path=${credentials[$i]}
    echo "Processing $container"
    success=false
    counter=0
    while [[ $success == false && $counter -lt $max_retries ]]; do
        temp_file=$(mktemp)
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

length=${#containers[@]}
for ((i=0; i<$length; i++)); do

    container=${containers[$i]}
    section=${sections[$i]}
    if [[ -n ${passwords[$container]} ]]; then
        echo "$container start to set password"
        docker exec -i websoft9-apphub apphub setconfig --section $section --key user_pwd --value ${passwords[$container]}
    else
        echo "Password for $container is not set or empty. Skipping..."
    fi
done
