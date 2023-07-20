#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/stackhub/issues"' ERR

install_way=$1

urls=(
    https://ghproxy.com/https://github.com
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
  sudo yum install  git curl wget yum-utils jq firewalld bc unzip -y  1>/dev/null 2>&1

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
  if command -v firewalld > /dev/null;then  
    echo "firewalld installed ..."
  else
    sudo apt install firewalld -y
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

echo "Set cockpit port to 9000 ..." 
sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket

# install plugins
if [ "${install_way}" == 'online' ] ;then
    # install appstore
    mkdir /usr/share/cockpit/appstore
    cp -r /data/apps/plugin-appstore/build/* /usr/share/cockpit/appstore
    cp -r /data/apps/plugin-appstore/data /usr/share/cockpit/appstore/static/

    # install portainer
    mkdir /usr/share/cockpit/container
    cp -r /data/apps/plugin-portainer/build/* /usr/share/cockpit/container

    ## install nginx
    mkdir /usr/share/cockpit/nginx
    cp -r /data/apps/plugin-nginx/build/* /usr/share/cockpit/nginx

    ## install settings
    mkdir /usr/share/cockpit/settings
    cp -r /data/apps/plugin-settings/build/* /usr/share/cockpit/settings

    ## install myapps
    mkdir /usr/share/cockpit/myapps
    cp -r /data/apps/plugin-myapps/build/* /usr/share/cockpit/myapps
    cp -r /data/apps/plugin-myapps/logos /usr/share/cockpit/appstore/static/
    rm -rf /data/apps/plugin-*
else
    echo "install from artifact"
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

# configure cockpit
if [ "${install_way}" == 'online' ] ;then
    cp /data/apps/websoft9/cockpit/cockpit.conf /etc/cockpit/cockpit.conf
else
    echo "install from artifact"
fi 


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
    if curl --output /dev/null --silent --head --fail --max-time 3 "$url"; then
        data="url is available"
    else
        continue
    fi 
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
        git clone --depth=1 $url $path
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
if [ -z "$fasturl" ]; then
  fasturl="https://ghproxy.com/https://github.com"
fi
# download apps
mkdir -p /data/apps

if [ "${install_way}" == 'online' ] ;then
    clone_repo $fasturl/Websoft9/docker-library /data/library
    clone_repo $fasturl/Websoft9/websoft9 /data/apps/websoft9
    clone_repo $fasturl/Websoft9/plugin-appstore /data/apps/plugin-appstore
    clone_repo $fasturl/Websoft9/plugin-myapps /data/apps/plugin-myapps
    clone_repo $fasturl/Websoft9/plugin-portainer /data/apps/plugin-portainer
    clone_repo $fasturl/Websoft9/plugin-settings /data/apps/plugin-settings
    clone_repo $fasturl/Websoft9/plugin-nginx /data/apps/plugin-nginx
    cp -r /data/apps/websoft9/docker  /data/apps/w9services
else
    echo "install from artifact"
fi 

}

StartAppMng(){

echo "Start appmanage API ..." 
cd /data/apps/w9services/w9redis  && sudo docker compose up -d
cd /data/apps/w9services/w9appmanage  && sudo docker compose up -d

if [ "${install_way}" == 'online' ] ;then
    public_ip=`bash /data/apps/websoft9/scripts/get_ip.sh`
else
    public_ip=`curl https://websoft9.github.io/websoft9/scripts/get_ip.sh |bash`
fi 
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
echo "Portainer init password:" $new_password
curl -X POST -H "Content-Type: application/json" -d '{"username":"admin", "Password":"'$new_password'"}' http://$portainer_ip:9000/api/users/admin/init
curl "http://$appmanage_ip:5000/AppUpdateUser?user_name=admin&password=$new_password"

}

InstallNginx(){

echo "Install nginxproxymanager ..." 
cd /data/apps/w9services/w9nginxproxymanager && sudo docker compose up -d
sleep 25
echo "edit nginxproxymanager password..." 
nginx_ip=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-nginxproxymanager)
login_data=$(curl -X POST -H "Content-Type: application/json" -d '{"identity":"admin@example.com","scope":"user", "secret":"changeme"}' http://$nginx_ip:81/api/tokens)
#token=$(echo $login_data | grep -Po '(?<="token":")[^"]*')
token=$(echo $login_data | jq -r '.token')
echo "Nginx token:"$token
new_password=$(docker run --name pwgen backplane/pwgen 15)!
docker rm -f pwgen
echo "Nginx init password:" $new_password
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
PrepareStaticFiles
InstallCockpit
StartAppMng
StartPortainer
InstallNginx
EditMenu