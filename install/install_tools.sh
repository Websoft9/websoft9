#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

echo "Starting InstallTools..."


InstallTools(){

echo "Prepare to install Tools ..."

#!/bin/bash

dnf --version >/dev/null 2>&1 || yum --version >/dev/null 2>&1 || apt --version >/dev/null 2>&1

if [ $? -eq 0 ]; then
    dnf install git curl wget yum-utils jq bc unzip -y
elif [ $? -eq 0 ]; then
    yum install git curl wget yum-utils jq bc unzip -y
elif [ $? -eq 0 ]; then
    while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
    done
    sudo apt update -y 1>/dev/null 2>&1
    apt install curl wget yum-utils jq bc unzip -y --assume-yes
else
    echo "None of the required package managers are installed."
fi

}

InstallTools