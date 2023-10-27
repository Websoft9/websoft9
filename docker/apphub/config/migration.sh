#!/bin/bash

echo "start to migrate config.ini"

migrate_config() {
    /usr/local/bin/python3 - <<EOF
import configparser
import os
import sys

# Define file paths
runtime_configfile = '/websoft9/apphub/src/config/config.ini'
parent_configfile = '/websoft9/config/config.ini'

# Check if the files exist and are not empty
if not os.path.isfile(runtime_configfile) or os.stat(runtime_configfile).st_size == 0:
    print(f"Error: {runtime_configfile} does not exist or is empty.")
    sys.exit(1)

if not os.path.isfile(parent_configfile) or os.stat(parent_configfile).st_size == 0:
    print(f"Error: {parent_configfile} does not exist or is empty.")
    sys.exit(1)

# Create two config parsers
config_runtime = configparser.ConfigParser()
config_parent = configparser.ConfigParser()

# Try to read the two files and handle errors
try:
    config_runtime.read(runtime_configfile)
    config_parent.read(parent_configfile)
except configparser.MissingSectionHeaderError:
    print("Error: The provided files are not valid INI files.")
    sys.exit(1)

# Traverse each section and property in parent_configfile
for section in config_parent.sections():
    if not config_runtime.has_section(section):
        # If the section does not exist in runtime_configfile, add the whole section from parent_configfile
        config_runtime.add_section(section)
        for key, value in config_parent.items(section):
            config_runtime.set(section, key, value)
    else:
        # If the section exists in runtime_configfile, only add the keys that don't exist in runtime_configfile
        for key, value in config_parent.items(section):
            if not config_runtime.has_option(section, key):
                config_runtime.set(section, key, value)

# Write the updated runtime_configfile back to the file
with open(runtime_configfile, 'w') as f:
    config_runtime.write(f)
EOF
}

migrate_config

if [ $? -eq 0 ]; then
    echo "Success to update config.ini"
else
    echo "Fail to update config.ini, skip it"
fi