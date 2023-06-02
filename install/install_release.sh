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
    https://github.com
    https://gitee.com
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

CheckEnvironment(){

echo "---------------------------------- Welcome to install websoft9's appstore, it will take 3-5 minutes -------------------------------------------------------" 

echo "Check  environment ..."
echo  os_type: $os_type
echo  os_version: $os_version
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

# Check port used
if netstat -tuln | grep -qE ':(80|9000|5000)\s'; then
    echo "Port 80 or 9000 or 5000 is already in use."
    exit 1
else
    echo "Port 80, 9000 and 5000 are free."
fi
          
}

InstallTools(){

echo "Prepare to install Tools ..."

if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
  sudo yum update -y 1>/dev/null 2>&1
  sudo yum install  git curl wget yum-utils jq firewalld -y  1>/dev/null 2>&1

fi

if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
  done
  sudo apt update -y 1>/dev/null 2>&1
  sudo apt install git curl wget jq firewalld -y  1>/dev/null 2>&1
fi

}

InstallDocker(){

echo "Prepare to install Docker ..."

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

InstallCockpit(){
echo "Prepare to install Cockpit ..." 

if [ "${os_type}" == 'Debian' ]; then
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo echo "deb http://deb.debian.org/debian ${VERSION_CODENAME}-backports main" >/etc/apt/sources.list.d/backports.list
  sudo apt update
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  sudo apt install cockpit-pcp -y 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'Ubuntu' ]; then
  if grep -q "^#.*deb http://mirrors.tencentyun.com/ubuntu.*backports" /etc/apt/sources.list; then
      echo "Add backports deb ..." 
      sudo sed -i 's/^#\(.*deb http:\/\/mirrors.tencentyun.com\/ubuntu.*backports.*\)/\1/' /etc/apt/sources.list
      apt update
  fi
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  sudo apt install cockpit-pcp -y 1>/dev/null 2>&1
  echo "Cockpit allow root user" 
  echo "" >/etc/cockpit/disallowed-users 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'CentOS' ] || [ "$os_type" == 'OracleLinux' ]; then
  sudo yum install cockpit -y 
  sudo yum install cockpit-pcp -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --permanent --zone=public --add-service=cockpit
  sudo firewall-cmd --reload
fi

if [ "$os_type" == 'Fedora' ]; then
  sudo dnf install cockpit -y 
  sudo dnf install cockpit-pcp -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'Redhat' ] ; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo yum install cockpit-pcp -y 1>/dev/null 2>&1
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'CentOS Stream' ]; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo yum install cockpit-pcp -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  
fi

echo "Set cockpit port to 9000 ..." 
sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket

# install plugins
# install appstore
cp -r /data/apps/stackhub/appmanage/static/images /data/apps/stackhub/cockpit/appstore/static
cp -r /data/apps/stackhub/cockpit/appstore /usr/share/cockpit
# install portainer
cp -r /data/apps/stackhub/cockpit/portainer /usr/share/cockpit
mv /usr/share/cockpit/portainer /usr/share/cockpit/container
## install nginx
cp -r /data/apps/stackhub/cockpit/nginxproxymanager /usr/share/cockpit
mv /usr/share/cockpit/nginxproxymanager /usr/share/cockpit/nginx
## install kopia
cp -r /data/apps/stackhub/cockpit/kopia /usr/share/cockpit
mv /usr/share/cockpit/kopia /usr/share/cockpit/backup
## install myapps
cp -r /data/apps/stackhub/cockpit/myapps /usr/share/cockpit

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

# uninstall plugins
rm -rf /usr/share/cockpit/apps /usr/share/cockpit/selinux /usr/share/cockpit/kdump /usr/share/cockpit/sosreport

# configure cockpit
cp /data/apps/stackhub/cockpit/cockpit.conf /etc/cockpit/cockpit.conf

sudo systemctl daemon-reload
sudo systemctl enable --now cockpit
sudo systemctl enable --now cockpit.socket
sudo systemctl restart cockpit.socket
sudo systemctl restart cockpit

}

function fastest_url() {
  urls=("$@")
  fastest_url=""
  fastest_time=0

  for url in "${urls[@]}"; do
    time=$(curl --connect-timeout 3 -s -w '%{time_total}\n' -o /dev/null $url)
    if (( $(echo "$time < $fastest_time || $fastest_time == 0" | bc -l) )); then
      fastest_time=$time
      fastest_url=$url
    fi
  done

  echo "$fastest_url"
}

function clone_repo() {
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
    if [ ! -d "$path" ]; then
      echo "$path clone failed."
      exit 1
    fi
}

PrepareStaticFiles(){

echo "Prepare to install ..." 
fasturl=$(fastest_url "${urls[@]}")
echo "fast url is: "$fasturl

# download apps
mkdir -p /data/apps
clone_repo $fasturl/Websoft9/docker-library /data/library
clone_repo $fasturl/Websoft9/StackHub /data/apps/stackhub
}

StartAppMng(){

echo "Start appmanage API ..." 
cd /data/apps/stackhub/docker/w9redis  && sudo docker compose up -d
cd /data/apps/stackhub/docker/w9appmanage  && sudo docker compose up -d

public_ip=`bash /data/apps/stackhub/scripts/get_ip.sh`
echo $public_ip > /data/apps/stackhub/docker/w9appmanage/public_ip

}

StartPortainer(){

echo "Start Portainer ..." 
cd /data/apps/stackhub/docker/w9portainer  && sudo docker compose up -d
docker pull backplane/pwgen
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
sudo sed -i 's/"PORTAINER_USERNAME": ".*"/"PORTAINER_USERNAME": "admin"/g' /usr/share/cockpit/appstore/config.json
sudo sed -i 's/"PORTAINER_PASSWORD": ".*"/"PORTAINER_PASSWORD": "'$new_password'"/g' /usr/share/cockpit/appstore/config.json
curl -X POST -H "Content-Type: application/json" -d '{"username":"admin", "Password":"'$new_password'"}' http://127.0.0.1:9091/api/users/admin/init
}

StartKopia(){

echo "Start Kopia ..."
docker pull backplane/pwgen
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
sudo sed -i "s/POWER_PASSWORD=.*/POWER_PASSWORD=$new_password/g" /data/apps/stackhub/docker/w9kopia/.env
cd /data/apps/stackhub/docker/w9kopia  && sudo docker compose up -d

sudo sed -i 's/"KOPIA_USERNAME": ".*"/"KOPIA_USERNAME": "admin"/g' /usr/share/cockpit/appstore/config.json
sudo sed -i 's/"KOPIA_PASSWORD": ".*"/"KOPIA_PASSWORD": "'$new_password'"/g' /usr/share/cockpit/appstore/config.json
}

InstallNginx(){

echo "Install nginxproxymanager ..." 
cd /data/apps/stackhub/docker/w9nginxproxymanager && sudo docker compose up -d
sleep 25
echo "edit nginxproxymanager password..." 
login_data=$(curl -X POST -H "Content-Type: application/json" -d '{"identity":"admin@example.com","scope":"user", "secret":"changeme"}' http://127.0.0.1:9092/api/tokens)
sleep 3
token=$(echo $login_data | jq -r '.token')
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"email": "help@websoft9.com", "nickname": "admin", "is_disabled": false, "roles": ["admin"]}'  http://127.0.0.1:9092/api/users/1
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"type":"password","current":"changeme","secret":"'$new_password'"}'  http://127.0.0.1:9092/api/users/1/auth
sleep 3
sudo sed -i 's/"NGINXPROXYMANAGER_USERNAME": ".*"/"NGINXPROXYMANAGER_USERNAME": "help@websoft9.com"/g' /usr/share/cockpit/appstore/config.json
sudo sed -i 's/"NGINXPROXYMANAGER_PASSWORD": ".*"/"NGINXPROXYMANAGER_PASSWORD": "'$new_password'"/g' /usr/share/cockpit/appstore/config.json
sudo sed -i 's/"NGINXPROXYMANAGER_NIKENAME": ".*"/"NGINXPROXYMANAGER_NIKENAME": "admin"/g' /usr/share/cockpit/appstore/config.json
echo "edit password success ..." 
while [ ! -d "/var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host" ]; do
    sleep 1
done
cp /data/apps/stackhub/docker/w9nginxproxymanager/initproxy.conf /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host
public_ip=`bash /data/apps/stackhub/scripts/get_ip.sh`
sudo sed -i "s/domain.com/$public_ip/g" /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host/initproxy.conf

echo "Add htpasswd for appmanage ..."
sudo sed -i 's/"APPMANAGE_USERNAME": ".*"/"APPMANAGE_USERNAME": "websoft9"/g' /usr/share/cockpit/appstore/config.json
sudo sed -i 's/"APPMANAGE_PASSWORD": ".*"/"APPMANAGE_PASSWORD": "'$new_password'"/g' /usr/share/cockpit/appstore/config.json
rm -rf /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host/.htpasswd /tmp/.htpasswd
docker run --rm --volume /tmp:/work backplane/htpasswd -c -b .htpasswd websoft9 $new_password
cp /tmp/.htpasswd /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host/.htpasswd
sudo docker restart websoft9-nginxproxymanager

}

EditMenu(){

echo "Start to  Edit Cockpit Menu ..."
if [ -e /usr/share/cockpit/systemd ]; then
  jq  '. | .tools as $menu | .menu as $tools | .tools=$tools | .menu=$menu' /usr/share/cockpit/systemd/manifest.json > /usr/share/cockpit/systemd/manifest.json.tmp
  rm -rf /usr/share/cockpit/systemd/manifest.json
  mv /usr/share/cockpit/systemd/manifest.json.tmp /usr/share/cockpit/systemd/manifest.json
fi
if [ -e /usr/share/cockpit/networkmanager ]; then
  sudo sed -i 's/menu/tools/g' /usr/share/cockpit/networkmanager/manifest.json
fi
if [ -e /usr/share/cockpit/storaged ]; then
  sudo sed -i 's/menu/tools/g' /usr/share/cockpit/storaged/manifest.json
fi
if [ -e /usr/share/cockpit/users ]; then
  sudo sed -i 's/menu/tools/g' /usr/share/cockpit/users/manifest.json
fi

echo "---------------------------------- Install success!  you can  install a app by websoft9's appstore -------------------------------------------------------" 

}

CheckEnvironment
InstallTools
InstallDocker
PrepareStaticFiles
InstallCockpit
StartAppMng
StartPortainer
StartKopia
InstallNginx
EditMenu