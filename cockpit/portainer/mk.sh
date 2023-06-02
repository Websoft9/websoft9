#!/bin/bash
cd /data/stackhub-web/plugins/portainer/build
yarn build
while [ ! -d "/usr/share/cockpit/container" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/container/
