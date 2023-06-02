#!/bin/bash
cd /data/stackhub-web/plugins/myapps/build
yarn build
while [ ! -d "/usr/share/cockpit/myapps" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/myapps/
