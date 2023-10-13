#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
clear

# Check if user is root
[ $(id -u) != "0" ] && { echo "Error: You must be root to run this script, please use 'sudo su -' command to change root"; exit 1; }

version(){
    echo "version: 0.1"
    echo "updated date: 2019-12-30"
}

Show_Help(){
    version
    echo "Usage: $0 command ...[parameters]...
    --help, -h           Show this help message
    --version, -v        Show version info
    "
}

echo "Pre-installation is starting, please wait for 1-3 minutes..."

if command -v yum > /dev/null; then
  sudo yum install -y epel-release 1>/dev/null 2>&1
  sudo yum install yum-utils git python python3 -y 1>/dev/null 2>&1
fi

if command -v apt > /dev/null; then
  sudo apt-get install git python python3 git -y 1>/dev/null 2>&1
  sudo apt install software-properties-common -y 1>/dev/null 2>&1
fi

sudo echo "Pre-installation has beend completed"
