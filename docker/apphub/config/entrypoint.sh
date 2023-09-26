#!/bin/bash

# check credentials exists
check_file_exists() {
    file_path=$1
    max_attempts=$2

    for ((i=1; i<=max_attempts; i++))
    do
        if [ -f "$file_path" ]; then
            echo "$file_path exists"
            return 0
        else
            echo "$file_path is not exists, wait a moment.."
        fi
        sleep 1
        if ((i==max_attempts)); then
            echo "$file_path is not exists, app may be work normally."
            return 1
        fi
    done
}

set +e 
check_file_exists "/websoft9/credentials/credential_proxy" 1
check_file_exists "/websoft9/credentials/credential_deployment" 1
check_file_exists "/websoft9/credentials/credential_git" 1

# set git user and email
if [ $? -eq 0 ]; then
    username=$(jq -r '.username' /websoft9/credentials/credential_git)
    password=$(jq -r '.email' /websoft9/credentials/credential_git)
else
    echo "Git set with default value"
    username="websoft9"
    password="help@websoft9.com"
fi
git config --global user.name "$username"
git config --global user.email "$password"
set -e

internal_ip=$(ip addr show eth0 | awk '/inet /{split($2, a, "/"); print a[1]}')
nsenter -m -u -i -n -p -t 1 sh -c "sed -i '/websoft9-apphub/d' /etc/hosts"
nsenter -m -u -i -n -p -t 1 sh -c "echo $internal_ip websoft9-apphub>> /etc/hosts"

# start by supervisord
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null