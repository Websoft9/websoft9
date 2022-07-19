#!/bin/bash

app_url_replace=$(cat /data/apps/$1/.env |grep APP_URL_REPLACE)
if [ $app_url_replace == "APP_URL_REPLACE=true" ]; then
  echo "Change APP_URL"
  public_ip=`wget -O - https://download.websoft9.com/ansible/get_ip.sh | bash`
  sudo sed -i "s/APP_URL=.*/APP_URL=$public_ip/g" /data/apps/$1/.env
else
  echo "There is not APP_URL"
fi 
