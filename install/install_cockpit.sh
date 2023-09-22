#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


## Cockpit build at redhat family: https://copr.fedorainfracloud.org/coprs/g/cockpit/cockpit-preview/monitor/
## PackageKit: https://www.freedesktop.org/software/PackageKit/
## [apt show cockpit] or [apt install cockpit] show all additional packages

# Below vars from install.sh
# cockpit_port
# install_path

# $cockpit_port is define at install.sh
if [ -z "$cockpit_port" ]; then
  cockpit_port="9000"
fi

echo_prefix_cockpit=$'\n[Cockpit] - '
cockpit_packages="cockpit cockpit-pcp cockpit-sosreport"
cockpit_plugin_delete="apps,machines,selinux,subscriptions,kdump,updates,playground,packagekit"
menu_overrides_github_page_url="https://websoft9.github.io/websoft9/cockpit/menu_override"
cockpit_config_github_page_url="https://websoft9.github.io/websoft9/cockpit/cockpit.conf"
cockpit_menu_overrides=(networkmanager.override.json shell.override.json storaged.override.json systemd.override.json users.override.json)


Install_PackageKit(){
    echo "$echo_prefix_cockpit Try to install pkcon"
    if command -v pkcon &> /dev/null; then
        echo "pkcon is at you system"
    elif command -v yum &> /dev/null; then
        sudo yum install PackageKit
    elif command -v dnf &> /dev/null; then
        sudo dnf install PackageKit
    elif command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install packagekit
    else
        echo "PackageKit not found, Cockpit can not install"
        exit 1
    fi
}

Restart_Cockpit(){
    echo "$echo_prefix_cockpit Restart Cockpit"
    sudo systemctl daemon-reload
    sudo systemctl restart cockpit
}

Set_Firewall(){
  echo "$echo_prefix_cockpit Set firewall for cockpit access"
  if command -v firewall-cmd &> /dev/null; then
     echo "Set firewall for Cockpit..."
     sudo firewall-cmd --permanent --zone=public --add-service=cockpit
     sudo firewall-cmd --reload
  fi

  if [ -f /etc/selinux/config ]; then
     echo "Set Selinux for Cockpit..."
     sudo setenforce 0  1>/dev/null 2>&1
     sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  fi
}

Set_Cockpit(){
    echo "$echo_prefix_cockpit Set Cockpit for Websoft9"

    echo "Cockpit allowed root user ..." 
    echo "" > /etc/cockpit/disallowed-users

    echo "Set Cockpit config file..." 
    if [ -f "$install_path/cockpit/cockpit.conf" ]; then
        cp -f "$install_path/cockpit/cockpit.conf" /etc/cockpit/cockpit.conf
    else
        echo "Download config from URL"
        curl -sSL $cockpit_config_github_page_url | sudo tee /etc/cockpit/cockpit.conf > /dev/null
    fi

    echo "Change cockpit default port to $cockpit_port ..." 
    sudo sed -i "s/ListenStream=9090/ListenStream=$cockpit_port/" /lib/systemd/system/cockpit.socket
}

Download_Menu_Override(){
    for file in "${cockpit_menu_overrides[@]}"
        do

        echo "$menu_overrides_github_page_url/$file"

        curl -sSL "$menu_overrides_github_page_url/$file" | sudo tee /etc/cockpit/"$file" > /dev/null
        if [ $? -ne 0 ]; then
        echo "Failed to download files"
        exit 1
        fi

        done
}

Edit_Menu(){
    echo "$echo_prefix_cockpit Start to edit Cockpit origin Menu"
    if [ -f "$install_path/cockpit/cockpit.conf" ]; then
        cp -f "$install_path/cockpit/cockpit.conf" /etc/cockpit/cockpit.conf
    else
        echo "Download config file from URL..."
        curl -sSL $cockpit_config_github_page_url | sudo tee /etc/cockpit/cockpit.conf > /dev/null
    fi

    if test -d "$install_path/cockpit/menu_override"; then
        cp -r $install_path/cockpit/menu_override/* /etc/cockpit
    else
        echo "Download override files from URL..."
        Download_Menu_Override
    fi

    sudo rm -rf /usr/share/cockpit/{$cockpit_plugin_delete}
}

Upgrade_Cockpit(){
    echo "$echo_prefix_cockpit Prepare to upgrade Cockpit"
    output=$(sudo pkcon update $cockpit_packages -y 2>&1)
    if [ $? -ne 0 ]; then
    echo "Cockpit upgrade failed or not need upgrade..."
    else
    echo "$output"
    fi
}

Install_Cockpit(){
    
    sudo pkcon refresh > /dev/null
    sudo pkcon get-updates > /dev/null

    if systemctl is-active --quiet cockpit; then
        Upgrade_Cockpit
        Restart_Cockpit
    else
        echo "$echo_prefix_cockpit Prepare to install Cockpit" 
        export DEBIAN_FRONTEND=noninteractive
        sudo pkcon install $cockpit_packages -y
        Restart_Cockpit
    fi

    Set_Firewall
    Set_Cockpit
    Edit_Menu
    Restart_Cockpit
}


#### -------------- main() start here  -------------------  ####

Install_PackageKit
Install_Cockpit

# release package memory
sudo systemctl restart packagekit.service