#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH




### -----------------------------------------------------###

InstallPlugins(){



# install plugins
cd /usr/share/cockpit
appstore_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .APPSTORE | tr -d '"')
wget $urls/plugin/appstore/appstore-$appstore_version.zip
unzip appstore-$appstore_version.zip

myapps_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .MYAPPS| tr -d '"')
wget $urls/plugin/myapps/myapps-$myapps_version.zip
unzip myapps-$myapps_version.zip

portainer_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .PORTAINER | tr -d '"')
wget $urls/plugin/portainer/portainer-$portainer_version.zip
unzip portainer-$portainer_version.zip

nginx_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NGINX | tr -d '"')
wget $urls/plugin/nginx/nginx-$nginx_version.zip
unzip nginx-$nginx_version.zip

settings_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .SETTINGS | tr -d '"')
wget $urls/plugin/settings/settings-$settings_version.zip
unzip settings-$settings_version.zip

# install navigator
navigator_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .NAVIGATOR | tr -d '"')
wget $urls/plugin/navigator/navigator-$navigator_version.zip
unzip navigator-$navigator_version.zip
rm -f *.zip

# install library
cd /data
library_version=$(cat /data/apps/websoft9/version.json | jq .PLUGINS |jq .LIBRARY | tr -d '"')
wget $urls/plugin/library/library-$library_version.zip
unzip library-$library_version.zip
rm -f library-$library_version.zip

# configure cockpit
cp /data/apps/websoft9/cockpit/cockpit.conf /etc/cockpit/cockpit.conf

#####ci-section#####

sudo systemctl daemon-reload
sudo systemctl enable --now cockpit.socket
sudo systemctl restart cockpit.socket

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
echo "Portainer init password:" $new_password >> /usr/password.txt
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
echo "Nginx init password:" $new_password >> /usr/password.txt
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
sudo docker cp websoft9-appmanage:/usr/src/app/db/database.sqlite /usr
}

EditMenu(){

echo "Start to  Edit Cockpit Menu ..."

# uninstall plugins
rm -rf /usr/share/cockpit/apps /usr/share/cockpit/selinux /usr/share/cockpit/kdump /usr/share/cockpit/sosreport /usr/share/cockpit/packagekit
cp -r /data/apps/websoft9/cockpit/menu_override/* /etc/cockpit
}

InstallPlugins
