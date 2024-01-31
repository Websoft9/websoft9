#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH

## This script is used for install or upgrade Cockpit on Linux
## Cockpit build at redhat family: https://copr.fedorainfracloud.org/coprs/g/cockpit/cockpit-preview/monitor/
## Cockpit reposoitory list: https://pkgs.org/download/cockpit
## PackageKit: https://www.freedesktop.org/software/PackageKit/
## Not use pkcon install/update cockpit, the reason is: https://cockpit-project.org/faq.html#error-message-about-being-offline
## pkcon can read repositories at you system directly, it don't provide exra repository
## [apt show cockpit] or [apt install cockpit] show all additional packages
## Ubuntu have backports at file /etc/apt/sources.list by default
## Cockpit application: https://cockpit-project.org/applications

# Command-line options
# ==========================================================
#
# --port <9000>
# Use the --port option to set Websoft9 cosole port. default is 9000, for example:
#
#   $ sudo sh install_cockpit.sh --port 9001

############################################################
# Below vars export from install.sh
#  $port
#  $install_path
############################################################

echo -e "\n\n-------- Cockpit --------"

# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --port"
                exit 1
            fi
            port="$1"
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# Port priority: --port > ListenStream= > 9000

cockpit_exist() {
  systemctl list-unit-files | grep -q "cockpit.service"
  return $?
}

if cockpit_exist; then
    cockpit_now_port=$(grep -oP "(?<=^ListenStream=).*" "/lib/systemd/system/cockpit.socket")
    if [ -z "${cockpit_now_port// }" ]; then
        echo "cockpit port is null,set it to 9000"
        cockpit_now_port=9000
    else
        echo "$cockpit_now_port at cockpit.socket"
    fi

else
    cockpit_now_port=9000
fi

if [ -n "$port" ]; then
    cockpit_port=$port
else
    cockpit_port=$cockpit_now_port
fi


if [ -n "$install_path" ]; then
    echo "Have found install files"
else
    install_path="/data/websoft9/source"
fi

echo -e "\nYour installation parameters are as follows: "
echo "cockpit_port:$cockpit_port"
echo "install_path:$install_path"

related_containers=("websoft9-apphub")
echo_prefix_cockpit=$'\n[Cockpit] - '
# package cockpit depends_on [cockpit-bridge,cockpit-ws,cockpit-system], but update cockpit the depends don't update 
cockpit_packages="cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-pcp cockpit-networkmanager cockpit-session-recording cockpit-sosreport"
menu_overrides_github_page_url="https://websoft9.github.io/websoft9/cockpit/menu_override"
cockpit_config_github_page_url="https://websoft9.github.io/websoft9/cockpit/cockpit.conf"
cockpit_menu_overrides=()
# export OS release environments
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    echo "Can't judge your Linux distribution"
    exit 1
fi

# This solution from: https://help.ubuntu.com/community/PinningHowto
pin_config="
Package: cockpit*
Pin: release a=$VERSION_CODENAME-backports
Pin-Priority: 1000
"

check_ports() {
    local ports=("$@")

    for port in "${ports[@]}"; do
        if [[ $port =~ ^[0-9]+$ ]] && [ $port -ge 0 ] && [ $port -le 65535 ]; then
            if netstat -tuln | grep ":$port " >/dev/null; then
                echo "Port $port is in use, install failed"
                exit
            fi
        else
            echo "Invalid port: $port"
            exit 1
        fi
    done

    echo "All ports are available"
}

Print_Version(){
    sudo /usr/libexec/cockpit-ws --version 2>/dev/null || sudo /usr/lib/cockpit-ws --version 2>/dev/null || /usr/lib/cockpit/cockpit-ws --version 2>/dev/null
}

Disable_PackageKit(){
    
    echo "$echo_prefix_cockpit disable PackageKit(pkcon)"

    if command -v pkcon &> /dev/null; then
        echo "pkcon is at your system ..."
        sudo  systemctl stop packagekit
        sudo  systemctl disable packagekit
 
    fi
}

Set_Repository() {
    echo "$echo_prefix_cockpit Set Cockpit deb repository"
    if command -v apt &> /dev/null; then
        if [ "$NAME" = "Debian" ]; then
            echo "deb http://deb.debian.org/debian $VERSION_CODENAME-backports main" > /etc/apt/sources.list.d/backports.list
        fi
        echo "Set the cockpit repository priority on Ubuntu/Debian..."
        sudo bash -c "echo '$pin_config' > /etc/apt/preferences.d/cockpit_backports"
    fi
    echo "Complete set Cockpit repository"
}


Restart_Cockpit(){
    echo "$echo_prefix_cockpit Restart Cockpit"
    sudo systemctl daemon-reload
    sudo systemctl enable cockpit.socket 2> /dev/null
    sudo systemctl restart cockpit.socket 2> /dev/null
    sudo systemctl restart cockpit || exit 1
}

Add_Firewalld(){
    echo "Add cockpit service to Firewalld..."
    # cockpit.xml is not always the same path at Linux distributions
    sudo sed -i "s/port=\"[0-9]*\"/port=\"$cockpit_port\"/g" /etc/firewalld/services/cockpit.xml
    sudo sed -i "s/port=\"[0-9]*\"/port=\"$cockpit_port\"/g" /usr/lib/firewalld/services/cockpit.xml
    sudo firewall-cmd --zone=public --add-service=cockpit --permanent 
    sudo firewall-cmd --zone=public --add-port=443/tcp --permanent
    sudo firewall-cmd --zone=public --add-port=80/tcp --permanent
    sudo firewall-cmd --reload
}

Set_Firewalld(){
  echo "$echo_prefix_cockpit Set firewalld for cockpit access"
  if command -v firewall-cmd &> /dev/null; then
     echo "Set firewall for Cockpit..."
     if ! systemctl is-active --quiet firewalld; then
        sudo systemctl start firewalld
        Add_Firewalld
        sudo systemctl stop firewalld
     else
        Add_Firewalld
     fi
  fi
}

Set_Selinux(){
  echo "$echo_prefix_cockpit Set Selinux for cockpit access"
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

    # fix bug: https://github.com/Websoft9/websoft9/issues/332
    sed 's/selector(:is():where())/selector(:is(*):where(*))/' -i /usr/share/cockpit/static/login.js 

    echo "Set Cockpit config file..." 
    if [ -f "$install_path/cockpit/cockpit.conf" ]; then
        cp -f "$install_path/cockpit/cockpit.conf" /etc/cockpit/cockpit.conf
    else
        echo "Download config from URL $cockpit_config_github_page_url"
        curl -sSL $cockpit_config_github_page_url | sudo tee /etc/cockpit/cockpit.conf > /dev/null
    fi


    echo "Change cockpit default port to $cockpit_port ..." 
    sudo sed -i "s/ListenStream=[0-9]*/ListenStream=${cockpit_port}/" /lib/systemd/system/cockpit.socket


    if docker ps --format '{{.Names}}' | grep -wq "${related_containers[0]}"; then
        echo "Try to change cockpit port at ${related_containers[0]} container..."
        sudo docker exec -i ${related_containers[0]} apphub setconfig --section cockpit --key port --value $cockpit_port || true
    else
        echo "Not found ${related_containers[0]} container"
    fi


    # fwupd-refresh.service may push error for Cockpit menu, so disable it
    if sudo systemctl is-active --quiet fwupd-refresh.service; then
        echo "fwupd-refresh.service is already running. Stopping and disabling it..."
        sudo systemctl stop fwupd-refresh.service
        sudo systemctl disable fwupd-refresh.service
        echo "fwupd-refresh.service stopped and disabled."
    else
        echo "fwupd-refresh.service is not running."
    fi

}

get_github_files() {
    python3 - <<EOF
import requests
import json

url = "https://api.github.com/repos/Websoft9/websoft9/contents/cockpit/menu_override?ref=main"
headers = {
    "Accept": "application/vnd.github.v3+json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    files = json.loads(response.text)
    for file in files:
        print(file['name'])
else:
    print(f"Error: {response.status_code}")
EOF
}


Download_Menu_Override(){

    cockpit_menu_overrides=($(get_github_files))

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
        if [ $? -ne 0 ]; then
        echo "Failed to download cockpit.conf"
        exit 1
        fi
    fi

    if test -d "$install_path/cockpit/menu_override"; then
        cp -r $install_path/cockpit/menu_override/* /etc/cockpit
    else
        echo "Download override files from URL..."
        Download_Menu_Override
    fi
}

Install_Cockpit(){
    if cockpit_exist; then
        echo "$echo_prefix_cockpit Prepare to upgrade Cockpit"
        echo "You installed version:  "
        Print_Version
    else
        echo "$echo_prefix_cockpit Prepare to install Cockpit" 
        check_ports $port
    fi
    
    dnf --version >/dev/null 2>&1
    dnf_status=$?
    yum --version >/dev/null 2>&1
    yum_status=$?
    apt --version >/dev/null 2>&1
    apt_status=$? 

    if [ $dnf_status -eq 0 ]; then
        for pkg in $cockpit_packages
        do
            echo "Install or upgrade $pkg"
            sudo dnf upgrade -y "$pkg" > /dev/null  || echo "$pkg failed to upgrade"
            sudo dnf install -y "$pkg" > /dev/null  || echo "$pkg failed to install"
        done
    elif [ $yum_status -eq 0 ]; then
        for pkg in $cockpit_packages
        do
            echo "Install or update $pkg"
            sudo yum update -y "$pkg" > /dev/null || echo "$pkg failed to update"
            sudo yum install -y "$pkg" > /dev/null || echo "$pkg failed to install"
        done
    elif [ $apt_status -eq 0 ]; then
        export DEBIAN_FRONTEND=noninteractive
        sudo dpkg --configure -a
        apt-get update -y >/dev/null
        apt-get --fix-broken install
        for pkg in $cockpit_packages
        do
            echo "Installing $pkg"
            sudo apt-get install -u -y "$pkg" > /dev/null || echo "$pkg failed to install"
        done
    else
        echo "Neither apt,dnf nor yum found. Please install one of them and try again."
    fi

    Set_Firewalld
    Set_Selinux
    Set_Cockpit
    Edit_Menu
    Restart_Cockpit
}

Test_Cockpit(){
    echo "$echo_prefix_cockpit Test Cockpit console accessibility" 
    test_cmd="curl localhost:$cockpit_port"
    start_time=$(date +%s)
    timeout=30
    while true; do
        if $test_cmd >/dev/null 2>&1; then
            echo "Cockpit running OK..."
            break
        else
            current_time=$(date +%s)
            elapsed_time=$(($current_time - $start_time))
            if [ $elapsed_time -ge $timeout ]; then
                echo "Cockpit is not running... Timeout after waiting $timeout seconds."
                exit 1
            fi
            sleep 1
        fi
    done

    Print_Version
}


#### -------------- main() start here  -------------------  ####

Set_Repository
Install_Cockpit
Test_Cockpit

# release package memory
if systemctl cat packagekit > /dev/null 2>&1; then
  Disable_PackageKit
else
  echo "no packagekit"
fi
