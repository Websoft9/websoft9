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
        sleep 2
        if ((i==max_attempts)); then
            echo "$file_path is not exists, timeout."
            break
        fi
    done
}

check_file_exists "/websoft9/credentials/proxy" 10
check_file_exists "/websoft9/credentials/git" 10
check_file_exists "/websoft9/credentials/deployment" 10

# start by supervisord
/usr/local/bin/supervisord
supervisorctl start all
tail -f /dev/null