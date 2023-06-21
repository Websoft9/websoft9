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

LibraryUpdate(){
echo "Update appstore library..."
if [ ! -f /data/library/install/version.json ]; then
    old_library_version="0.0.1"
else
    old_library_version=$(cat /data/library/install/version.json | jq .VERSION | tr -d '"')
fi
latest_library_version=$(curl https://websoft9.github.io/docker-library/install/version.json | jq .VERSION | tr -d '"')
if [ "$old_library_version" \< "$latest_library_version" ]; then
    echo "start to update Library..."
    fastest=$(fastest_url "${urls[@]}")
    echo "fasturl is: "$fastest
    cd /tmp && rm -rf /tmp/library
    if [[ $fastest == *gitee.com* ]]; then
        echo "update from gitee"
        wget $fastest/websoft9/docker-library/repository/archive/$latest_library_version
        unzip $latest_library_version
        mv docker-library* library
        rm -f $latest_library_version
    else
        echo "update from github"
        wget $fastest/websoft9/docker-library/archive/refs/tags/$latest_library_version.zip
        unzip $latest_library_version.zip
        mv docker-library* library
        rm -f $latest_library_version.zip
    fi
    rm -rf /data/library && cp -r /tmp/library /data
else
    echo "Library is not need to update"
fi
}
StackhubUpdate(){
echo "Update stackhub ..."
cd /tmp && rm -rf version.json && wget https://websoft9.github.io/StackHub/install/version.json

if [ ! -f /data/apps/stackhub/install/version.json ]; then
    old_version="0.0.1"
else
    old_version=$(cat /data/apps/stackhub/install/version.json | jq .VERSION | tr -d '"')
fi
release_version=$(cat /tmp/version.json | jq .VERSION | tr -d '"')

if [ "$old_version" \< "$release_version" ]; then
    echo "start to update stackhub..."
    fasturl=$(fastest_url "${urls[@]}")
    echo "fasturl is: "$fasturl
    cd /tmp && rm -rf /tmp/stackhub
    if [[ $fasturl == *gitee.com* ]]; then
        wget $fasturl/websoft9/StackHub/repository/archive/$release_version
        unzip $release_version
        mv StackHub* stackhub
        rm -f $release_version
    else
        wget $fasturl/websoft9/StackHub/archive/refs/tags/$release_version.zip
        unzip $release_version.zip
        mv StackHub* stackhub
        rm -f $release_version.zip
    fi
    rm -rf /data/apps/stackhub
    cp -r /tmp/stackhub /data/apps
    
else
    echo "stackhub is not need to update"
fi

}
CheckUpdate(){
echo "------------------ Welcome to update websoft9's appstore, it will take 1-3 minutes -----------------"

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

if command -v apt > /dev/null;then  
  sudo apt -y install --only-upgrade  docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
elif  command -v dnf > /dev/null;then 
  sudo dnf update -y docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
elif  command -v yum > /dev/null;then 
  sudo yum update -y docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin
fi

}

UpdateCockpit(){

echo "Parpare to update Cockpit to latest  ..."
pkcon refresh /dev/null 2>&1
pkcon get-updates >/dev/null 2>&1
pkcon update -y >/dev/null 2>&1

# update navigator
if command -v apt > /dev/null;then  
  sudo apt -y install --only-upgrade  cockpit-navigator
elif  command -v dnf > /dev/null;then 
  sudo dnf update -y cockpit-navigator
elif  command -v yum > /dev/null;then 
  sudo yum update -y cockpit-navigator
fi

}

UpdatePlugins(){

echo "Check plugins if have update ..."

rm -rf /tmp/config.json
cp /usr/share/cockpit/myapps/config.json /tmp/config.json

# update appstore
old_appstore_version=$(cat /usr/share/cockpit/appstore/manifest.json | jq .version)
new_appstore_version=$(cat /data/apps/stackhub/cockpit/appstore/build/manifest.json |jq .version)

# update settings
old_settings_version=$(cat /usr/share/cockpit/settings/manifest.json | jq .version)
new_settings_version=$(cat /data/apps/stackhub/cockpit/settings/build/manifest.json |jq .version)

# update myapps
old_myapps_version=$(cat /usr/share/cockpit/myapps/manifest.json | jq .version)
new_myapp_version=$(cat /data/apps/stackhub/cockpit/myapps/build/manifest.json |jq .version)

## update container
old_container_version=$(cat /usr/share/cockpit/container/manifest.json | jq .version)
new_container_version=$(cat /data/apps/stackhub/cockpit/portainer/build/manifest.json |jq .version)

## update nginx
old_nginx_version=$(cat /usr/share/cockpit/nginx/manifest.json | jq .version)
new_nginx_version=$(cat /data/apps/stackhub/cockpit/nginxproxymanager/build/manifest.json |jq .version)

if [ "$old_appstore_version" = "$new_appstore_version" ] && [ "$old_settings_version" = "$new_settings_version" ] && [ "$old_myapps_version" = "$new_myapp_version" ] && [ "$old_container_version" = "$new_container_version" ] && [ "$old_nginx_version" \< "$new_nginx_version" ]; then
    echo "appstore all plugins is latest"
else

    release_version=$(curl https://websoft9.github.io/stackhub-web/CHANGELOG.md | head -n 1 |cut -d' ' -f2)
    fastest=$(fastest_url "${urls[@]}")
    echo "fasturl is: "$fastest
    cd /tmp && rm -rf /tmp/stackhub-web
    if [[ $fastest == *gitee.com* ]]; then
        echo "update from gitee"
        wget $fastest/websoft9/stackhub-web/repository/archive/$release_version
        unzip $release_version
        mv stackhub-web* stackhub-web
        rm -f $release_version
    else
        echo "update from github"
        wget $fastest/websoft9/stackhub-web/archive/refs/tags/$release_version.zip
        unzip $release_version.zip
        mv stackhub-web* stackhub-web
        rm -f $release_version.zip
    fi
    rm -rf /data/apps/stackhub-web && cp -r /tmp/stackhub-web /data/apps

    if [ "$old_appstore_version" \< "$new_appstore_version" ]; then
        echo "appstore plugin need to update"
        rm -rf /usr/share/cockpit/appstore/*
        cp -r /data/apps/stackhub-web/plugins/appstore/build/* /usr/share/cockpit/appstore
    else
        echo "appstore is not need to update"
    fi

    if [ "$old_settings_version" \< "$new_settings_version" ]; then
        echo "settings plugin need to update"
        rm -rf /usr/share/cockpit/settings/*
        cp -r /data/apps/stackhub-web/plugins/settings/build/* /usr/share/cockpit/settings
    else
        echo "settings is not need to update"
    fi

    if [ "$old_myapps_version" \< "$new_myapp_version" ]; then
        echo "start to update myapps..."
        rm -rf /usr/share/cockpit/myapps/*
        cp -r /data/apps/stackhub-web/plugins/myapps/build/* /usr/share/cockpit/myapps
        rm -f /usr/share/cockpit/myapps/config.json
        cp /tmp/config.json /usr/share/cockpit/myapps/config.json
    else
        echo "myapps is not need to update"
    fi

    if [ "$old_container_version" \< "$new_container_version" ]; then
        echo "start  to update portainer..."
        rm -rf /usr/share/cockpit/container/*
        cp -r /data/apps/stackhub-web/plugins/portainer/build/* /usr/share/cockpit/container
    else
        echo "portainer is not need to update"
    fi

    if [ "$old_nginx_version" \< "$new_nginx_version" ]; then
        echo "start to update nginx..."
        rm -rf /usr/share/cockpit/nginx/*
        cp -r /data/apps/stackhub-web/plugins/nginxproxymanager/build/* /usr/share/cockpit/nginx
    else
        echo "nginx is not need to update"
    fi
fi
 
}

UpdateServices(){
echo "Check services if have update ..."
old_appmanage=$(cat /data/apps/w9services/w9appmanage/.env |grep APP_VERSION |cut -d= -f2)
new_appmanage=$(cat /data/apps/stackhub/docker/w9appmanage/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_appmanage" \< "$new_appmanage" ]; then
    echo "start to update w9appmanage..."
    cp /data/apps/stackhub/docker/w9appmanage/.env /data/apps/w9services/w9appmanage/.env
    cp /data/apps/stackhub/docker/w9appmanage/docker-compose.yml /data/apps/w9services/w9appmanage/docker-compose.yml
    cd /data/apps/w9services/w9appmanage  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "appmanage is not need to update"
fi

old_redis=$(cat /data/apps/w9services/w9redis/.env |grep APP_VERSION |cut -d= -f2)
new_redis=$(cat /data/apps/stackhub/docker/w9redis/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_redis" \< "$new_redis" ]; then
    echo "start to update w9redis..."
    cp /data/apps/stackhub/docker/w9redis/.env /data/apps/w9services/w9redis/.env
    cp /data/apps/stackhub/docker/w9redis/docker-compose.yml /data/apps/w9services/w9redis/docker-compose.yml
    cd /data/apps/w9services/w9redis  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "redis is not need to update"
fi

old_portainer=$(cat /data/apps/w9services/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
new_portainer=$(cat /data/apps/stackhub/docker/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_portainer" \< "$new_portainer" ]; then
    echo "start to update w9portainer..."
    cp /data/apps/stackhub/docker/w9portainer/.env /data/apps/w9services/w9portainer/.env
    cp /data/apps/stackhub/docker/w9portainer/docker-compose.yml /data/apps/w9services/w9portainer/docker-compose.yml
    cd /data/apps/w9services/w9portainer  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "w9portainer is not need to update"
fi

old_nginx=$(cat /data/apps/w9services/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
new_nginx=$(cat /data/apps/stackhub/docker/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_nginx" \< "$new_nginx" ]; then
    echo "start to update w9nginx..."
    cp /data/apps/stackhub/docker/w9nginxproxymanager/.env /data/apps/w9services/w9nginxproxymanager/.env
    cp /data/apps/stackhub/docker/w9nginxproxymanager/docker-compose.yml /data/apps/w9services/w9nginxproxymanager/docker-compose.yml
    cd /data/apps/w9services/w9nginxproxymanager  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "w9nginx is not need to update"
fi

}

CheckUpdate
LibraryUpdate
StackhubUpdate
UpdateDocker
UpdatePlugins
UpdateServices
UpdateCockpit