#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# Install and Upgade Docker for mosts of Linux
# This script is intended from https://get.docker.com and add below:
#
# - install or update Docker
# - support Redhat, CentOS-Stream, OracleLinux, AmazonLinux
#
# 1. download the script
#
#   $ curl -fsSL https://websoft9.github.io/websoft9/install/install_docker.sh -o install_docker.sh
#
# 2. verify the script's content
#
#   $ cat install_docker.sh
#
# 3. run the script with --dry-run to verify the steps it executes
#
#   $ sh install_docker.sh --dry-run
#
# 4. run the script either as root, or using sudo to perform the installation.
#
#   $ sudo sh install_docker.sh


# it must export, otherwise Rocky Linux cannot used at yum command
export docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
echo_prefix_docker=$'\n[Docker] - '

docker_exist() {
    # 检查 `docker` 命令是否存在
    if ! command -v docker &> /dev/null; then
        echo "docker command not exist"
        return 1
    fi

    # 检查 Docker 服务是否正在运行
    systemctl is-active docker.service &> /dev/null
    if [ $? -ne 0 ]; then
        echo "Docker service is not running, trying to start it..."
        systemctl start docker.service
        if [ $? -ne 0 ]; then
            echo "Failed to start Docker service."
            return 1
        fi
    fi

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
            sudo yum install yum-utils -y > /dev/null
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install $docker_packages -y
        fi
    fi

    # For Ubuntu, Debian, or Raspbian
    if type apt >/dev/null 2>&1; then
        # Wait for apt to be unlocked
        curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
    fi
}


Upgrade_Docker(){
if docker_exist; then
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
        sudo apt update -y
        sudo apt -y install --only-upgrade $docker_packages
    else
        echo "Docker installed, but cannot upgrade"
    fi
else

    max_retries=3
    retry_count=0

    while ((retry_count < max_retries)); do
        Install_Docker
        if [ $? -ne 0 ]; then
            echo "Installation timeout or failed, retrying..."
            ((retry_count++))
        else
            echo "Docker installed successfully."
            exit 0
        fi
    done

    echo "Docker Installation failed after $max_retries retries."
    exit 1

fi
}

Start_Docker(){
# should have Docker server and Docker cli
if docker_exist; then
    echo "$echo_prefix_docker Starting Docker"
    sudo systemctl enable docker
    sudo systemctl restart docker
else
   echo "Docker not installed or start failed, exit..."
   exit 1
fi
}

echo -e "\n\n-------- Docker --------"
Upgrade_Docker
Start_Docker