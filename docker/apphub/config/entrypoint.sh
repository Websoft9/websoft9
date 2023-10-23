#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH

set -e

try_times=5

supervisord
supervisorctl start apphub

# set git user and email
for ((i=0; i<$try_times; i++)); do
    set +e
    username=$(apphub getconfig --section gitea --key user_name 2>/dev/null) 
    email=$(apphub getconfig --section gitea --key user_email 2>/dev/null)
    set -e
    if [ -n "$username" ] && [ -n "$email" ]; then
        break
    fi
    echo "Wait for service running, retrying..."
    sleep 3
done

if [[ -n "$username" ]]; then
    echo "git config --global user.name $username"
    git config --global user.name "$username"
else
    echo "username is null, git config username failed"
    exit 1
fi

regex="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
if [[ $email =~ $regex ]]; then
    echo "git config --global user.email $email"
    git config --global user.email "$email"
else
    echo "Not have correct email, git config email failed"
    exit 1
fi

create_apikey() {
    # 容器第一次启动时，不管apikey是否为空，调用apphub genkey
    if [ ! -f /websoft9/first_run ]; then
        echo "Create new apikey"
        apphub genkey
        touch /websoft9/first_run
    fi
    # apphub getkey 为空时，创建新的apikey
    if [ -z "$(apphub getkey)" ]; then
        echo "Create new apikey"
        apphub genkey
    fi
}

create_apikey

tail -f /var/log/supervisord.log