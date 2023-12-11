#!/bin/bash

set +e 

# Define the array
proxy_line=("proxy_set_header Upgrade \$http_upgrade;" "proxy_set_header Connection upgrade;")

# Define the file path
proxy_path="/etc/nginx/conf.d/include/proxy.conf"

# Get the length of the array
length=${#proxy_line[@]}

# Loop over the array and append each item to the file
for ((i=0; i<$length; i++)); do
    # Check if the line already exists in the file
    if ! grep -Fxq "${proxy_line[$i]}" $proxy_path; then
        # If the line does not exist in the file, append it
        echo "${proxy_line[$i]}" >> $proxy_path
    fi
done


set -e