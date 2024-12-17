#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

cockpit_port="9000"
container_name="websoft9-apphub"
volume_name="websoft9_apphub_config"

# get volume from container
function get_volume_path() {
    local container_name="$1"
    local volume_name="$2"
    local retries=0
    local max_retries=5
    local mounts

    while [ $retries -lt $max_retries ]; do
        mounts=$(docker inspect -f '{{ json .Mounts }}' "$container_name" | jq -r ".[] | select(.Name == \"$volume_name\") | .Source")

        if [[ "$mounts" == *"/"* ]]; then
            echo "$mounts"
            return 0
        fi

        ((retries++))
        sleep 5
    done

    echo "Cannot get volume path"
    exit 1
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

        ex -s -c "g/ListenStream=${listen_stream}/s//ListenStream=${cockpit_port}/" -c wq "$cockpit_service_path"
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

# when websoft9 restart, sync cockpit port and ssl
on_change
cp -r /etc/cockpit/ws-certs.d/* /var/lib/docker/volumes/websoft9_nginx_data/_data/custom_ssl/

# monitor /lib/systemd/system/cockpit.socket and config.ini, make sure config.ini port is the same with cockpit.socket
inotifywait -e modify,attrib -m $FILES | while read PATH EVENT FILE; do
    echo "Set cockpit port by config.ini..."
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
    on_change
done

# monitor /etc/cockpit/ws-certs.d and copy files to /var/lib/docker/volumes/websoft9_nginx_data/_data/custom_ssl
inotifywait -e create,modify,delete -m /etc/cockpit/ws-certs.d | while read PATH EVENT FILE; do
    echo "Copying files from /etc/cockpit/ws-certs.d to /var/lib/docker/volumes/websoft9_nginx_data/_data/custom_ssl..."
    cp -r /etc/cockpit/ws-certs.d/* /var/lib/docker/volumes/websoft9_nginx_data/_data/custom_ssl/
done