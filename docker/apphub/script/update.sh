#!/bin/bash

channel=release

if [ -f /websoft9/version.json ]; then
    version=$(cat /websoft9/version.json | jq -r .version)
    if [[ $version == *rc* ]]; then
        channel=dev
    fi
fi

echo "channel is $channel"

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Compare remote version and local version." | tee -a /var/log/supervisord.log
echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Download remote packages and replace local data." | tee -a /var/log/supervisord.log

bash /websoft9/script/update_zip.sh --channel $channel --package_name "media-latest.zip" --sync_to "/websoft9/media"
bash /websoft9/script/update_zip.sh --channel $channel --package_name "library-latest.zip" --sync_to "/websoft9/library"

echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Success to update library and media."