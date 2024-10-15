#!/bin/bash

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Compare remote version and local version." | tee -a /var/log/supervisord.log

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Download remote packages and replace local data." | tee -a /var/log/supervisord.log
bash /websoft9/script/update_zip.sh --package_name "media-latest.zip" --sync_to "/websoft9/media"
bash /websoft9/script/update_zip.sh --package_name "library-latest.zip" --sync_to "/websoft9/library"

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Success to update library and media."