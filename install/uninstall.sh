#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH

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
    sudo systemctl disable cockpit.socket cockpit
    
    dnf --version >/dev/null 2>&1
    dnf_status=$?

    yum --version >/dev/null 2>&1
    yum_status=$?

    apt --version >/dev/null 2>&1
    apt_status=$?

    if [ $dnf_status -eq 0 ]; then
        for pkg in $cockpit_packages
        do
            echo "Uninstalling $pkg"
            sudo dnf remove -y "$pkg" > /dev/null || echo "$pkg failed to uninstall"
        done
    elif [ $yum_status -eq 0 ]; then
        for pkg in $cockpit_packages
        do
            echo "Uninstalling $pkg"
            sudo yum remove -y "$pkg" > /dev/null || echo "$pkg failed to uninstall"
        done
    elif [ $apt_status -eq 0 ]; then
        export DEBIAN_FRONTEND=noninteractive
        for pkg in $cockpit_packages
        do
            echo "Uninstalling $pkg"
            sudo apt-get remove -y "$pkg" > /dev/null || echo "$pkg failed to uninstall"
        done
    else
        echo "Neither apt,dnf nor yum found. Please install one of them and try again."
    end

    sudo rm -rf /etc/cockpit/*
}

remove_files() {
    echo -e "\n---Remove files---"
    sudo rm -rf $install_path/* $systemd_path/* $cockpit_plugin_path/*
}

remove_cockpit
remove_files

echo -e "\nCongratulations, Websoft9 uninstall is complete!"