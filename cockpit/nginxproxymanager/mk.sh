#!/bin/bash
cd /data/stackhub-web/plugins/nginxproxymanager/build
yarn build
while [ ! -d "/usr/share/cockpit/nginx" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/nginx/
