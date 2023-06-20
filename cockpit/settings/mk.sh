#!/bin/bash
cd /data/stackhub-web/plugins/settings/build
yarn build
while [ ! -d "/usr/share/cockpit/settings" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/settings/
