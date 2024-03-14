#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

cockpit_port="9000"
container_name="websoft9-apphub"
volume_name="websoft9_apphub_config"

check_ports() {
    
    local ports=("$@")
    for port in "${ports[@]}"; do
        echo "Check port: $port"
        if ss -tuln | grep ":$port " >/dev/null && ! systemctl status cockpit.socket | grep "$port" >/dev/null; then
            echo "Port $port is in use, can not set this port to config.ini"
            return 0
        fi
    done
    echo "All ports are available"
    return 1
}

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
    cockpit_port=$(docker exec -i websoft9-apphub apphub getconfig --section cockpit --key port)
    listen_stream=$(grep -Po 'ListenStream=\K[0-9]*' /lib/systemd/system/cockpit.socket)
    if [ "$cockpit_port" != "$listen_stream" ]; then
        check_ports "$cockpit_port"
        if [ $? -eq 0 ]; then
            sudo docker exec -i websoft9-apphub apphub setconfig --section cockpit --key port --value "$listen_stream"
        else
            ex -s -c "g/ListenStream=${listen_stream}/s//ListenStream=${cockpit_port}/" -c wq "$cockpit_service_path"
            systemctl daemon-reload
            systemctl restart cockpit.socket 2> /dev/null
            systemctl restart cockpit || exit 1
            set_Firewalld
        fi
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