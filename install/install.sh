#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


# Command-line options
# ==============================================================================
#
# --version
# Use the --version option to install a special version for installation. default is latest, for example:
#
#  $ sudo bash install.sh --version "0.8.25"
#
# --port <9000>
# Use the --port option to set Websoft9 cosole port. default is 9000, for example:
#
#   $ sudo bash install.sh --port 9001
#
# --channel <release|dev>
# Use the --channel option to install a release(production) or dev distribution. default is release, for example:
#
#  $ sudo bash install.sh --channel release
#
# --path
# Use the --path option to for installation path for example:
#
#  $ sudo bash install.sh --path "/data/websoft9/source"
#
# ==============================================================================


# 设置参数的默认值
version="latest"
channel="release"
path="/data/websoft9/source"

# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            version="$2"
            shift 2
            ;;
        --port)
            port="$2"
            shift 2
            ;;
        --channel)
            channel="$2"
            shift 2
            ;;
        --path)
            path="$2"
            shift 2
            ;;
        --devto)
            path="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -n "$port" ]; then
    export port
else
    port=9000
fi


# 输出参数值
echo -e "\n------ Welcome to install Websoft9, it will take 3-5 minutes ------"
echo -e "\nYour installation parameters are as follows: "
echo "--version: $version"
echo "--port: $port"
echo "--channel: $channel"
echo "--path: $path"
echo "--devto: $devto"

echo -e "\nYour OS: "
cat /etc/os-release | head -n 3  2>/dev/null

# Define global vars
# export var can send it to subprocess

export http_port=80
export https_port=443
export install_path=$path
export channel
export version
export systemd_path="/opt/websoft9/systemd"
export source_zip="websoft9-$version.zip"
export source_unzip="websoft9"
export source_github_pages="https://websoft9.github.io/websoft9"
export tools_yum="git curl wget yum-utils jq bc unzip inotify-tools"
export tools_apt="git curl wget jq bc unzip inotify-tools"
export docker_network="websoft9"
export artifact_url="https://w9artifact.blob.core.windows.net/$channel/websoft9"
echo Install from url: $artifact_url

# Define common functions

Wait_apt() {
    # Function to check if apt is locked
    local lock_files=("/var/lib/dpkg/lock" "/var/lib/apt/lists/lock")

    for lock_file in "${lock_files[@]}"; do
        while fuser "${lock_file}" >/dev/null 2>&1 ; do
            echo "${lock_file} is locked by another process. Waiting..."
            sleep 5
        done
    done

    echo "APT locks are not held by any processes. You can proceed."
}

export -f Wait_apt


install_tools(){
    echo_prefix_tools=$'\n[Tools] - '
    echo "$echo_prefix_tools Starting install necessary tool..."

    dnf --version >/dev/null 2>&1
    dnf_status=$?
    yum --version >/dev/null 2>&1
    yum_status=$?
    apt --version >/dev/null 2>&1
    apt_status=$?

    if [ $dnf_status -eq 0 ]; then
        dnf install $tools_yum -y
    elif [ $yum_status -eq 0 ]; then
        yum install $tools_yum -y
    elif [ $apt_status -eq 0 ]; then
        while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
        echo "Waiting for other software managers to finish..."
        sleep 5
        done
        sudo apt update -y 1>/dev/null 2>&1
        apt install $tools_apt -y --assume-yes
    else
        echo "None of the required package managers are installed."
    fi
}



download_source() {
    echo_prefix_source=$'\n[Download Source] - '
    echo "$echo_prefix_source Download Websoft9 source code from $artifact_url/$source_zip"
    
    find . -type f -name "websoft9*.zip*" -exec rm -f {} \;
    if [ -d "$install_path" ]; then
        echo "Directory $install_path already exists and installation will cover it."
    else
        mkdir -p "$install_path"
    fi

    wget "$artifact_url/$source_zip"
    if [ $? -ne 0 ]; then
        echo "Failed to download source package."
        exit 1
    fi

    sudo unzip -o "$source_zip" -d "$install_path" > /dev/null
    if [ $? -ne 0 ]; then
        echo "Failed to unzip source package."
        exit 1
    fi

    cp -r $install_path/$source_unzip/* "$install_path"
    if [ $? -ne 0 ]; then
        echo "Move directory failed"
        exit 1
    fi

    rm -rf "$source_zip" "$install_path/$source_unzip"

}



check_ports() {
    local ports=("$@")

    echo "Stop Websoft9 Proxy and Cockpit service for reserve ports..."
    sudo docker stop websoft9-proxy 2>/dev/null || echo "docker stop websoft9-proxy not need "
    sudo systemctl stop cockpit 2>/dev/null || echo "systemctl stop cockpit not need"
    sudo systemctl stop cockpit.socket 2>/dev/null || echo "systemctl stop cockpit.socket not need"


    for port in "${ports[@]}"; do
        if netstat -tuln | grep ":$port " >/dev/null; then
            echo "Port $port is in use, install failed"
            exit
        fi
    done

    echo "All ports are available"
}


source_github_pages="https://websoft9.github.io/websoft9"
install_path="/data/websoft9/source"


merge_json_files() {
    local target_path="/etc/docker/daemon.json"

    python3 - <<EOF 2>/dev/null
import json
import urllib.request
import os

def merge_json_files(file1, file2):
    print("Merge from local file... ")
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    merged_data = {**data1, **data2}

    with open(file1, 'w') as f:
        json.dump(merged_data, f, indent=4)

def download_and_merge(url, file_path):
    print("Download daemon.json from url and merge... ")
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())

    with open(file_path, 'r') as f:
        local_data = json.load(f)

    merged_data = {**local_data, **data}

    with open(file_path, 'w') as f:
        json.dump(merged_data, f, indent=4)

# Create target file if it does not exist
if not os.path.exists("${target_path}"):
    os.makedirs(os.path.dirname("${target_path}"), exist_ok=True)
    with open("${target_path}", 'w') as f:
        json.dump({}, f)

if os.path.exists("${install_path}/docker/daemon.json"):
    merge_json_files("${target_path}", "${install_path}/docker/daemon.json")
elif urllib.request.urlopen("${source_github_pages}/docker/daemon.json").getcode() == 200:
    download_and_merge("${source_github_pages}/docker/daemon.json", "${target_path}")
else:
    print("No target daemon.json file need to merged")
EOF

    if [ $? -ne 0 ]; then
        echo "merge daemon.json failed, but install continue running"
    fi
}


set_docker(){
    echo "Set Docker for Websoft9 backend service..."
    merge_json_files
    if ! systemctl is-active --quiet firewalld; then
        echo "firewalld is not running"  
    else
        echo "Set firewall for Docker..."
        sudo sudo firewall-cmd --permanent --new-zone=docker 2> /dev/null
        sudo firewall-cmd --permanent --zone=docker --add-interface=docker0 2> /dev/null
        sudo firewall-cmd --permanent --zone=docker --set-target=ACCEPT
        sudo firewall-cmd --reload
    fi
    sudo systemctl restart docker   
}

install_backends() {
    echo_prefix_backends=$'\n[Backend] - '
    echo "$echo_prefix_backends Install backend docker services"
    set_docker

    cd "$install_path/docker"
    if [ $? -ne 0 ]; then
        echo "Failed to change directory."
        exit 1
    fi

    sudo docker network inspect $docker_network >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "Docker network '$docker_network' already exists."
    else
        sudo docker network create $docker_network
        if [ $? -ne 0 ]; then
            echo "Failed to create docker network."
            exit 1
        fi
    fi

    # set to devloper mode
    if [ -n "$devto" ]; then
        sed -i "s|.*:/websoft9/src|$devto:/websoft9/src|g" docker-compose-dev.yml
        composefile=docker-compose-dev.yml
    else
        composefile=docker-compose.yml
    fi

    container_names=$(docker ps -a --format "{{.Names}}" --filter "name=websoft9")
    sudo docker compose -p websoft9 -f $composefile down
    
    # delete some dead containers that docker compose cannot deleted
    if [ ! -z "$container_names" ]; then
        echo "Deleting containers:"
        echo $container_names
        docker rm -f $container_names 2>/dev/null
    else
        echo "No containers to delete."
    fi

    sudo docker compose -f $composefile pull
    sudo docker compose -p websoft9 -f $composefile up -d --build
    if [ $? -ne 0 ]; then
        echo "Failed to start docker services."
        exit 1
    fi
}


install_systemd() {
    echo_prefix_systemd=$'\n[Systemd] - '
    echo "$echo_prefix_systemdInstall Systemd service"

    if [ ! -d "$systemd_path" ]; then
    sudo mkdir -p "$systemd_path"
    fi

    sudo cp -r $install_path/systemd/script/* "$systemd_path"
    sudo cp -f "$install_path/systemd/websoft9.service" /lib/systemd/system/
    if [ $? -ne 0 ]; then
        echo "Failed to copy Systemd service file."
        exit 1
    fi

    sudo systemctl daemon-reload
    if [ $? -ne 0 ]; then
        echo "Failed to reload Systemd daemon."
        exit 1
    fi

    sudo systemctl enable websoft9.service
    if [ $? -ne 0 ]; then
        echo "Failed to enable Systemd service."
        exit 1
    fi

    sudo systemctl start websoft9
    if [ $? -ne 0 ]; then
        echo "Failed to start Systemd service."
        exit 1
    fi
}



#--------------- main-----------------------------------------
check_ports $http_port $https_port $port
install_tools
download_source

bash $install_path/install/install_docker.sh
if [ $? -ne 0 ]; then
    echo "install_docker failed with error $?. Exiting."
    exit 1
fi

bash $install_path/install/install_cockpit.sh
if [ $? -ne 0 ]; then
    echo "install_cockpit failed with error $?. Exiting."
    exit 1
fi

bash $install_path/install/install_plugins.sh
if [ $? -ne 0 ]; then
    echo "install_plugins failed with error $?. Exiting."
    exit 1
fi

install_backends
install_systemd

echo -e "\n-- Install success! ------" 
echo "Access Websoft9 console by: http://Internet IP:$(grep ListenStream /lib/systemd/system/cockpit.socket | cut -d= -f2) and using Linux user for login"