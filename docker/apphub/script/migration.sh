#!/bin/bash

echo "start to migrate config.ini"

migrate_ini() {

# Define file paths, use template ini and syn exsit items from target ini
local target_ini="$1"
local template_ini="$2"

    /usr/local/bin/python3 - <<EOF
import configparser
import os
import sys

# Create two config parsers
target_parser = configparser.ConfigParser()
template_parser = configparser.ConfigParser()

# Check if the files exist and are not empty
if not os.path.isfile(target_ini) or os.stat(target_ini).st_size == 0:
    print(f"Error: {target_ini} does not exist or is empty.")
    sys.exit(1)

if not os.path.isfile(template_ini) or os.stat(template_ini).st_size == 0:
    print(f"Error: {template_ini} does not exist or is empty.")
    sys.exit(1)

try:
    target_parser.read(target_ini)
    template_parser.read(template_ini)
except configparser.MissingSectionHeaderError:
    print("Error: The provided files are not valid INI files.")
    sys.exit(1)

# Traverse each section and property in template_ini
for section in template_parser.sections():
    if not target_parser.has_section(section):
        # If the section does not exist in target_ini, add the whole section from template_ini
        target_parser.add_section(section)
        for key, value in template_parser.items(section):
            target_parser.set(section, key, value)
    else:
        # If the section exists in target_ini, only add the keys that don't exist in target_ini
        for key, value in template_parser.items(section):
            if not target_parser.has_option(section, key):
                target_parser.set(section, key, value)

with open(target_ini, 'w') as f:
    template_parser.write(f)
EOF
}

migrate_ini "/websoft9/apphub/src/config/config.ini" "/websoft9/config/config.ini"

if [ $? -eq 0 ]; then
    echo "Success to update config.ini"
else
    echo "Fail to update config.ini, skip it"
fi