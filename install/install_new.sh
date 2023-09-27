#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH
export PATH


# Command-line options
# ==============================================================================
#
# --force <y|n>
# Use the --force option to ignore all interactive choices. default is n, for example:
#
#  $ sudo sh install.sh --force n
#
# --port <9000>
# Use the --port option to set Websoft9 cosole port. default is 9000, for example:
#
#   $ sudo sh install.sh --port 9001
#
# --channel <release|dev>
# Use the --channel option to install a release(production) or dev distribution. default is release, for example:
#
#  $ sudo sh install.sh --channel release
#
# ==============================================================================

#!/bin/bash

# 设置参数的默认值
force="n"
port="9000"
channel="release"

# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            force="$2"
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
        *)
            shift
            ;;
    esac
done

# 输出参数值
echo "Your installation parameters are as follows: "
echo "--force: $force"
echo "--port: $port"
echo "--channel: $channel"

# Define global vars
# export var can send it to subprocess

export http_port=80
export https_port=443
export cockpit_port=$port
export force_install=$force
export install_path="/data/websoft9/source"
export systemd_path="/opt/websoft9/systemd"
export source_zip="websoft9-latest.zip"
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
    
    rm -rf websoft9-latest.zip*
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

    unzip -o "$source_zip" -d "$install_path"
    if [ $? -ne 0 ]; then
        echo "Failed to unzip source package."
        exit 1
    fi

    mv -fn $install_path/$source_unzip/* "$install_path"
    if [ $? -ne 0 ]; then
        echo "Move directory failed"
        exit 1
    fi

    rm -rf "$source_zip" "$install_path/$source_unzip"

}


check_ports() {
    local ports=("$@")

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