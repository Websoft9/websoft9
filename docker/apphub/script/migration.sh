#!/bin/bash

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - start to migrate config.ini"

migrate_ini() {
# Combine source_ini to target ini
export target_ini="$1"
export source_ini="$2"

python3 - <<EOF
import configparser
import os
import sys

target_ini = os.environ['target_ini']
source_ini = os.environ['source_ini']

# Create two config parsers
target_parser = configparser.ConfigParser()
source_parser = configparser.ConfigParser()

try:
  
    target_parser.read(target_ini)
    source_parser.read(source_ini)
except configparser.MissingSectionHeaderError:
    print("Error: The provided files are not valid INI files.")
    sys.exit(1)

# use target_parser to override source_parser
for section in target_parser.sections():
    if source_parser.has_section(section):
        for key, value in target_parser.items(section):
            if source_parser.has_option(section, key):
                source_parser.set(section, key, value)


with open(target_ini, 'w') as f:
    source_parser.write(f)
EOF
}

# Special migration
post_migration(){
    echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Set listen_port to nginx_proxy_manager"
    listen_port=${INNER_GATEWAY_PORT:-80}
    apphub setconfig --section nginx_proxy_manager --key listen_port  --value "$listen_port"
}

migrate_ini "/websoft9/apphub/src/config/config.ini" "/websoft9/config/config.ini"
migrate_ini "/websoft9/apphub/src/config/system.ini" "/websoft9/config/system.ini"
post_migration

if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Success to update config.ini"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - Fail to update config.ini, skip it"
fi
