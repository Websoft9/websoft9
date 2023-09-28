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
port="9000"
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
        *)
            shift
            ;;
    esac
done

# 输出参数值
echo "Your installation parameters are as follows: "
echo "--version: $version"
echo "--port: $port"
echo "--channel: $channel"
echo "--path: $path"

# Define global vars
# export var can send it to subprocess

export http_port=80
export https_port=443
export cockpit_port=$port
export install_path=$path
export channel
export version
export systemd_path="/opt/websoft9/systemd"
export source_zip="websoft9-$version.zip"
export source_unzip="websoft9"
export source_github_pages="https://websoft9.github.io/websoft9"
export tools_yum="git curl wget yum-utils jq bc unzip"
export tools_apt="git curl wget jq bc unzip"
export docker_network="websoft9"
export artifact_url="https://w9artifact.blob.core.windows.net/$channel/websoft9"
echo Install from url: $artifact_url

# Define common functions

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
    echo_prefix_source=$'\n[Dowload Source] - '
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
    sudo docker stop websoft9-proxy || echo "docker stop websoft9-proxy failed "
    sudo systemctl stop cockpit || echo "systemctl stop cockpit failed"
    sudo systemctl stop cockpit.socket || echo "systemctl stop cockpit.socket failed"

    for port in "${ports[@]}"; do
        if netstat -tuln | grep ":$port " >/dev/null; then
            echo "Port $port is in use, install failed"
            exit
        fi
    done

    echo "All ports are available"
}

install_backends() {
    echo_prefix_backends=$'\n[Backend] - '
    echo "$echo_prefix_backends Install backend docker services"

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

    container_names=$(docker ps -a --format "{{.Names}}" --filter "name=websoft9")
    sudo docker compose -p websoft9 down
    
    # delete some dead containers that docker compose cannot deleted
    if [ ! -z "$container_names" ]; then
        echo "Deleting containers:"
        echo $container_names
        docker rm $container_names
    else
        echo "No containers to delete."
    fi

    sudo docker compose -p websoft9 pull
    sudo docker compose -p websoft9 up -d
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

    sudo cp -r $install_path/systemd/* "$systemd_path"
    sudo cp -f "$systemd_path/websoft9.service" /lib/systemd/system/
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

echo "------ Welcome to install Websoft9, it will take 3-5 minutes ------" 
check_ports $http_port $https_port $cockpit_port
install_tools
download_source

bash $install_path/install/install_docker.sh
bash $install_path/install/install_cockpit.sh
bash $install_path/install/install_plugins.sh

install_backends
install_systemd
echo "-- Install success! Access Websoft9 console by: http://Internet IP:$cockpit_port and using Linux user for login ------" 