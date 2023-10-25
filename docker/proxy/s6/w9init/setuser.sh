#!/bin/bash

set +e 
username="help@websoft9.com"
password=$(openssl rand -base64 16 | tr -d '/+' | cut -c1-16)
token=""
cred_path="/data/credential"
max_attempts=10

echo "Start to change nginxproxymanage users"
if [ -e "$cred_path" ]; then
  echo "File $cred_path exists. Exiting script."
  exit 0
fi

echo "create diretory"
mkdir -p "$(dirname "$cred_path")"

sleep 10
while [ -z "$token" ]; do
    sleep 5
    login_data=$(curl -X POST -H "Content-Type: application/json" -d '{"identity":"admin@example.com","scope":"user", "secret":"changeme"}' http://localhost:81/api/tokens)
    token=$(echo $login_data | jq -r '.token')
done

echo "Change username(email)"
for attempt in $(seq 1 $max_attempts); do
    response=$(curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"email": "'$username'", "nickname": "admin", "is_disabled": false, "roles": ["admin"]}'  http://localhost:81/api/users/1)
    if [ $? -eq 0 ]; then
        echo "Set username successful"
        break
    else
        echo "Set username failed, retrying..."
        sleep 5
        if [ $attempt -eq $max_attempts ]; then
            echo "Failed to set username after $max_attempts attempts. Exiting."
            exit 1
        fi
    fi
done

echo "Update password"
for attempt in $(seq 1 $max_attempts); do
    response=$(curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"type":"password","current":"changeme","secret":"'$password'"}'  http://localhost:81/api/users/1/auth)
    if [ $? -eq 0 ]; then
        echo "Set password successful"
        echo "Save to credential"
        json="{\"username\":\"$username\",\"password\":\"$password\"}"
        echo "$json" > "$cred_path"
        break
    else
        echo "Set password failed, retrying..."
        sleep 5
        if [ $attempt -eq $max_attempts ]; then
            echo "Failed to set password after $max_attempts attempts. Exiting."
            exit 1
        fi
    fi
done

set -e