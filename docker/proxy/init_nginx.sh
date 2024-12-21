#!/bin/bash

# Define variables
credential_path="/data/credential"

# Migrating initproxy.conf file
if [ ! -d /data/nginx/default_host ]; then mkdir -p /data/nginx/default_host; fi
cp -f /etc/websoft9/initproxy.conf /data/nginx/default_host/initproxy.conf
[ -f /etc/websoft9/initproxy.conf ] && rm -f /data/nginx/proxy_host/initproxy.conf

# Deploy Websoft9 landing pages
if [ ! -d /data/nginx/default_www/landing ]; then
    mkdir -p /data/nginx/default_www/ 
    cp -r /etc/websoft9/landing /data/nginx/default_www/
else
    echo "/data/nginx/default_www/landing already exists."
fi

# If credential file then create it and init credential for NPM
# Reload NPM docker image Environments

if [ ! -f "$credential_path" ]; then
  # Set init credential
  INITIAL_ADMIN_EMAIL="admin@mydomain.com"
  INITIAL_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+' | cut -c1-16)

  # Write credential to file
  mkdir -p "$(dirname "$credential_path")"
  echo "{\"username\":\"$INITIAL_ADMIN_EMAIL\",\"password\":\"$INITIAL_ADMIN_PASSWORD\"}" > "$credential_path"

else
  read -r INITIAL_ADMIN_EMAIL INITIAL_ADMIN_PASSWORD < <(jq -r '.username + " " + .password' "$credential_path")
fi

# Reload NPM docker image Environments
export INITIAL_ADMIN_EMAIL
export INITIAL_ADMIN_PASSWORD

# Start NPM
exec /init
