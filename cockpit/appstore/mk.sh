#!/bin/bash
cd /data/stackhub-web/src/apps/build
yarn build
while [ ! -d "/usr/share/cockpit/appstore" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/appstore/
