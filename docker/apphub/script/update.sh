#!/bin/bash

# update media and library

echo "$(date) - Compare remote version and local version" | tee -a /var/log/supervisord.log

echo "$(date) - Download remote packages and replace local data" | tee -a /var/log/supervisord.log
