#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH


InstallDocker(){

if command -v docker &> /dev/null
then
    echo "Docker is installed, update..."
    if command -v apt > /dev/null;then  
      sudo apt -y install --only-upgrade  docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
    elif  command -v dnf > /dev/null;then 
      sudo dnf update -y docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
    elif  command -v yum > /dev/null;then 
      sudo yum update -y docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
    fi
    sudo systemctl start docker
    sudo systemctl enable docker
    if ! docker network inspect websoft9 > /dev/null 2>&1; then
      sudo docker network create websoft9
    fi
    return
else
    echo "Docker is not installed, start to install..."
fi
if [ "$os_type" == 'CentOS' ];then
  curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
fi

if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  apt-get update
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
  done
  curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
  sleep 30
fi

if [ "$os_type" == 'OracleLinux' ] ;then
  sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo yum install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
fi

if [ "$os_type" == 'Fedora' ] ;then
  wget -O /etc/yum.repos.d/docker-ce.repo https://download.docker.com/linux/fedora/docker-ce.repo
  sudo yum install device-mapper-persistent-data lvm2 docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-scan-plugin docker-ce-rootless-extras -y
fi

if [ "$os_type" == 'Redhat' ] ;then
  sudo yum remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine podman runc -y 1>/dev/null 2>&1
  sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo yum install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
fi

if [ "$os_type" == 'CentOS Stream' ] || [ "$os_type" == 'Rocky Linux' ];then
  sudo yum remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine podman runc -y 1>/dev/null 2>&1
  wget -O /etc/yum.repos.d/docker-ce.repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo yum install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
fi

sudo systemctl start docker
sudo systemctl enable docker
if ! docker network inspect websoft9 > /dev/null 2>&1; then
  sudo docker network create websoft9
fi

}

InstallDocker