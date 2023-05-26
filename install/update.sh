#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/StackHub/issues"' ERR

urls=(
    https://ghproxy.com/https://github.com
    #https://github.com
)

function get_os_type() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
    else
        OS=$(uname -s)
    fi

    if [[ "$OS" == "CentOS Linux" ]]; then
        echo "CentOS"
    elif [[ "$OS" == "Oracle Linux Server" ]]; then
        echo "OracleLinux"
    elif [[ "$OS" == "Debian GNU/Linux" ]]; then
        echo "Debian"
    elif [[ "$OS" == "Ubuntu" ]]; then
        echo "Ubuntu"
    elif [[ "$OS" == "Fedora Linux" ]]; then
        echo "Fedora"
    elif [[ "$OS" =~  "Red Hat Enterprise Linux" ]]; then
        echo "Redhat"
    else
        echo $OS
    fi
}

function get_os_version() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VERSION=$(lsb_release -sr)
    else
        OS=$(uname -s)
        VERSION=$(uname -r)
    fi

    if [[ "$OS" == "CentOS Linux" && "$VERSION" =~ ^7|8$ ]]; then
        echo "CentOS"$VERSION
    elif [[ "$OS" == "Oracle Linux Server" && "$VERSION" =~ ^7|8$ ]]; then
        echo "OracleLinux"$VERSION
    elif [[ "$OS" == "Debian GNU/Linux" && "$VERSION" =~ ^9|10|11$ ]]; then
        echo "Debian"$VERSION
    elif [[ "$OS" == "Ubuntu" && "$VERSION" =~ ^20.04|20.10|21.04|21.10|22.04$ ]]; then
        echo "Ubuntu"$VERSION
    elif [[ "$OS" =~ "Red Hat Enterprise Linux" && "$VERSION" =~ ^7|8$ ]]; then
        echo "Redhat"$VERSION
    else
        echo $OS $VERSION
    fi
}
os_type=$(get_os_type)
os_version=$(get_os_version)

CheckUpdate(){

echo "Update appstore library ..."
cd /data/library && git pull
cd /tmp && rm -rf install.sh && wget https://websoft9.github.io/StackHub/install/version.json
old_version=$(cat /data/apps/stackhub/install/version.json)
latest_version=$(cat /tmp/version.json)
if [ "$old_version" = "$latest_version" ]
then
    echo "------------------ Your plugins and service is latest, it not need to update ------------------ "
    exit 1
else
    echo "------------------ Welcome to update websoft9's appstore, it will take 1-3 minutes -----------------"
fi

if [ $(id -u) != "0" ]; then
    echo "Please change to root or 'sudo su' to up system privileges, and  reinstall the script again ."
    exit 1
fi

if [ $(getconf WORD_BIT) = '32' ] && [ $(getconf LONG_BIT) = '64' ] ; then
    echo "64-bit operating system detected."
else
    echo "This script only works on 64-bit operating systems."
    exit 1
fi

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VERSION=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -si)
    VERSION=$(lsb_release -sr)
else
    OS=$(uname -s)
    VERSION=$(uname -r)
fi

if [[ "$OS" == "CentOS Linux" && "$VERSION" =~ ^[0-6]$ ]]; then
    echo "This script only works on CentOS 7 or later."
    exit 1
elif [[ "$OS" == "Ubuntu" && "$VERSION" =~ ^1[0-9].*$ ]]; then
    echo "This script only works on Ubuntu 20.04 or later."
    exit 1
elif [[ "$OS" == "Debian GNU/Linux" && "$VERSION" =~ ^[1-8]$ ]]; then
    echo "This script only works on Debian 9 or later."
    exit 1
elif [[ "$OS" =~ "Red Hat Enterprise Linux" && "$VERSION" =~ ^[0-6]$ ]]; then
    echo "This script only works on Red Hat 7 or later."
    exit 1
else
    echo "Your server os is supported to install this software."
fi

echo "Update Linux packate to latest ..."

if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
  sudo yum update -y 1>/dev/null 2>&1
fi

if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
  done
  sudo apt update -y 1>/dev/null 2>&1
fi
       
}

UpdateDocker(){

echo "Parpare to update Docker to latest  ..."

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

if [ "$os_type" == 'CentOS Stream' ] ;then
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

UpdateCockpit(){

echo "Parpare to update Cockpit to latest  ..."
if [ "${os_type}" == 'Debian' ]; then
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo echo "deb http://deb.debian.org/debian ${VERSION_CODENAME}-backports main" >/etc/apt/sources.list.d/backports.list
  sudo apt update
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
fi

if [ "${os_type}" == 'Ubuntu' ]; then
  if grep -q "^#.*deb http://mirrors.tencentyun.com/ubuntu.*backports" /etc/apt/sources.list; then
      echo "Add backports deb ..." 
      sudo sed -i 's/^#\(.*deb http:\/\/mirrors.tencentyun.com\/ubuntu.*backports.*\)/\1/' /etc/apt/sources.list
      apt update
  fi
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  echo "Cockpit allow root user" 
  echo "" >/etc/cockpit/disallowed-users 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'CentOS' ] || [ "$os_type" == 'OracleLinux' ]; then
  sudo yum install cockpit -y 
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --permanent --zone=public --add-service=cockpit
  sudo firewall-cmd --reload
fi

if [ "$os_type" == 'Fedora' ]; then
  sudo dnf install cockpit -y 
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'Redhat' ] ; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'CentOS Stream' ]; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  
fi

# install navigator
if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  wget -qO - https://repo.45drives.com/key/gpg.asc | sudo gpg --dearmor -o /usr/share/keyrings/45drives-archive-keyring.gpg
  cd /etc/apt/sources.list.d
  sudo curl -sSL https://repo.45drives.com/lists/45drives.sources -o /etc/apt/sources.list.d/45drives.sources
  sudo apt update
  sudo apt install cockpit-navigator -y 
fi

if [ "$os_type" == 'Redhat' ] || [ "$os_type" == 'CentOS Stream' ] || [ "$os_type" == 'Fedora' ] ;then
  curl -sSL https://repo.45drives.com/setup -o setup-repo.sh
  sudo bash setup-repo.sh
  sudo dnf install cockpit-navigator -y 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'CentOS' ] || [ "$os_type" == 'OracleLinux' ] ;then
  curl -sSL https://repo.45drives.com/setup -o setup-repo.sh
  sudo bash setup-repo.sh
  sudo yum install cockpit-navigator -y 1>/dev/null 2>&1
fi
}

function fastest_url() {
  urls=("$@")
  fastest_url=""
  fastest_time=0

  for url in "${urls[@]}"; do
    time=$(curl -s -w '%{time_total}\n' -o /dev/null $url)
    if (( $(echo "$time < $fastest_time || $fastest_time == 0" | bc -l) )); then
      fastest_time=$time
      fastest_url=$url
    fi
  done

  echo "$fastest_url"
}

clone_repo() {
    url=$1
    path=$2
    for i in {1..5}
    do
        git clone $url $path
        if [ $? -eq 0 ]
        then
            echo "Clone successful"
            break
        else
            echo "Clone failed, retrying $i/5"
        fi
    done
}

ParpareStaticFiles(){

echo "Parpare to update cockpit plugin ..." 
fasturl=$(fastest_url "${urls[@]}")
echo "Fast url is: "$fasturl

clone_repo $fasturl/Websoft9/docker-library /data/library
clone_repo $fasturl/Websoft9/Stackhub /data/apps/stackhub
clone_repo $fasturl/Websoft9/stackhub-web /data/stackhubweb

}


UpdatePlugins(){
echo "Check plugins if have update ..."
rm -rf /tmp/config.json
cp /usr/share/cockpit/appstore/config.json /tmp/config.json
rm -rf /data/library /data/apps/stackhub /data/stackhubweb 
rm -rf /usr/share/cockpit/appstore/* /usr/share/cockpit/container/* /usr/share/cockpit/nginx/* /usr/share/cockpit/backup/*

ParpareStaticFiles

# install web
cp -r /data/apps/stackhub/appmanage/static/images /data/stackhubweb/src/apps/build/static
cp -r /data/stackhubweb/src/apps/build/* /usr/share/cockpit/appstore
rm -f /usr/share/cockpit/appstore/config.json
cp /tmp/config.json /usr/share/cockpit/appstore/config.json
## install container
cp -r /data/stackhubweb/plugins/portainer/build/* /usr/share/cockpit/container
cp -r /data/stackhubweb/plugins/nginxproxymanager/build/* /usr/share/cockpit/nginx
cp -r /data/stackhubweb/plugins/kopia/build/* /usr/share/cockpit/backup
 
}

UpdateServices(){
echo "Check services if have update ..."
cd /data/apps/stackhub/docker/w9appmanage  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
cd /data/apps/stackhub/docker/w9redis  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
cd /data/apps/stackhub/docker/w9portainer  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
cd /data/apps/stackhub/docker/w9nginxproxymanager  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
old_password=$(cat /usr/share/cockpit/appstore/config.json | jq -r '.KOPIA.KOPIA_PASSWORD')
sudo sed -i 's/POWER_PASSWORD=.*/POWER_PASSWORD="'$old_password'"/g' /data/apps/stackhub/docker/w9kopia/.env
cd /data/apps/stackhub/docker/w9kopia  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
}

CheckUpdate
UpdateDocker
UpdateCockpit
UpdatePlugins
UpdateServices
