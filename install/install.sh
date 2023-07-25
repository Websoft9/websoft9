#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/stackhub/issues"' ERR

install_way="online"

urls="https://artifact.azureedge.net/release/websoft9"

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
if netstat -tuln | grep -qE ':(80|9000)\s'; then
    echo "Port 80 or 9000  is already in use."
    exit 1
else
    echo "Port 80, 9000 are free."
fi
          
}

InstallTools(){

echo "Prepare to install Tools ..."

if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'Rocky Linux' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
  sudo yum update -y 1>/dev/null 2>&1
  sudo yum install  git curl wget yum-utils jq bc unzip -y  1>/dev/null 2>&1

fi

if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
  done
  sudo apt update -y 1>/dev/null 2>&1
  if command -v git > /dev/null;then  
    echo "git installed ..."
  else
    sudo apt install git -y
  fi
  if command -v curl > /dev/null;then  
    echo "jcurlq installed ..."
  else
    sudo apt install curl -y
  fi
  if command -v wget > /dev/null;then  
    echo "wget installed ..."
  else
    sudo apt install wget -y
  fi
  if command -v jq > /dev/null;then  
    echo "jq installed ..."
  else
    sudo apt install jq -y
  fi

  if command -v bc > /dev/null;then  
    echo "bc installed ..."
  else
    sudo apt install bc -y
  fi
  if command -v unzip > /dev/null;then  
    echo "unzip installed ..."
  else
    sudo apt install unzip -y
  fi
fi

}

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

InstallCockpit(){
echo "Prepare to install Cockpit ..." 

if [ "${os_type}" == 'Debian' ]; then
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo echo "deb http://deb.debian.org/debian ${VERSION_CODENAME}-backports main" >/etc/apt/sources.list.d/backports.list
  sudo apt update
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  sudo apt install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
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
  sudo yum install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --permanent --zone=public --add-service=cockpit
  sudo firewall-cmd --reload
fi

if [ "$os_type" == 'Fedora' ]; then
  sudo dnf install cockpit -y 
  sudo dnf install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'Redhat' ] ; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo yum install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
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

file="/etc/cockpit/disallowed-users"

if [ -f "$file" ]; then
    echo "" > "$file"
else
    echo "$file is not exist"
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

# uninstall plugins
rm -rf /usr/share/cockpit/apps /usr/share/cockpit/selinux /usr/share/cockpit/kdump /usr/share/cockpit/sosreport /usr/share/cockpit/packagekit

}

InstallPlugins(){

# download apps
mkdir -p /data/apps && cd /data/apps
wget $urls/websoft9-latest.zip
unzip websoft9-latest.zip
cp -r /data/apps/websoft9/docker  /data/apps/w9services
rm -f websoft9-latest.zip

# install plugins
cd /usr/share/cockpit
appstore_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .APPSTORE | tr -d '"')
wget $urls/plugin/appstore-$appstore_version.zip
unzip appstore-$appstore_version.zip

myapps_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .MYAPPS| tr -d '"')
wget $urls/plugin/myapps-$myapps_version.zip
unzip myapps-$myapps_version.zip

portainer_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .PORTAINER | tr -d '"')
wget $urls/plugin/portainer-$portainer_version.zip
unzip portainer-$portainer_version.zip

nginx_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NGINX | tr -d '"')
wget $urls/plugin/nginx-$nginx_version.zip
unzip nginx-$nginx_version.zip

# settings_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .SETTINGS | tr -d '"')
# wget https://w9artifact.blob.core.windows.net/release/websoft9/plugin/settings-$settings_version.zip
# unzip settings-$settings_version.zip
rm -f *.zip

# install library
cd /data
library_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .LIBRARY | tr -d '"')
wget $urls/plugin/library-$library_version.zip
unzip library-$library_version.zip
rm -f library-$library_version.zip

echo "Set cockpit port to 9000 ..." 
sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket

# configure cockpit
cp /data/apps/websoft9/cockpit/cockpit.conf /etc/cockpit/cockpit.conf

#####ci-section#####

#sudo systemctl restart cockpit
sudo systemctl daemon-reload
sudo systemctl enable --now cockpit.socket
#sudo systemctl enable --now cockpit
sudo systemctl restart cockpit.socket
#sudo systemctl restart cockpit

}

StartAppMng(){

echo "Start appmanage API ..." 
cd /data/apps/w9services/w9redis  && sudo docker compose up -d
cd /data/apps/w9services/w9appmanage  && sudo docker compose up -d

public_ip=`bash /data/apps/websoft9/scripts/get_ip.sh`
echo $public_ip > /data/apps/w9services/w9appmanage/public_ip
appmanage_ip=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-appmanage)
}

StartPortainer(){

echo "Start Portainer ..." 
cd /data/apps/w9services/w9portainer  && sudo docker compose up -d
docker pull backplane/pwgen
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
portainer_ip=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-portainer)
#echo "Portainer init password:" $new_password
curl -X POST -H "Content-Type: application/json" -d '{"username":"admin", "Password":"'$new_password'"}' http://$portainer_ip:9000/api/users/admin/init
curl "http://$appmanage_ip:5000/AppUpdateUser?user_name=admin&password=$new_password"

}

InstallNginx(){

echo "Install nginxproxymanager ..." 
cd /data/apps/w9services/w9nginxproxymanager && sudo docker compose up -d
sleep 30
echo "edit nginxproxymanager password..." 
nginx_ip=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-nginxproxymanager)
login_data=$(curl -X POST -H "Content-Type: application/json" -d '{"identity":"admin@example.com","scope":"user", "secret":"changeme"}' http://$nginx_ip:81/api/tokens)
#token=$(echo $login_data | grep -Po '(?<="token":")[^"]*')
token=$(echo $login_data | jq -r '.token')
while [ -z "$token" ]; do
    sleep 5
    login_data=$(curl -X POST -H "Content-Type: application/json" -d '{"identity":"admin@example.com","scope":"user", "secret":"changeme"}' http://$nginx_ip:81/api/tokens)
    token=$(echo $login_data | jq -r '.token')
done
echo "Nginx token:"$token
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
#echo "Nginx init password:" $new_password
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"email": "help@websoft9.com", "nickname": "admin", "is_disabled": false, "roles": ["admin"]}'  http://$nginx_ip:81/api/users/1
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"type":"password","current":"changeme","secret":"'$new_password'"}'  http://$nginx_ip:81/api/users/1/auth
sleep 3
curl "http://$appmanage_ip:5000/AppUpdateUser?user_name=help@websoft9.com&password=$new_password"
echo "edit password success ..." 
while [ ! -d "/var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host" ]; do
    sleep 1
done
cp /data/apps/w9services/w9nginxproxymanager/initproxy.conf /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host
echo $public_ip
sudo sed -i "s/domain.com/$public_ip/g" /var/lib/docker/volumes/w9nginxproxymanager_nginx_data/_data/nginx/proxy_host/initproxy.conf
sudo docker restart websoft9-nginxproxymanager
}

EditMenu(){

echo "Start to  Edit Cockpit Menu ..."
if command -v jq > /dev/null; then
  if [ -e /usr/share/cockpit/systemd ]; then
    jq  '. | .tools as $menu | .menu as $tools | .tools=$tools | .menu=$menu | del(.tools.services) | del(.menu.preload.services) | .menu.index = .tools.index | del(.tools.index) | .menu.index.order = -2' /usr/share/cockpit/systemd/manifest.json > /usr/share/cockpit/systemd/manifest.json.tmp
    rm -rf /usr/share/cockpit/systemd/manifest.json
    mv /usr/share/cockpit/systemd/manifest.json.tmp /usr/share/cockpit/systemd/manifest.json
    cd /usr/share/cockpit/systemd && rm -rf services.js.gz services.html.gz services.css.gz services.js services.html services.css
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

  jq  '. | del(.locales."ca-es") | del(.locales."nb-no") | del(.locales."sk-sk") | del(.locales."tr-tr")| del(.locales."cs-cz") | del(.locales."de-de") | del(.locales."es-es") | del(.locales."fi-fi") | del(.locales."fr-fr") | del(.locales."it-it") | del(.locales."ja-jp") | del(.locales."pl-pl") | del(.locales."pt-br") | del(.locales."ru-ru") | del(.locales."sv-se") | del(.locales."uk-ua") | del(.locales."zh-tw") | del(.locales."he-il") | del(.locales."nl-nl")  | del(.locales."ko-kr") | del(.locales."ka-ge")' /usr/share/cockpit/shell/manifest.json > /usr/share/cockpit/shell/manifest.json.tmp
  rm -rf /usr/share/cockpit/shell/manifest.json
  mv /usr/share/cockpit/shell/manifest.json.tmp /usr/share/cockpit/shell/manifest.json
else
  echo "system have no jq, use cockpit menu ..."
  if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
    sudo yum install epel-release -y 1>/dev/null 2>&1
    sudo yum install jq -y  1>/dev/null 2>&1
    if [ -e /usr/share/cockpit/systemd ]; then
      jq  '. | .tools as $menu | .menu as $tools | .tools=$tools | .menu=$menu | del(.tools.services) | del(.menu.preload.services) | .menu.index = .tools.index | del(.tools.index) | .menu.index.order = -2' /usr/share/cockpit/systemd/manifest.json > /usr/share/cockpit/systemd/manifest.json.tmp
      rm -rf /usr/share/cockpit/systemd/manifest.json
      mv /usr/share/cockpit/systemd/manifest.json.tmp /usr/share/cockpit/systemd/manifest.json
      cd /usr/share/cockpit/systemd && rm -rf services.js.gz services.html.gz services.css.gz
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

    jq  '. | del(.locales."ca-es") | del(.locales."nb-no") | del(.locales."sk-sk") | del(.locales."tr-tr")| del(.locales."cs-cz") | del(.locales."de-de") | del(.locales."es-es") | del(.locales."fi-fi") | del(.locales."fr-fr") | del(.locales."it-it") | del(.locales."ja-jp") | del(.locales."pl-pl") | del(.locales."pt-br") | del(.locales."ru-ru") | del(.locales."sv-se") | del(.locales."uk-ua") | del(.locales."zh-tw") | del(.locales."he-il") | del(.locales."nl-nl")  | del(.locales."ko-kr") | del(.locales."ka-ge")' /usr/share/cockpit/shell/manifest.json > /usr/share/cockpit/shell/manifest.json.tmp
    rm -rf /usr/share/cockpit/shell/manifest.json
    mv /usr/share/cockpit/shell/manifest.json.tmp /usr/share/cockpit/shell/manifest.json
  fi

fi

echo "---------------------------------- Install success!  you can  install a app by websoft9's appstore -------------------------------------------------------" 
}

CheckEnvironment
InstallTools
InstallDocker
InstallCockpit
InstallPlugins
StartAppMng
StartPortainer
InstallNginx
EditMenu