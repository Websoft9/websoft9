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
# --channel <release|rc|dev>
# Use the --channel option to install a release(production) or dev distribution. default is release, for example:
#
#  $ sudo bash install.sh --channel release
#
# --path
# Use the --path option to for installation path for example:
#
#  $ sudo bash install.sh --path "/data/websoft9/source"
#
# --apps <wordpress,gitlab>
# Use the --apps option to set Websoft9 appstore dispaly. default is null and display all applicaionts. If you set it, appstore only display the defined, for example:
#
#   $ sudo bash install.sh --apps "wordpress,gitlab"
#
# --mirrors <https://docker.rainbond.cc,https://registry.inner.websoft9.cn>
# Use the --mirrors option to set docker image mirrors when can not pull image from docker-hub, for example:
#
#   $ sudo bash install.sh --mirrors "https://docker.rainbond.cc,https://registry.inner.websoft9.cn"
#
# --devto
# Use the --devto option to developer mode, devto is the developer code path, for example:
#
#  $ sudo bash install.sh --devto "/data/dev/mycode"
#
# --execute_mode <auto|install|upgrade>
# Use the --execute_mode option to tell script is install Websoft9 or Ugrade Websoff9. The default value is auto 
# and script will automaticlly check it need install or upgrade, for example:
#
#  $ sudo bash install.sh --execute_mode "upgrade"
#
# ==============================================================================


# 设置参数的默认值
version="latest"
channel="release"
execute_mode="auto"
path="/data/websoft9/source"
apps=""
mirrors="https://dockerhub.websoft9.com"

# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --version"
                exit 1
            fi
            version="$1"
            shift
            ;;
        --port)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --port"
                exit 1
            fi
            port="$1"
            shift
            ;;
        --channel)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --channel"
                exit 1
            fi
            channel="$1"
            shift
            ;;
        --path)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --path"
                exit 1
            fi
            path="$1"
            shift
            ;;
        --apps)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --apps"
                exit 1
            fi
            apps="$1"
            shift
            ;;
        --mirrors)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --mirrors"
                exit 1
            fi
            mirrors="$1"
            shift
            ;;
        --devto)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --devto"
                exit 1
            fi
            devto="$1"
            shift
            ;;
        --execute_mode)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --execute_mode"
                exit 1
            fi
            execute_mode="$1"
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# check it is root user or have sudo changed to root user,if not  exit 1
if [ $(id -u) -ne 0 ]; then
    echo "You must be the root user to run this script."
    exit 1
fi

if [ -n "$port" ]; then
    export port
else
    export port=9000
fi


starttime=$(date +%s)

# Automaticlly check the $execute_mode to install or upgrade if is auto
if [ "$execute_mode" = "auto" ]; then
    if sudo systemctl cat websoft9 >/dev/null 2>&1 && sudo systemctl cat cockpit >/dev/null 2>&1 && sudo docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^websoft9-apphub'; then
        echo "execute_mode=upgrade"
        export execute_mode="upgrade"
    else
        echo "execute_mode=install"
        export execute_mode="install"
    fi
fi


# 输出参数值
echo -e "\n------ Welcome to install Websoft9, it will take 3-5 minutes ------"
echo -e "\nYour installation parameters are as follows: "
echo "--version: $version"
echo "--port: $port"
echo "--channel: $channel"
echo "--path: $path"
echo "--apps: $apps"
echo "--mirrors: $mirrors"
echo "--devto: $devto"
echo "--execute_mode: $execute_mode"

echo -e "\nYour OS: "
cat /etc/os-release | head -n 3  2>/dev/null

# Define global vars
# export var can send it to subprocess

export http_port=80
export https_port=443
export install_path=$path
export channel
export version
export apps
export mirrors
export systemd_path="/opt/websoft9/systemd"
export source_zip="websoft9-$version.zip"
export source_unzip="websoft9"
export source_github_pages="https://websoft9.github.io/websoft9"
# inotify-tools is at epel-release
export repo_tools_yum="epel-release"
export tools_yum="git curl wget jq bc unzip inotify-tools yum-utils"
export tools_apt="git curl wget jq bc unzip inotify-tools"
export docker_network="websoft9"
export artifact_url="https://artifact.websoft9.com/$channel/websoft9"
# export OS release environments
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    echo "Can't judge your Linux distribution"
    exit 1
fi
echo Install from url: $artifact_url

if [ -d "$install_path" ]; then
    echo "Directory $install_path already exists and installation will cover it."
else
    sudo mkdir -p "$install_path"
fi
    
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

    if [ "$ID" = "rhel" ] || [ "$ID" = "ol" ]; then
        RHEL_VERSION=${VERSION_ID%%.*}
        sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-${RHEL_VERSION}.noarch.rpm >/dev/null
        if [ $? -ne 0 ]; then
            exit 1
        fi 
    elif [ "$ID" = "centos" ] || [ "$ID" = "rocky" ]; then
        sudo yum install -y "$repo_tools_yum" >/dev/null
        if [ $? -ne 0 ]; then
            exit 1
        fi 
    elif [ "$ID" = "amzn" ]; then
        sudo amazon-linux-extras install epel -y >/dev/null
        if [ $? -ne 0 ]; then
            exit 1
        fi 
    fi

    dnf --version >/dev/null 2>&1
    dnf_status=$?
    yum --version >/dev/null 2>&1
    yum_status=$?
    apt --version >/dev/null 2>&1
    apt_status=$?

    if [ $dnf_status -eq 0 ]; then
        for package in $tools_yum; do 
            echo "Start to install $package"
            sudo dnf install -y $package > /dev/null
            if [ $? -ne 0 ]; then
                exit 1
            fi 
        done
    elif [ $yum_status -eq 0 ]; then
        for package in $tools_yum; do 
            echo "Start to install $package"
            sudo yum install -y $package > /dev/null
            if [ $? -ne 0 ]; then
                exit 1
            fi 
        done
    elif [ $apt_status -eq 0 ]; then
        while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
        echo "Waiting for other software managers to finish..."
        sleep 5
        done
        sudo apt-get update -y 1>/dev/null 2>&1
        for package in $tools_apt; do 
            echo "Start to install $package"
            sudo apt-get install $package -y > /dev/null
            if [ $? -ne 0 ]; then
                exit 1
            fi                        
        done
    else
        echo "You system can not install Websoft9 because not have available Linux Package Manager"
        exit 1
    fi
}

download_artifact() {
    local artifact_url="$1"
    local source_zip="$2"
    local max_attempts="$3"
    
    for ((i=1; i<=max_attempts; i++)); do
        wget --timeout=4 --read-timeout=30 -P /tmp "$artifact_url/$source_zip"
        if [ $? -eq 0 ]; then
            echo "Downloaded successfully using wget on attempt $i."
            return 0
        else
            echo "Attempt $i failed using wget."
        fi
    done

    for ((i=1; i<=max_attempts; i++)); do
        curl -o /tmp/"$source_zip" "$artifact_url/$source_zip"
        if [ $? -eq 0 ]; then
            echo "Downloaded successfully using curl on attempt $i."
            return 0 
        else
            echo "Attempt $i failed using curl."
        fi
    done

    echo "Failed to download source package after $((max_attempts * 2)) attempts."
    return 1
}

download_source_and_checkimage() {
    echo_prefix_source=$'\n[Download Source] - '
    echo "$echo_prefix_source Download Websoft9 source code from $artifact_url/$source_zip"
    
    find . -type f -name "websoft9*.zip*" -exec rm -f {} \;
    rm -rf /tmp/$source_unzip

    download_artifact "$artifact_url" "$source_zip" 10
    if [ $? -ne 0 ]; then
        echo "Failed to download source package."
        exit 1
    fi
    
    ## unzip and check image
    sudo unzip -o "/tmp/$source_zip" -d /tmp > /dev/null
    if [ $? -ne 0 ]; then
        echo "Failed to unzip source package."
        exit 1
    fi
    
    # install docker
    bash /tmp/$source_unzip/install/install_docker.sh

    cd /tmp/$source_unzip/docker
    docker compose pull
    if [ $? -ne 0 ]; then
    
        echo "Can not pull images from docker hub, set mirrors...."

        if [ -f "/etc/docker/daemon.json" ]; then
            if grep -q "registry-mirrors" "/etc/docker/daemon.json"; then
                mv /etc/docker/daemon.json /etc/docker/daemon.json.bak
                cp daemon.json /etc/docker/daemon.json
            else
                rm -f /etc/docker/daemon.json
                cp daemon.json /etc/docker/daemon.json
            fi
        else
            cp daemon.json /etc/docker/daemon.json
        fi

        sudo systemctl daemon-reload
        sudo systemctl restart docker

        # pull image by new mirrors
        docker compose pull
        if [ $? -ne 0 ]; then
            echo "image pull failed again, exit install"
            exit 1
        else
            echo "image pull success by new mirrors"
        fi
    else
        echo "image pull success"
    fi

    rm -rf /tmp/$source_unzip
    sudo unzip -o "/tmp/$source_zip" -d "$install_path" > /dev/null
    if [ $? -ne 0 ]; then
        echo "Failed to unzip source package."
        exit 1
    fi

    cp -r $install_path/$source_unzip/* "$install_path"
    if [ $? -ne 0 ]; then
        echo "Move directory failed"
        exit 1
    fi

    rm -rf "/tmp/$source_zip" "$install_path/$source_unzip"

}

check_ports() {
    local ports=("$@")

    echo "Stop Websoft9 Proxy and Cockpit service for reserve ports..."
    sudo docker stop websoft9-proxy 2>/dev/null || echo "docker stop websoft9-proxy not need "
    
    for port in "${ports[@]}"; do

        if [[ $port =~ ^[0-9]+$ ]] && [ $port -ge 0 ] && [ $port -le 65535 ]; then
            if ss -tuln | grep ":$port " >/dev/null && ! systemctl status cockpit.socket | grep "$port" >/dev/null; then
                echo "Port $port is in use or not in cockpit.socket, install failed"
                exit 1
            fi
        else
            echo "Invalid port: $port"
            exit 1
        fi

    done

    echo "All ports are available"
}

set_docker(){
    echo "Set Docker for Websoft9 backend service..."
    if ! systemctl is-active --quiet firewalld; then
        echo "firewalld is not running"  
    else
        echo "Set firewall for Docker..."
        sudo sudo firewall-cmd --permanent --new-zone=docker 2> /dev/null
        sudo firewall-cmd --permanent --zone=docker --add-interface=docker0 2> /dev/null
        sudo firewall-cmd --permanent --zone=docker --set-target=ACCEPT
        sudo firewall-cmd --reload
        sudo systemctl stop firewalld
        sudo systemctl disable firewalld
    fi

    if [ "$execute_mode" = "install" ]; then
        sudo systemctl restart docker   
    fi 
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
        sed -i "s|\(- \).*:/websoft9/apphub-dev|\1$devto:/websoft9/apphub-dev|g" docker-compose-dev.yml
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
    
    sudo docker compose -p websoft9 -f $composefile up -d
    if [ $? -ne 0 ]; then
        echo "Failed to start docker services."
        exit 1
    fi

    if [ "$execute_mode" = "install" ]; then
        sudo docker exec -i websoft9-apphub apphub setconfig --section domain --key wildcard_domain --value ""
        if [ -n "$apps" ]; then
            sudo docker exec -i websoft9-apphub apphub setconfig --section initial_apps --key keys --value "$apps"
        fi
    fi 
    
    if [ -f "/etc/docker/daemon.json.bak" ]; then
        rm -rf /etc/docker/daemon.json
        mv /etc/docker/daemon.json.bak /etc/docker/daemon.json
    fi
}

install_systemd() {
    echo -e "\n\n-------- Systemd --------"
    echo_prefix_systemd=$'\n[Systemd] - '
    echo "$echo_prefix_systemd Install Systemd service"

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

    sudo systemctl restart websoft9
    if [ $? -ne 0 ]; then
        echo "Failed to start Systemd service."
        exit 1
    fi
}

#--------------- main-----------------------------------------
log_path="$install_path/install.log"
check_ports $http_port $https_port $port | tee -a  $log_path
install_tools | tee -a  $log_path

download_source_and_checkimage | tee -a  $log_path

install_backends | tee -a  $log_path

bash $install_path/install/install_cockpit.sh | tee -a  $log_path
if [ $? -ne 0 ]; then
    echo "install_cockpit failed with error $?. Exiting."
    exit 1
fi

install_systemd | tee -a  $log_path

bash $install_path/install/install_plugins.sh | tee -a  $log_path
if [ $? -ne 0 ]; then
    echo "install_plugins failed with error $?. Exiting."
    exit 1
fi

echo "Restart Docker for Firewalld..."
if [ "$execute_mode" = "install" ]; then
    sudo systemctl restart docker   
fi 

endtime=$(date +%s)
runtime=$((endtime-starttime))
echo "Script execution time: $runtime seconds"
echo -e "\n-- Install success! ------" 
echo "Access Websoft9 console by: http://Internet IP:$(grep ListenStream /lib/systemd/system/cockpit.socket | cut -d= -f2) and using Linux user for login"
