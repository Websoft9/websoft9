#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# get applist
git clone --depth=1 https://github.com/Websoft9/StackHub.git
appnames=$(ls StackHub/apps/roles |grep -v Template |grep -v README.md |grep -v role)
for appname in $appnames; do                                   
    echo $character
done 
