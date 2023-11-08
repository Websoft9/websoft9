#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

cockpit_port="9000"
container_name="websoft9-apphub"
volume_name="websoft9_apphub_config"

# get volume from container
function get_volume_path() {
    local container_name="$1"
    local volume_name="$2"
    local mounts=$(docker inspect -f '{{ json .Mounts }}' "$container_name" | jq -r '.[] | select(.Name == "'$volume_name'") | .Source')
    echo "$mounts"
}

volume_path=$(get_volume_path "$container_name" "$volume_name")
config_path="$volume_path/config.ini"
cockpit_service_path="/lib/systemd/system/cockpit.socket"
FILES="$cockpit_service_path $config_path"

# 监控文件发生变动时需要做的事情
on_change() {
    set +e
    # 从配置文件中获取端口号

    cockpit_port=$(docker exec -i websoft9-apphub apphub getconfig --section cockpit --key port)
    listen_stream=$(grep -Po 'ListenStream=\K[0-9]*' /lib/systemd/system/cockpit.socket)

    if [ "$cockpit_port" != "$listen_stream" ]; then
        sed -i "s/ListenStream=${listen_stream}/ListenStream=${cockpit_port}/" /lib/systemd/system/cockpit.socket
        systemctl daemon-reload
        systemctl restart cockpit.socket 2> /dev/null
        systemctl restart cockpit || exit 1
        set_Firewalld
    fi

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