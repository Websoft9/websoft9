#!/bin/bash

set -e

trap "sleep 1; continue" ERR

while ! docker cp my-container:/path/to/file websoft9-apphub:/websoft9/credentials; do
    sleep 1
done


while ! docker cp my-container:/path/to/file websoft9-apphub:/path/to/credentials; do
    sleep 1
done


while ! docker cp my-container:/path/to/file websoft9-apphub:/path/to/credentials; do
    sleep 1
done