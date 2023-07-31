#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/websoft9/issues"' ERR

urls="https://artifact.azureedge.net/release/websoft9"

CheckEnv(){
echo "------------------ Welcome to update websoft9's appstore, it will take 1-3 minutes -----------------"

if [ $(id -u) != "0" ]; then
    echo "Please change to root or 'sudo su' to up system privileges, and  reinstall the script again ."
    exit 1
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

UpdateWebsoft9(){

echo "Update websoft9 ..."

if [ ! -f /data/apps/websoft9/version.json ]; then
    old_version="0.0.0"
else
    old_version=$(cat /data/apps/websoft9/version.json | jq .VERSION | tr -d '"')
fi
release_version=$(curl $urls/version.json | jq .VERSION | tr -d '"')

if [ "$old_version" \< "$release_version" ]; then
    echo "start to update websoft9..."
    cd /data/apps && rm -rf websoft9
    wget $urls/websoft9-latest.zip
    unzip websoft9-latest.zip
    rm -rf websoft9-latest.zip
else
    echo "websoft9 is not need to update"
fi

}

UpdatePlugins(){

echo "Check plugins if have update ..."

# update appstore
old_appstore_version=$(cat /usr/share/cockpit/appstore/appstore.json | jq .Version |  tr -d '"')
new_appstore_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .APPSTORE | tr -d '"')

# update settings
old_settings_version=$(cat /usr/share/cockpit/settings/settings.json | jq .Version |  tr -d '"')
new_settings_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .SETTINGS | tr -d '"')

# update myapps
old_myapps_version=$(cat /usr/share/cockpit/myapps/myapps.json | jq .Version |  tr -d '"')
new_myapps_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .MYAPPS | tr -d '"')

## update container
old_container_version=$(cat /usr/share/cockpit/container/portainer.json | jq .Version |  tr -d '"')
new_container_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .PORTAINER | tr -d '"')

## update nginx
old_nginx_version=$(cat /usr/share/cockpit/nginx/nginx.json | jq .Version |  tr -d '"')
new_nginx_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NGINX | tr -d '"')

## update library
old_library_version=$(cat /data/library/library.json | jq .Version |  tr -d '"')
new_library_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .LIBRARY | tr -d '"')

if [ "$old_appstore_version" = "$new_appstore_version" ] && [ "$old_settings_version" = "$new_settings_version" ] && [ "$old_myapps_version" = "$new_myapp_version" ] && [ "$old_container_version" = "$new_container_version" ] && [ "$old_nginx_version" \< "$new_nginx_version" ]; then
    echo "appstore all plugins is latest"
else

      if [ "$old_appstore_version" \< "$new_appstore_version" ]; then
        echo "appstore plugin need to update"
        cd /usr/share/cockpit
        wget $urls/plugin/appstore/appstore-$new_appstore_version.zip
        rm -rf appstore
        unzip appstore-$new_appstore_version.zip
        rm -f appstore-$new_appstore_version.zip
    else
        echo "appstore is not need to update"
    fi

    if [ "$old_settings_version" \< "$new_settings_version" ]; then
        echo "settings plugin need to update"
        cd /usr/share/cockpit
        wget $urls/plugin/settings/settings-$new_settings_version.zip
        rm -rf settings
        unzip settings-$new_appstore_version.zip
        rm -f settings-$new_appstore_version.zip
    else
        echo "settings is not need to update"
    fi

    if [ "$old_myapps_version" \< "$new_myapps_version" ]; then
        echo "start to update myapps..."
        cd /usr/share/cockpit
        wget $urls/plugin/myapps/myapps-$new_myapps_version.zip
        rm -rf myapps
        unzip myapps-$new_myapps_version.zip
        rm -f myapps-$new_myapps_version.zip
    else
        echo "myapps is not need to update"
    fi

    if [ "$old_container_version" \< "$new_container_version" ]; then
        echo "start  to update portainer..."
        cd /usr/share/cockpit
        wget $urls/plugin/portainer/portainer-$new_container_version.zip
        rm -rf portainer
        unzip portainer-$new_container_version.zip
        rm -f portainer-$new_container_version.zip
    else
        echo "portainer is not need to update"
    fi

    if [ "$old_nginx_version" \< "$new_nginx_version" ]; then
        echo "start to update nginx..."
        cd /usr/share/cockpit
        wget $urls/plugin/nginx/nginx-$new_nginx_version.zip
        rm -rf nginx
        unzip nginx-$new_nginx_version.zip
        rm -f nginx-$new_nginx_version.zip
    else
        echo "nginx is not need to update"
    fi

    if [ "$old_library_version" \< "$new_library_version" ]; then
        echo "start to update library..."
        cd /data
        wget $urls/plugin/library/library-$new_library_version.zip
        rm -rf library
        unzip library-$new_library_version.zip
        rm -f library-$new_library_version.zip
    else
        echo "library is not need to update"
    fi
fi
 
}

UpdateServices(){
echo "Check services if have update ..."
old_appmanage=$(cat /data/apps/w9services/w9appmanage/.env |grep APP_VERSION |cut -d= -f2)
new_appmanage=$(cat /data/apps/websoft9/docker/w9appmanage/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_appmanage" \< "$new_appmanage" ]; then
    echo "start to update w9appmanage..."
    rm -rf /tmp/database.sqlite && sudo docker cp websoft9-appmanage:/usr/src/app/database.sqlite /tmp
    rm -f /data/apps/w9services/w9appmanage/.env && cp /data/apps/websoft9/docker/w9appmanage/.env /data/apps/w9services/w9appmanage/.env
    rm -f /data/apps/w9services/w9appmanage/docker-compose.yml && cp /data/apps/websoft9/docker/w9appmanage/docker-compose.yml /data/apps/w9services/w9appmanage/docker-compose.yml
    cd /data/apps/w9services/w9appmanage  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
    sudo docker exec -it websoft9-appmanage rm -f /usr/src/app/database.sqlite && sudo docker cp /tmp/database.sqlite websoft9-appmanage:/usr/src/app
    docker restart websoft9-appmanage
else
    echo "appmanage is not need to update"
fi

old_redis=$(cat /data/apps/w9services/w9redis/.env |grep APP_VERSION |cut -d= -f2)
new_redis=$(cat /data/apps/websoft9/docker/w9redis/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_redis" \< "$new_redis" ]; then
    echo "start to update w9redis..."
    rm -f /data/apps/w9services/w9redis/.env && cp /data/apps/websoft9/docker/w9redis/.env /data/apps/w9services/w9redis/.env
    rm -f /data/apps/w9services/w9redis/docker-compose.yml && cp /data/apps/websoft9/docker/w9redis/docker-compose.yml /data/apps/w9services/w9redis/docker-compose.yml
    cd /data/apps/w9services/w9redis  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "redis is not need to update"
fi

old_portainer=$(cat /data/apps/w9services/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
new_portainer=$(cat /data/apps/websoft9/docker/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_portainer" \< "$new_portainer" ]; then
    echo "start to update w9portainer..."
    rm -f /data/apps/w9services/w9portainer/.env && cp /data/apps/websoft9/docker/w9portainer/.env /data/apps/w9services/w9portainer/.env
    rm -f /data/apps/w9services/w9portainer/docker-compose.yml && cp /data/apps/websoft9/docker/w9portainer/docker-compose.yml /data/apps/w9services/w9portainer/docker-compose.yml
    cd /data/apps/w9services/w9portainer  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "w9portainer is not need to update"
fi

old_nginx=$(cat /data/apps/w9services/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
new_nginx=$(cat /data/apps/websoft9/docker/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
if [ "$old_nginx" \< "$new_nginx" ]; then
    echo "start to update w9nginx..."
    rm -f /data/apps/w9services/w9nginxproxymanager/.env && cp /data/apps/websoft9/docker/w9nginxproxymanager/.env /data/apps/w9services/w9nginxproxymanager/.env
    rm -f /data/apps/w9services/w9nginxproxymanager/docker-compose.yml && cp /data/apps/websoft9/docker/w9nginxproxymanager/docker-compose.yml /data/apps/w9services/w9nginxproxymanager/docker-compose.yml
    cd /data/apps/w9services/w9nginxproxymanager  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "w9nginx is not need to update"
fi

}

EditMenu(){

echo "Start to  Edit Cockpit Menu ..."
if command -v jq > /dev/null; then
  if [ -e /usr/share/cockpit/systemd ]; then
    rm -f /usr/share/cockpit/systemd/manifest.json.tmp
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

  rm -f /usr/share/cockpit/shell/manifest.json.tmp
  jq  '. | del(.locales."ca-es") | del(.locales."nb-no") | del(.locales."sk-sk") | del(.locales."tr-tr")| del(.locales."cs-cz") | del(.locales."de-de") | del(.locales."es-es") | del(.locales."fi-fi") | del(.locales."fr-fr") | del(.locales."it-it") | del(.locales."ja-jp") | del(.locales."pl-pl") | del(.locales."pt-br") | del(.locales."ru-ru") | del(.locales."sv-se") | del(.locales."uk-ua") | del(.locales."zh-tw") | del(.locales."he-il") | del(.locales."nl-nl")  | del(.locales."ko-kr") | del(.locales."ka-ge")' /usr/share/cockpit/shell/manifest.json > /usr/share/cockpit/shell/manifest.json.tmp
  rm -rf /usr/share/cockpit/shell/manifest.json
  mv /usr/share/cockpit/shell/manifest.json.tmp /usr/share/cockpit/shell/manifest.json
  
else
  echo "system have no jq, use cockpit menu ..."
  if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
    sudo yum install epel-release -y 1>/dev/null 2>&1
    sudo yum install jq -y  1>/dev/null 2>&1
    if [ -e /usr/share/cockpit/systemd ]; then
      rm -f /usr/share/cockpit/systemd/manifest.json.tmp
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
    rm -f /usr/share/cockpit/shell/manifest.json.tmp
    jq  '. | del(.locales."ca-es") | del(.locales."nb-no") | del(.locales."sk-sk") | del(.locales."tr-tr")| del(.locales."cs-cz") | del(.locales."de-de") | del(.locales."es-es") | del(.locales."fi-fi") | del(.locales."fr-fr") | del(.locales."it-it") | del(.locales."ja-jp") | del(.locales."pl-pl") | del(.locales."pt-br") | del(.locales."ru-ru") | del(.locales."sv-se") | del(.locales."uk-ua") | del(.locales."zh-tw") | del(.locales."he-il") | del(.locales."nl-nl")  | del(.locales."ko-kr") | del(.locales."ka-ge")' /usr/share/cockpit/shell/manifest.json > /usr/share/cockpit/shell/manifest.json.tmp
    rm -rf /usr/share/cockpit/shell/manifest.json
    mv /usr/share/cockpit/shell/manifest.json.tmp /usr/share/cockpit/shell/manifest.json
  fi

fi

}

UpdateCockpit(){

echo "Parpare to update Cockpit to latest  ..."
pkcon refresh /dev/null 2>&1
pkcon get-updates >/dev/null 2>&1
pkcon update -y >/dev/null 2>&1

# update navigator(not update on official)
# if command -v apt > /dev/null;then  
#   sudo apt -y install --only-upgrade  cockpit-navigator
# elif  command -v dnf > /dev/null;then 
#   sudo dnf update -y cockpit-navigator
# elif  command -v yum > /dev/null;then 
#   sudo yum update -y cockpit-navigator
# fi
# echo "Set cockpit port to 9000 ..." 
# sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket
# # uninstall plugins
# rm -rf /usr/share/cockpit/apps /usr/share/cockpit/selinux /usr/share/cockpit/kdump /usr/share/cockpit/sosreport /usr/share/cockpit/packagekit
# EditMenu

}

CheckEnv
UpdateDocker
UpdateWebsoft9
UpdatePlugins
UpdateServices
UpdateCockpit