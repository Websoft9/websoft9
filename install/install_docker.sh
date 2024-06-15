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
    local mirror=$1
    local timeout=$2
    local repo_url=$3

    echo "$echo_prefix_docker Installing Docker from ${mirror} with timeout ${timeout} seconds for your system"

    if [ "$mirror" = "Official" ]; then
        mirror=""
    fi
    
    curl -fsSL --max-time 5 https://get.docker.com -o /dev/null

    if [ $? -eq 0 ]; then
        # For redhat family
        if [[ -f /etc/redhat-release ]] || command -v amazon-linux-extras >/dev/null 2>&1; then
            # For CentOS, Fedora, or RHEL(only s390x)
            if [[ $(cat /etc/redhat-release) =~ "Red Hat" ]] && [[ $(uname -m) == "s390x" ]] || [[ $(cat /etc/redhat-release) =~ "CentOS" ]] || [[ $(cat /etc/redhat-release) =~ "Fedora" ]]; then
                curl -fsSL https://get.docker.com -o get-docker.sh
                timeout $timeout sh get-docker.sh --channel stable --mirror $mirror
            else
                # For other distributions(Redhat and Rocky linux ...)
                dnf --version >/dev/null 2>&1
                dnf_status=$?
                yum --version >/dev/null 2>&1
                yum_status=$?

                if [ $dnf_status -eq 0 ]; then
                    sudo dnf install dnf-utils -y > /dev/null
                    sudo dnf config-manager --add-repo $repo_url
                    timeout $timeout sudo dnf install $docker_packages -y
                elif [ $yum_status -eq 0 ]; then
                    sudo yum install yum-utils -y > /dev/null
                    sudo yum-config-manager --add-repo $repo_url
                    if command -v amazon-linux-extras >/dev/null 2>&1; then
                        wget -O /etc/yum.repos.d/CentOS7-Base.repo https://websoft9.github.io/stackhub/apps/roles/role_common/files/CentOS7-Base.repo        
                        sudo sed -i "s/\$releasever/7/g" /etc/yum.repos.d/docker-ce.repo
                        timeout $timeout sudo yum install $docker_packages --disablerepo='amzn2-extras,amzn2-core' -y
                    else
                        timeout $timeout sudo yum install $docker_packages -y
                    fi
                    
                else
                    echo "None of the required package managers are installed."
                fi                
            fi
        fi
        
        # For Ubuntu, Debian, or Raspbian
        if type apt >/dev/null 2>&1; then
            # Wait for apt to be unlocked
            curl -fsSL https://get.docker.com -o get-docker.sh
            timeout $timeout sh get-docker.sh --channel stable --mirror $mirror
        fi
    else
        echo "can not install by installation script, use special way to install docker"
        dnf --version >/dev/null 2>&1
        dnf_status=$?
        yum --version >/dev/null 2>&1
        yum_status=$?
        apt --version >/dev/null 2>&1
        apt_status=$?

        if [ $dnf_status -eq 0 ]; then
            sudo dnf install yum-utils -y
            sudo dnf config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        elif [ $yum_status -eq 0 ]; then
            sudo yum install yum-utils -y
            sudo yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        elif [ $apt_status -eq 0 ]; then
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg lsb-release
            curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        else
            echo "don't know package tool"
        fi
        
        sudo systemctl enable docker
        sudo systemctl restart docker
        
        DOCKER_CONFIG_FILE="/etc/docker/daemon.json"
        MIRROR_ADDRESS="http://119.8.39.15:5000"

        if [ ! -f "$DOCKER_CONFIG_FILE" ]; then
            echo "{}" > "$DOCKER_CONFIG_FILE"
        fi

        if command -v jq >/dev/null 2>&1; then
            jq ".\"registry-mirrors\" = [\"$MIRROR_ADDRESS\"]" "$DOCKER_CONFIG_FILE" > "$DOCKER_CONFIG_FILE.tmp" && mv "$DOCKER_CONFIG_FILE.tmp" "$DOCKER_CONFIG_FILE"
        else
            echo "jq not installed!"
            exit 1
        fi

        sudo systemctl daemon-reload
        sudo systemctl restart docker
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
    local mirrors=("Official" "Official" "AzureChinaCloud" "Aliyun")
    local urls=("https://download.docker.com/linux/centos/docker-ce.repo" "https://download.docker.com/linux/centos/docker-ce.repo" "https://mirror.azure.cn/docker-ce/linux/centos/docker-ce.repo" "https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo")
    local timeout=180
    local max_retries=4
    local retry_count=0

    while ((retry_count < max_retries)); do
        Install_Docker ${mirrors[$retry_count]} $timeout ${urls[$retry_count]}
        if ! docker_exist; then
            echo "Installation timeout or failed, retrying with ${mirrors[$retry_count]} mirror..."
            ((retry_count++))
            sleep 3
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

if [ -z "$execute_mode" ] || [ "$execute_mode" = "install" ]; then
    Start_Docker
fi