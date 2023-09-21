#!/bin/bash

# check 
check_file_exists() {
    file_path=$1
    max_attempts=$2

    for ((i=1; i<=max_attempts; i++))
    do
        if [ -f "$file_path" ]; then
            echo "$file_path exists"
            break
        else
            echo "$file_path is not exists, wait a moment.."
        fi
        sleep 1
        if ((i==max_attempts)); then
            echo "$file_path is not exists, app may be work normally."
            break
        fi
    done
}

check_file_exists "/websoft9/credentials/proxy" 1
check_file_exists "/websoft9/credentials/deployment" 1
check_file_exists "/websoft9/credentials/git" 1

# start by supervisord
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null