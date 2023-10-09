#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

# monitor /lib/systemd/system/cockpit.socket and config.ini, make sure config.ini port is the same with cockpit.socket
while true; do
    inotifywait -e modify /lib/systemd/system/cockpit.socket
    # 当文件修改时，执行你需要的操作
done

