#!/bin/bash

PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
set -e
trap "sleep 1; continue" ERR
try_times=20
counter=1

deployment_username="admin"
credential_path="/var/websoft9/credential"
containers=("websoft9-git" "websoft9-deployment" "websoft9-proxy")

for container in ${containers[@]}; do
    temp_file=$(mktemp)
    echo "Copying /var/websoft9/credential from $container to $temp_file"
    docker cp $container:$credential_path $temp_file
    # Check if temp_file is JSON format
    if jq -e . >/dev/null 2>&1 <<< "$(cat "$temp_file")"; then
        # If it is JSON format, use it directly
        username=$(jq -r '.username' $temp_file)
		password=$(jq -r '.password' $temp_file)
    else
        # If it is not JSON format, get the content and convert it to JSON
        content=$(cat "$temp_file")
        username="$deployment_username"
        password="$content"
    fi

    rm -f "$temp_file"
done

get_credential() {

	# 设置参数的默认值
	source_container=
	source_path="/var/websoft9/credential"
	destination_container="websoft9-apphub"
	destination_path="/websoft9/credentials/credential_git"

	# 获取参数值
	while [[ $# -gt 0 ]]; do
		case $1 in
			--sc)
				source_container="$2"
				shift 2
				;;
			--sp)
				source_path="$2"
				shift 2
				;;
			--dc)
				destination_container="$2"
				shift 2
				;;
			--dp)
				destination_path="$2"
				shift 2
				;;
			*)
				shift
				;;
		esac
	done
    
	echo "Your installation parameters are as follows: "
	echo "--sc: $source_container"
	echo "--sp: $source_path"
	echo "--dc: $destination_container"
	echo "--dp: $destination_path"

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

}

while true; do

    sleep 3
    set +e
    echo  "Try to get credentials for %d times\n" "$counter" >> /tmp/copy

    copy_credential  --sc "websoft9-git" --sp $credential_path --dc $apphub_container_name --dp "/websoft9/credentials/credential_git"
    copy_credential  --sc "websoft9-deployment" --sp $credential_path --dc $apphub_container_name --dp "/websoft9/credentials/credential_deployment"
    copy_credential  --sc "websoft9-proxy" --sp $credential_path --dc $apphub_container_name --dp "/websoft9/credentials/credential_proxy"

    if docker exec "websoft9-apphub" [ -s "/websoft9/credentials/credential_git" ] && \
       docker exec "websoft9-apphub" [ -s "/websoft9/credentials/credential_deployment" ] && \
       docker exec "websoft9-apphub" [ -s "/websoft9/credentials/credential_proxy" ]; then
        break
    else
        if [ $counter -gt $try_times ]; then
            printf "Systemd cannot get all credentials after executing %d times\n" "$try_times"
            break
        fi
    fi

    set -e

    counter=$((counter + 1))
done