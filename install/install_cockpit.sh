#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


## Cockpit build at redhat family: https://copr.fedorainfracloud.org/coprs/g/cockpit/cockpit-preview/monitor/
## PackageKit: https://www.freedesktop.org/software/PackageKit/
## [apt show cockpit] or [apt install cockpit] show all additional packages

# $cockpit_port is define at install.sh
if [ -z "$cockpit_port" ]; then
  cockpit_port="9000"
fi

cockpit_packages="cockpit cockpit-pcp cockpit-sosreport"
cockpit_plugin_delete="apps,selinux,kdump,sosreport,packagekit"
menu_overrides_github_page_url="https://websoft9.github.io/websoft9/cockpit/menu_override"
cockpit_menu_overrides=(networkmanager.override.json shell.override.json storaged.override.json systemd.override.json users.override.json)


Install_PackageKit(){
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

Set_Firewall(){
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
    echo "Set Cockpit for Websoft9..."
    sudo systemctl daemon-reload
    sudo systemctl enable --now cockpit cockpit.socket
    echo "Set Cockpit allowed root user" 
    file="/etc/cockpit/disallowed-users"
    if [ -f "$file" ]; then
        echo "" > "$file"
    else
        echo "$file is not exist"
    fi
    echo "Set cockpit port to $cockpit_port ..." 
    sudo sed -i "s/ListenStream=9090/ListenStream=$cockpit_port/" /lib/systemd/system/cockpit.socket
}

Download_Menu_Override(){
    for file in "${cockpit_menu_overrides[@]}"
        do
        wget -N -P /etc/cockpit "$menu_overrides_github_page_url/$file"
        done
}

Edit_Menu(){
    echo "Start to edit Cockpit origin Menu ..."
    # uninstall plugins
    cp -r /data/apps/websoft9/cockpit/menu_override/* /etc/cockpit || Download_Menu_Override
    sudo rm -rf /usr/share/cockpit/{$cockpit_plugin_delete}
    sudo systemctl daemon-reload
    sudo systemctl restart cockpit.socket
}

Install_Cockpit(){
    echo "Prepare to install Cockpit ..." 
    sudo pkcon refresh
    sudo pkcon get-updates
    sudo pkcon install $cockpit_packages -y || echo "Install failed or this OS not support Cockpit"
    sudo pkcon update cockpit -y || echo "Upgrade failed or this OS not support Cockpit"
    Set_Firewall
    Set_Cockpit
    Edit_Menu
}

Install_PackageKit
Install_Cockpit