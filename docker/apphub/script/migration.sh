#!/bin/bash

echo "start to migrate config.ini"

migrate_ini() {

# Define file paths, use template ini and syn exsit items from target ini
export target_ini="$1"
export template_ini="$2"

python3 - <<EOF
import configparser
import os
import sys

target_ini = os.environ['target_ini']
template_ini = os.environ['template_ini']

# Create two config parsers
target_parser = configparser.ConfigParser()
template_parser = configparser.ConfigParser()

try:
  
    target_parser.read(target_ini)
    template_parser.read(template_ini)
except configparser.MissingSectionHeaderError:
    print("Error: The provided files are not valid INI files.")
    sys.exit(1)

# use target_parser to override template_parser
for section in target_parser.sections():
    if template_parser.has_section(section):
        for key, value in target_parser.items(section):
            if template_parser.has_option(section, key):
                template_parser.set(section, key, value)


with open(target_ini, 'w') as f:
    template_parser.write(f)
EOF
}


migrate_ini "/websoft9/apphub/src/config/config.ini" "/websoft9/config/config.ini"
migrate_ini "/websoft9/apphub/src/config/system.ini" "/websoft9/config/system.ini"

if [ $? -eq 0 ]; then
    echo "Success to update config.ini"
else
    echo "Fail to update config.ini, skip it"
fi