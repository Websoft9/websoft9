#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# Install and Upgade Docker for mosts of Linux
# This script is intended from https://get.docker.com and add below:
#
# - remove Podman
# - support Redhat, CentOS-Stream, OracleLinux, AmazonLinux
#
# 1. download the script
#
#   $ curl -fsSL https://websoft9.github.io/websoft9/install/install-docker.sh -o install-docker.sh
#
# 2. verify the script's content
#
#   $ cat install-docker.sh
#
# 3. run the script with --dry-run to verify the steps it executes
#
#   $ sh install-docker.sh --dry-run
#
# 4. run the script either as root, or using sudo to perform the installation.
#
#   $ sudo sh install-docker.sh

############################################################
# Below vars export from install.sh
#  $force_install
############################################################


docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
echo_prefix_docker=$'\n[Docker] - '

# Function to check if apt is locked
is_apt_locked(){
    if [[ -f /var/lib/dpkg/lock-frontend || -f /var/lib/apt/lists/lock ]]; then
        return 0  # Apt is locked
    else
        return 1  # Apt is not locked
    fi
}

docker_exist() {
    # 检查 `docker` 命令是否存在
    if ! command -v docker &> /dev/null; then
        echo "false"
        return 1
    fi

    # 检查 Docker 服务是否存在
    systemctl status docker &> /dev/null
    if [ $? -ne 0 ]; then
        echo "false"
        return 1
    fi

    echo "true"
    return 0
}


Install_Docker(){
    echo "$echo_prefix_docker Installing Docker for your system"

    # For redhat family
    if [[ -f /etc/redhat-release ]]; then
        # For CentOS, Fedora, or RHEL(only s390x)
        if [[ $(cat /etc/redhat-release) =~ "RHEL" ]] && [[ $(uname -m) == "s390x" ]] || [[ $(cat /etc/redhat-release) =~ "CentOS" ]] || [[ $(cat /etc/redhat-release) =~ "Fedora" ]]; then
            curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
        else
        # For other distributions
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install $docker_packages -y
        fi
    fi

    # For Ubuntu, Debian, or Raspbian
    if type apt >/dev/null 2>&1; then
        apt update
        # Wait for apt to be unlocked
        while is_apt_locked; do
            echo "Waiting for apt to be unlocked..."
            sleep 5
        done
        curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
    fi
}


Upgrade_Docker(){
if eval "$docker_exist"; then
    echo "$echo_prefix_docker Upgrading Docker for your system..."
    dnf --version >/dev/null 2>&1
    dnf_status=$?
    yum --version >/dev/null 2>&1
    yum_status=$?
    apt --version >/dev/null 2>&1
    apt_status=$?

    if [ $dnf_status -eq 0 ]; then
        sudo dnf update -y $docker_packages
    elif [ $yum_status -eq 0 ]; then
        sudo yum update -y $docker_packages
    elif [ $apt_status -eq 0 ]; then
        sudo apt -y install --only-upgrade $docker_packages
    else
        echo "Docker installed, but cannot upgrade"
    fi
else
    Install_Docker
fi
}

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


Set_Docker(){
# should have Docker server and Docker cli
if eval $docker_exist; then
    echo "$echo_prefix_docker Starting to Set docker..."
    sudo systemctl enable docker
    sudo systemctl start docker
    if ! docker network inspect websoft9 > /dev/null 2>&1; then
      sudo docker network create websoft9
    fi
else
   echo "Docker no installed, exit..."
   exit
fi
}

## This Script starting here ....................................

if command -v podman &> /dev/null; then
    if [ "$force_install" = "y" ]; then
        Remove_Podman
    else
        read -p "Install Websoft9 will remove Podman and Install Docker for continue(y/n): " answer
        if [ "$answer" = "y" ]; then
            Remove_Podman
        fi
    fi
fi

Upgrade_Docker
Set_Docker