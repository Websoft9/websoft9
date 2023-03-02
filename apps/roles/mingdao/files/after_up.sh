#!/bin/bash
echo "mingdao execute delete mingdao and first" >> /tmp/mingdao.txt
sudo systemctl stop mingdao
sudo docker stop $(docker ps -aq)
sudo docker rm $(docker ps -aq)
rm -rf /data/mingdao
rm -f /data/apps/mingdao/installer/first
sudo systemctl start mingdao
