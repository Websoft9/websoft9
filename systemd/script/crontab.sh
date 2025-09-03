#!/bin/bash
set -e
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin


APPHUB_INI_FILE="/var/lib/docker/volumes/websoft9_apphub_config/_data/config.ini"
COCKPIT_CONF_FILE="/etc/cockpit/cockpit.conf"
COCKPIT_SOCKET_FILE="/usr/lib/systemd/system/cockpit.socket"
NGINX_VAR_FILE="/var/lib/docker/volumes/websoft9_nginx_var/_data/custom_var.conf"
NGINX_PORT_FILE="/var/lib/docker/volumes/websoft9_nginx_var/_data/custom_port.conf"
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

# 主要包含：docker0_ip、console_port
cockpit_conf() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: cockpit_conf get docker0_ip|console_port
        if [ "$1" == "docker0_ip" ]; then
            sed -nE "s|Origins = http://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+) ws://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)|\1|p" "$COCKPIT_CONF_FILE"
        elif [ "$1" == "console_port" ]; then
            sed -nE "s|Origins = http://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+) ws://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)|\2|p" "$COCKPIT_CONF_FILE"
        fi
    elif [ "$action" == "set" ]; then
        # 用法: cockpit_conf set docker0_ip|console_port new
        if [ "$1" == "docker0_ip" ]; then
            sed -i -E "/^Origins = / s|(http://)[^:]+(:[0-9]+)( ws://)[^:]+(:[0-9]+)|\1$2\2\3$2\4|g" "$COCKPIT_CONF_FILE"
        elif [ "$1" == "console_port" ]; then
            sed -i -E "/^Origins = / s|(http://[^:]+:)[0-9]+( ws://[^:]+:)[0-9]+|\1$2\2$2|g" "$COCKPIT_CONF_FILE"
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

# 主要包含：docker0_ip、console_port、cert_path、key_path、cockpit_port
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

# 主要包含：console_port
nginx_port() {
    local action="$1"
    shift
    if [ "$action" == "get" ]; then
        # 用法: nginx_port get
        sed -nE "s|listen ([^;]+);|\1|p" "$NGINX_PORT_FILE"
    elif [ "$action" == "set" ]; then
        # 用法: nginx_port set new
        sed -i -E "/^listen/ s|(listen )[^;]+;|\1$1;|g" "$NGINX_PORT_FILE"
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


# apphub原始数据，包含ini文件
LAST_APPHUB_INI_DOCKER0IP=$(apphub_ini get nginx_proxy_manager docker0_ip)
LAST_APPHUB_INI_CONSOLEPORT=$(apphub_ini get nginx_proxy_manager listen_port)
LAST_APPHUB_INI_CERTPATH=$(apphub_ini get nginx_proxy_manager cert_path)
LAST_APPHUB_INI_KEYPATH=$(apphub_ini get nginx_proxy_manager key_path)
LAST_APPHUB_INI_COCKPITPORT=$(apphub_ini get cockpit port)

# cockpit原始数据，包含conf和socket文件
LAST_COCKPIT_SOCKET_COCKPITPORT=$(cockpit_socket get)

# 持续监控
while true; do
    changed_file=$(inotifywait -e modify,attrib --format "%w%f" "$APPHUB_INI_FILE" "$COCKPIT_SOCKET_FILE" 2>/dev/null)

    case "$changed_file" in
        "$APPHUB_INI_FILE")
            NOW_APPHUB_INI_DOCKER0IP=$(apphub_ini get nginx_proxy_manager docker0_ip)
            NOW_APPHUB_INI_CONSOLEPORT=$(apphub_ini get nginx_proxy_manager listen_port)
            NOW_APPHUB_INI_CERTPATH=$(apphub_ini get nginx_proxy_manager cert_path)
            NOW_APPHUB_INI_KEYPATH=$(apphub_ini get nginx_proxy_manager key_path)
            NOW_APPHUB_INI_COCKPITPORT=$(apphub_ini get cockpit port)
            # docker0_ip
            if [ "$NOW_APPHUB_INI_DOCKER0IP" != "$LAST_APPHUB_INI_DOCKER0IP" ] && [ -n "$NOW_APPHUB_INI_DOCKER0IP" ]; then
                cockpit_conf set docker0_ip "$NOW_APPHUB_INI_DOCKER0IP"
                nginx_var set docker0_ip "$NOW_APPHUB_INI_DOCKER0IP"
                systemctl restart cockpit && docker exec websoft9-proxy nginx -s reload
                LAST_APPHUB_INI_DOCKER0IP="$NOW_APPHUB_INI_DOCKER0IP"
            fi
            # console_port
            if [ "$NOW_APPHUB_INI_CONSOLEPORT" != "$LAST_APPHUB_INI_CONSOLEPORT" ] && [ -n "$NOW_APPHUB_INI_CONSOLEPORT" ]; then
                cockpit_conf set console_port "$NOW_APPHUB_INI_CONSOLEPORT"
                nginx_var set console_port "$NOW_APPHUB_INI_CONSOLEPORT"
                nginx_port set "$NOW_APPHUB_INI_CONSOLEPORT"
                systemctl restart cockpit && docker exec websoft9-proxy nginx -s reload
                LAST_APPHUB_INI_CONSOLEPORT="$NOW_APPHUB_INI_CONSOLEPORT"
            fi
            # cockpit_port
            if [ "$NOW_APPHUB_INI_COCKPITPORT" != "$LAST_APPHUB_INI_COCKPITPORT" ] && [ -n "$NOW_APPHUB_INI_COCKPITPORT" ]; then
                cockpit_socket set "$NOW_APPHUB_INI_COCKPITPORT"
                nginx_var set cockpit_port "$NOW_APPHUB_INI_COCKPITPORT"
                systemctl daemon-reload && systemctl restart cockpit.socket && docker exec websoft9-proxy nginx -s reload
                LAST_COCKPIT_SOCKET_COCKPITPORT="$NOW_APPHUB_INI_COCKPITPORT"
                LAST_APPHUB_INI_COCKPITPORT="$NOW_APPHUB_INI_COCKPITPORT"
            fi
            # cert_path
            if [ "$NOW_APPHUB_INI_CERTPATH" != "$LAST_APPHUB_INI_CERTPATH" ] && [ -n "$NOW_APPHUB_INI_CERTPATH" ]; then
                nginx_var set cert_path "$NOW_APPHUB_INI_CERTPATH"
                nginx_ssl set cert_path "$NOW_APPHUB_INI_CERTPATH"
                docker exec websoft9-proxy nginx -s reload
                LAST_APPHUB_INI_CERTPATH="$NOW_APPHUB_INI_CERTPATH"
            fi
            # key_path
            if [ "$NOW_APPHUB_INI_KEYPATH" != "$LAST_APPHUB_INI_KEYPATH" ] && [ -n "$NOW_APPHUB_INI_KEYPATH" ]; then
                nginx_var set key_path "$NOW_APPHUB_INI_KEYPATH"
                nginx_ssl set key_path "$NOW_APPHUB_INI_KEYPATH"
                docker exec websoft9-proxy nginx -s reload
                LAST_APPHUB_INI_KEYPATH="$NOW_APPHUB_INI_KEYPATH"
            fi
            ;;
        "$COCKPIT_SOCKET_FILE")
            NOW_COCKPIT_SOCKET_COCKPITPORT=$(cockpit_socket get)
            if [ "$NOW_COCKPIT_SOCKET_COCKPITPORT" != "$LAST_COCKPIT_SOCKET_COCKPITPORT" ] && [ -n "$NOW_COCKPIT_SOCKET_COCKPITPORT" ]; then
                apphub_ini set cockpit port "$NOW_COCKPIT_SOCKET_COCKPITPORT"
                nginx_var set cockpit_port "$NOW_COCKPIT_SOCKET_COCKPITPORT"
                systemctl daemon-reload && systemctl restart cockpit.socket && docker exec websoft9-proxy nginx -s reload
                LAST_APPHUB_INI_COCKPITPORT="$NOW_COCKPIT_SOCKET_COCKPITPORT"
                LAST_COCKPIT_SOCKET_COCKPITPORT="$NOW_COCKPIT_SOCKET_COCKPITPORT"
            fi
            ;;
    esac
done