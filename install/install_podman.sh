#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# This script is on development, can not use now
# to do


Remove_Podman(){
    echo "$echo_prefix_docker Try to remove Podman"
    podman pod stop --all
    # Remove Podman and its dependencies
    if [ -x "$(command -v dnf)" ]; then
        sudo dnf remove podman -y
    elif [ -x "$(command -v apt)" ]; then
        sudo apt remove podman -y
    elif [ -x "$(command -v zypper)" ]; then
        sudo zypper remove podman -y
    elif [ -x "$(command -v pacman)" ]; then
        sudo pacman -Rs podman --noconfirm
    else
        echo "Unable to find a suitable package manager to remove Podman."
        exit 1
    fi
    echo "Podman has been stopped and removed."

}