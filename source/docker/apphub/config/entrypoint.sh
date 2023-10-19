#!/bin/bash

set -e

try_times=3

# start by supervisord
/usr/bin/supervisord
# debug
supervisorctl start apphub

# set git user and email
for ((i=0; i<$try_times; i++)); do
    set +e
    username=$(apphub getconfig --section gitea --key user_name) 
    email=$(apphub getconfig --section gitea --key email)
    set -e
    if [ -n "$username" ] && [ -n "$email" ]; then
        break
    fi
    echo "Command failed, retrying..."
    sleep 3
done

echo $username
echo $email

if [[ -n "$username" ]]; then
    git config --global user.name "$username"
else
    echo "username is null"
    exit 1
fi

regex="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
if [[ $email =~ $regex ]]; then
    git config --global user.email "$email"
else
    echo "Not have correct email"
    exit 1
fi

tail -f /dev/null