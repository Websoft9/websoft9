#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
new_password=$1
sudo su && cd /www/server/panel && python tools.py panel $new_password
