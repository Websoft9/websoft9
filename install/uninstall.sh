#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


# Command-line options
# ==============================================================================
#
# --cockpit
# Use the --cockpit option to remove cockpit:
#
#  $ sudo sh install.sh --cockpit
#
# --files
# Use the  --files option remove files have installed:
#
#   $ sudo sh install.sh --cockpit
#
#
# ==============================================================================


install_path="/data/websoft9/source"
systemd_path="/opt/websoft9/systemd"
cockpit_plugin_path="/usr/share/cockpit"
cockpit_packages="cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-pcp cockpit-storaged cockpit-networkmanager cockpit-session-recording cockpit-doc cockpit-packagekit cockpit-sosreport"

echo -e "\n---Remove Websoft9 backend service containers---"
sudo docker compose -p websoft9 down -v

echo -e "\n---Remove Websoft9 systemd service---"
sudo systemctl disable websoft9
sudo systemctl stop websoft9
rm -rf /lib/systemd/system/websoft9.service



remove_cockpit() {
    echo -e "\n---Remove Cockpit---"
    sudo systemctl stop cockpit.socket cockpit
    for package in $cockpit_packages; do
        sudo pkcon remove $package  -y || true
    done
    sudo rm -rf /etc/cockpit/*
}

remove_files() {
    echo -e "\n---Remove files---"
    sudo rm -rf $install_path/* $systemd_path/* $cockpit_plugin_path/*
}

for arg in "$@"
do
    case $arg in
        --cockpit)
        remove_cockpit
        shift
        ;;
        --files)
        remove_files
        shift
        ;;
        *)
        echo "Unknown argument: $arg"
        exit 1
        ;;
    esac
done

echo -e "\nCongratulations, Websoft9 uninstall is complete!"