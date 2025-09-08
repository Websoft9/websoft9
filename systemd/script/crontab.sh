#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin


APPHUB_INI_FILE="/var/lib/docker/volumes/websoft9_apphub_config/_data/config.ini"
COCKPIT_CONF_FILE="/etc/cockpit/cockpit.conf"
COCKPIT_SOCKET_FILE="/usr/lib/systemd/system/cockpit.socket"
NGINX_VAR_FILE="/var/lib/docker/volumes/websoft9_nginx_var/_data/custom_var.conf"
NGINX_SSL_FILE="/var/lib/docker/volumes/websoft9_nginx_var/_data/custom_ssl.conf"

# 主要包含：docker0_ip、console_port、cert_path、key_path、cockpit_port
apphub_ini() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: apphub_ini get section key
        docker exec -i websoft9-apphub apphub getconfig --section "$1" --key "$2"
    elif [ "$action" == "set" ]; then
        # 用法: apphub_ini set section key value
        docker exec -i websoft9-apphub apphub setconfig --section "$1" --key "$2" --value "$3"
    fi
}

# 主要包含：docker0_ip
cockpit_conf() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: cockpit_conf get docker0_ip
        if [ "$1" == "docker0_ip" ]; then
            sed -nE "s|Origins = http://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+) ws://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)|\1|p" "$COCKPIT_CONF_FILE"
        fi
    elif [ "$action" == "set" ]; then
        # 用法: cockpit_conf set docker0_ip new
        if [ "$1" == "docker0_ip" ]; then
            sed -i -E "/^Origins = / s|(http://)[^:]+(:[0-9]+)( ws://)[^:]+(:[0-9]+)|\1$2\2\3$2\4|g" "$COCKPIT_CONF_FILE"
        fi
    fi
}

# 主要包含：cockpit_port
cockpit_socket() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: cockpit_socket get
        sed -nE "s|ListenStream=([0-9]+)|\1|p" "$COCKPIT_SOCKET_FILE"
    elif [ "$action" == "set" ]; then
        # 用法: cockpit_socket set new
        sed -i -E "/^ListenStream/ s|(ListenStream=)[0-9]+|\1$1|g" "$COCKPIT_SOCKET_FILE"
    fi
}

# 主要包含：cockpit_port
nginx_var() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: nginx_var get var_name
        sed -nE "s|set \\\$$1 ([^;]+);|\1|p" "$NGINX_VAR_FILE"
    elif [ "$action" == "set" ]; then
        # 用法: nginx_var set var_name new
        sed -i -E "/$1/ s|($1 )[^;]+;|\1$2;|g" "$NGINX_VAR_FILE"
    fi
}


# 主要包含：cert_path、key_path
nginx_ssl() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: nginx_ssl get cert_path|key_path
        if [ "$1" == "cert_path" ]; then
            sed -nE 's|ssl_certificate ([^;]+);|\1|p' "$NGINX_SSL_FILE"
        elif [ "$1" == "key_path" ]; then
            sed -nE 's|ssl_certificate_key ([^;]+);|\1|p' "$NGINX_SSL_FILE"
        fi
    elif [ "$action" == "set" ]; then
        # 用法: nginx_ssl set cert_path|key_path new
        if [ "$1" == "cert_path" ]; then
            sed -i -E "/^ssl_certificate/ s|(ssl_certificate )[^;]+;|\1$2;|g" "$NGINX_SSL_FILE"
        elif [ "$1" == "key_path" ]; then
            sed -i -E "/^ssl_certificate_key/ s|(ssl_certificate_key )[^;]+;|\1$2;|g" "$NGINX_SSL_FILE"
        fi
    fi
}


# 同步apphub，初始化时同步一次，后续监控
sync_apphub() {
    NOW_APPHUB_INI_DOCKER0IP=$(apphub_ini get nginx_proxy_manager docker0_ip)
    NOW_APPHUB_INI_CERTPATH=$(apphub_ini get nginx_proxy_manager ssl_cert)
    NOW_APPHUB_INI_KEYPATH=$(apphub_ini get nginx_proxy_manager ssl_key)
    NOW_APPHUB_INI_COCKPITPORT=$(apphub_ini get cockpit port)
    # docker0_ip
    if [ -n "$NOW_APPHUB_INI_DOCKER0IP" ]; then
        cockpit_conf set docker0_ip "$NOW_APPHUB_INI_DOCKER0IP"
    fi
    # cockpit_port
    if [ -n "$NOW_APPHUB_INI_COCKPITPORT" ]; then
        cockpit_socket set "$NOW_APPHUB_INI_COCKPITPORT"
        nginx_var set cockpit_port "$NOW_APPHUB_INI_COCKPITPORT"
    fi
    # cert_path
    if [ -n "$NOW_APPHUB_INI_CERTPATH" ]; then
        nginx_ssl set cert_path "$NOW_APPHUB_INI_CERTPATH"
    fi
    # key_path
    if [ -n "$NOW_APPHUB_INI_KEYPATH" ]; then
        nginx_ssl set key_path "$NOW_APPHUB_INI_KEYPATH"
    fi

}

sync_apphub
sudo systemctl daemon-reload &&  sudo systemctl restart cockpit.socket && sleep 2 && sudo systemctl restart cockpit && sudo docker exec websoft9-proxy nginx -s reload

# 持续监控
while true; do
    changed_file=$(inotifywait -e modify,attrib --format "%w%f" "$APPHUB_INI_FILE" "$COCKPIT_SOCKET_FILE" "$NGINX_VAR_FILE" "$NGINX_SSL_FILE" 2>/dev/null)

    if [ "$changed_file" == "$COCKPIT_SOCKET_FILE" ]; then
        NOW_COCKPIT_SOCKET_COCKPITPORT=$(cockpit_socket get)
        if [ -n "$NOW_COCKPIT_SOCKET_COCKPITPORT" ]; then
            apphub_ini set cockpit port "$NOW_COCKPIT_SOCKET_COCKPITPORT"
            nginx_var set cockpit_port "$NOW_COCKPIT_SOCKET_COCKPITPORT"
        fi
    else
        sync_apphub
    fi

    sudo systemctl daemon-reload &&  sudo systemctl restart cockpit.socket && sleep 2 && sudo systemctl restart cockpit && sudo docker exec websoft9-proxy nginx -s reload
done