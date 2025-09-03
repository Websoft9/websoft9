#!/bin/bash

APPHUB_INI_FILE="/var/lib/docker/volumes/websoft9_apphub_config/_data/config.ini"
COCKPIT_CONF_FILE="/etc/cockpit/cockpit.conf"
COCKPIT_SOCKET_FILE="/usr/lib/systemd/system/cockpit.socket"
NGINX_VAR_FILE="/etc/custom/custom_var.conf"
NGINX_PORT_FILE="/etc/custom/custom_port.conf"
NGINX_SSL_FILE="/etc/custom/custom_ssl.conf"

watch -n 1 "
echo '# APPHUB_INI_FILE: $APPHUB_INI_FILE'
grep -E '^\[nginx_proxy_manager\]|\[cockpit\]|^(listen_port|docker0_ip|cert_path|key_path|port) ?=' $APPHUB_INI_FILE
echo

echo '# COCKPIT_CONF_FILE: $COCKPIT_CONF_FILE'
grep '^Origins =' $COCKPIT_CONF_FILE
echo

echo '# COCKPIT_SOCKET_FILE: $COCKPIT_SOCKET_FILE'
grep '^ListenStream=' $COCKPIT_SOCKET_FILE
echo

echo '# NGINX_VAR_FILE: $NGINX_VAR_FILE'
cat $NGINX_VAR_FILE
echo

echo '# NGINX_PORT_FILE: $NGINX_PORT_FILE'
cat $NGINX_PORT_FILE
echo

echo '# NGINX_SSL_FILE: $NGINX_SSL_FILE'
cat $NGINX_SSL_FILE
"
