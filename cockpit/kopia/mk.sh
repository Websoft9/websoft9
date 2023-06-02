#!/bin/bash
cd /data/stackhub-web/plugins/kopia/build
yarn build
while [ ! -d "/usr/share/cockpit/backup" ]; do
  sleep 1
done
cp -r ./* /usr/share/cockpit/backup/
