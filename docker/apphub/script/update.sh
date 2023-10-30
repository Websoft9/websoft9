#!/bin/bash

echo "$(date) - Compare remote version and local version" | tee -a /var/log/supervisord.log

echo "$(date) - Download remote packages and replace local data" | tee -a /var/log/supervisord.log
bash update_zip.sh --package_name "media.zip" --sync_to "/websoft9/media"
bash update_zip.sh --package_name "docker-library.zip" --sync_to "/websoft9/library"

echo "$(date) - Success to update library and media."