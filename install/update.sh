#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/websoft9/issues"' ERR

urls="https://w9artifact.blob.core.windows.net/release/websoft9"
if [[ "$1" == "dev" ]]; then
    echo "update by dev artifacts"
    urls="https://w9artifact.blob.core.windows.net/dev/websoft9"
fi

CheckEnv(){
echo "------------------ Welcome to update websoft9's appstore, it will take 1-3 minutes -----------------"

if [ $(id -u) != "0" ]; then
    echo "Please change to root or 'sudo su' to up system privileges, and  reinstall the script again ."
    exit 1
fi
       
}

compare_versions() {
    local old_version="$1"
    local new_version="$2"

    IFS='.' read -ra old_parts <<< "$old_version"
    IFS='.' read -ra new_parts <<< "$new_version"

    for i in "${!old_parts[@]}"; do
        if [[ ${old_parts[i]} -lt ${new_parts[i]} ]]; then
            return 0
        elif [[ ${old_parts[i]} -gt ${new_parts[i]} ]]; then
            return 1
        fi
    done

    return 1
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

compare_versions $old_version $release_version
if [[ $? -eq 0 ]]; then
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
if [ -f "/usr/share/cockpit/appstore/appstore.json" ]; then
    old_appstore_version=$(cat /usr/share/cockpit/appstore/appstore.json | jq .Version |  tr -d '"')
else
    old_appstore_version="0.0.0"
fi
new_appstore_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .APPSTORE | tr -d '"')

# update settings
if [ -f "/usr/share/cockpit/settings/settings.json" ]; then
    old_settings_version=$(cat /usr/share/cockpit/settings/settings.json | jq .Version |  tr -d '"')
else
    old_settings_version="0.0.0"
fi
new_settings_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .SETTINGS | tr -d '"')

# update myapps
if [ -f "/usr/share/cockpit/myapps/myapps.json" ]; then
    old_myapps_version=$(cat /usr/share/cockpit/myapps/myapps.json | jq .Version |  tr -d '"')
else
    old_myapps_version="0.0.0"
fi
new_myapps_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .MYAPPS | tr -d '"')

## update container
if [ -f "/usr/share/cockpit/container/portainer.json" ]; then
    old_container_version=$(cat /usr/share/cockpit/container/portainer.json | jq .Version |  tr -d '"')
else
    old_container_version="0.0.0"
fi
new_container_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .PORTAINER | tr -d '"')

## update nginx
if [ -f "/usr/share/cockpit/nginx/nginx.json" ]; then
    old_nginx_version=$(cat /usr/share/cockpit/nginx/nginx.json | jq .Version |  tr -d '"')
else
    old_nginx_version="0.0.0"
fi
new_nginx_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NGINX | tr -d '"')

## update navigator
if [ -f "/usr/share/cockpit/navigator/navigator.json" ]; then
    old_navigator_version=$(cat /usr/share/cockpit/navigator/navigator.json | jq .Version |  tr -d '"')
else
    old_navigator_version="0.0.0"
fi
new_navigator_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NAVIGATOR | tr -d '"')

## update library
if [ -f "/data/library/library.json" ]; then
    old_library_version=$(cat /data/library/library.json | jq .Version |  tr -d '"')
else
    old_library_version="0.0.0"
fi
new_library_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .LIBRARY | tr -d '"')

if [ "$old_appstore_version" = "$new_appstore_version" ] && [ "$old_settings_version" = "$new_settings_version" ] && [ "$old_myapps_version" = "$new_myapp_version" ] && [ "$old_container_version" = "$new_container_version" ] && [ "$old_nginx_version" \< "$new_nginx_version" ]; then
    echo "appstore all plugins is latest"
else
    compare_versions $old_appstore_version $new_appstore_version
    if [[ $? -eq 0 ]]; then
        echo "appstore plugin need to update"
        cd /usr/share/cockpit
        wget $urls/plugin/appstore/appstore-$new_appstore_version.zip
        rm -rf appstore
        unzip appstore-$new_appstore_version.zip
        rm -f appstore-$new_appstore_version.zip
    else
        echo "appstore is not need to update"
    fi

    compare_versions $old_navigator_version $new_navigator_version
    if [[ $? -eq 0 ]]; then
        echo "navigator plugin need to update"
        cd /usr/share/cockpit
        wget $urls/plugin/navigator/navigator-$new_navigator_version.zip
        rm -rf navigator
        unzip navigator-$navigator_version.zip
        rm -f navigator-$navigator_version.zip
    else
        echo "navigator is not need to update"
    fi
    
    compare_versions $old_settings_version $new_settings_version
    if [[ $? -eq 0 ]]; then
        echo "settings plugin need to update"
        cd /usr/share/cockpit
        wget $urls/plugin/settings/settings-$new_settings_version.zip
        rm -rf settings
        unzip settings-$new_settings_version.zip
        rm -f settings-$new_settings_version.zip
    else
        echo "settings is not need to update"
    fi

    compare_versions $old_myapps_version $new_myapps_version
    if [[ $? -eq 0 ]]; then
        echo "start to update myapps..."
        cd /usr/share/cockpit
        wget $urls/plugin/myapps/myapps-$new_myapps_version.zip
        rm -rf myapps
        unzip myapps-$new_myapps_version.zip
        rm -f myapps-$new_myapps_version.zip
    else
        echo "myapps is not need to update"
    fi
    
    compare_versions $old_container_version $new_container_version
    if [[ $? -eq 0 ]]; then
        echo "start  to update portainer..."
        cd /usr/share/cockpit
        wget $urls/plugin/portainer/portainer-$new_container_version.zip
        rm -rf portainer
        unzip portainer-$new_container_version.zip
        rm -f portainer-$new_container_version.zip
    else
        echo "portainer is not need to update"
    fi

    compare_versions $old_nginx_version $new_nginx_version
    if [[ $? -eq 0 ]]; then
        echo "start to update nginx..."
        cd /usr/share/cockpit
        wget $urls/plugin/nginx/nginx-$new_nginx_version.zip
        rm -rf nginx
        unzip nginx-$new_nginx_version.zip
        rm -f nginx-$new_nginx_version.zip
    else
        echo "nginx is not need to update"
    fi

    compare_versions $old_library_version $new_library_version
    if [[ $? -eq 0 ]]; then
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
compare_versions $old_appmanage $new_appmanage
if [[ $? -eq 0 ]]; then
    echo "start to update w9appmanage..."
    rm -f /data/apps/w9services/w9appmanage/.env && cp /data/apps/websoft9/docker/w9appmanage/.env /data/apps/w9services/w9appmanage/.env
    rm -f /data/apps/w9services/w9appmanage/docker-compose.yml && cp /data/apps/websoft9/docker/w9appmanage/docker-compose.yml /data/apps/w9services/w9appmanage/docker-compose.yml
    cd /data/apps/w9services/w9appmanage  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "appmanage is not need to update"
fi

old_redis=$(cat /data/apps/w9services/w9redis/.env |grep APP_VERSION |cut -d= -f2)
new_redis=$(cat /data/apps/websoft9/docker/w9redis/.env |grep APP_VERSION |cut -d= -f2)
compare_versions $old_redis $new_redis
if [[ $? -eq 0 ]]; then
    echo "start to update w9redis..."
    rm -f /data/apps/w9services/w9redis/.env && cp /data/apps/websoft9/docker/w9redis/.env /data/apps/w9services/w9redis/.env
    rm -f /data/apps/w9services/w9redis/docker-compose.yml && cp /data/apps/websoft9/docker/w9redis/docker-compose.yml /data/apps/w9services/w9redis/docker-compose.yml
    cd /data/apps/w9services/w9redis  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "redis is not need to update"
fi

old_portainer=$(cat /data/apps/w9services/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
new_portainer=$(cat /data/apps/websoft9/docker/w9portainer/.env |grep APP_VERSION |cut -d= -f2)
compare_versions $old_portainer $new_portainer
if [[ $? -eq 0 ]]; then
    echo "start to update w9portainer..."
    rm -f /data/apps/w9services/w9portainer/.env && cp /data/apps/websoft9/docker/w9portainer/.env /data/apps/w9services/w9portainer/.env
    rm -f /data/apps/w9services/w9portainer/docker-compose.yml && cp /data/apps/websoft9/docker/w9portainer/docker-compose.yml /data/apps/w9services/w9portainer/docker-compose.yml
    cd /data/apps/w9services/w9portainer  && sudo docker compose down &&  sudo docker compose pull &&  sudo docker compose up -d
else
    echo "w9portainer is not need to update"
fi

old_nginx=$(cat /data/apps/w9services/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
new_nginx=$(cat /data/apps/websoft9/docker/w9nginxproxymanager/.env |grep APP_VERSION |cut -d= -f2)
compare_versions $old_nginx $new_nginx
if [[ $? -eq 0 ]]; then
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

# uninstall plugins
rm -rf /usr/share/cockpit/apps /usr/share/cockpit/selinux /usr/share/cockpit/kdump /usr/share/cockpit/sosreport /usr/share/cockpit/packagekit
cp -r /data/apps/websoft9/cockpit/menu_override/* /etc/cockpit

}

UpdateCockpit(){

echo "Parpare to update Cockpit to latest  ..."

if command -v apt > /dev/null;then  
  current_version=$(dpkg-query --showformat='${Version}' --show cockpit | cut -c 1-3)
  available_version=$(apt-cache policy cockpit | grep Candidate | awk '{print $2}' | cut -c 1-3)
elif  command -v yum > /dev/null;then 
  current_version=$(rpm -q --queryformat '%{VERSION}' cockpit | cut -c 1-3)
  available_version=$(yum list available cockpit --showduplicates | awk '/cockpit/ {print $2}' | sort -V | tail -n 1 | cut -c 1-3)
fi
if [ "$current_version" \< "$available_version" ]; then
  echo "There is newer version on cockpit."
  pkcon refresh
  pkcon get-updates
  pkcon update -y 'cockpit' 'cockpit-bridge' 'cockpit-packagekit' 'cockpit-storaged' 'cockpit-system' 'cockpit-ws'
  EditMenu
  sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket
  sudo systemctl daemon-reload
  sudo systemctl restart cockpit.socket
  echo "cockpit update finished."
else
  echo "cockpit is latest, not need to upadate."
fi

}

CheckEnv
UpdateDocker
UpdateWebsoft9
UpdatePlugins
UpdateServices
UpdateCockpit