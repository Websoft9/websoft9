#!/bin/bash

sudo systemctl stop mingdao
sudo docker stop $(docker ps -aq)
sudo docker rm $(docker ps -aq)
rm -rf /data/mingdao
rm -f /data/apps/mingdao/installer/first
sudo systemctl start mingdao
rm -rf /data/apps/mingdao/installer/log/*
