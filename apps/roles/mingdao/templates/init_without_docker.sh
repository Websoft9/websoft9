#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
sudo rm -rf /data/mingdao/
sudo rm -f /usr/local/mingdao/first
cd  /data/apps/mingdao/installer && bash ./service.sh start    
