#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

# 监控的文件
FILES="/lib/systemd/system/cockpit.socket /var/lib/docker/volumes/websoft9_apphub_config/_data/config.ini"
cockpit_port="9000"

# 监控文件发生变动时需要做的事情
on_change() {
    set +e
    # 从配置文件中获取端口号
    cockpit_port=$(docker exec -i websoft9-apphub apphub getconfig --section cockpit --key port)
    sed -i "s/ListenStream=[0-9]*/ListenStream=${cockpit_port}/" /lib/systemd/system/cockpit.socket
    systemctl daemon-reload
    systemctl restart cockpit.socket 2> /dev/null
    systemctl restart cockpit || exit 1
    set_Firewalld
    set -e
}

set_Firewalld(){
    echo "Set cockpit service to Firewalld..."
    sed -i "s/port=\"[0-9]*\"/port=\"$cockpit_port\"/g" /etc/firewalld/services/cockpit.xml 2>/dev/nul
    sed -i "s/port=\"[0-9]*\"/port=\"$cockpit_port\"/g" /usr/lib/firewalld/services/cockpit.xml 2>/dev/nul
    firewall-cmd --reload 2>/dev/nul
}

# monitor /lib/systemd/system/cockpit.socket and config.ini, make sure config.ini port is the same with cockpit.socket
inotifywait -e modify -m $FILES | while read PATH EVENT FILE; do
    echo "Set cockpit port by config.ini..."
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
    on_change
done

