#!/bin/bash

set -e

trap "sleep 1; continue" ERR

while true; do
    docker cp websoft9-git:/var/websoft9/credential websoft9-apphub:/websoft9/credentials
    docker cp websoft9-deployment:/var/websoft9/credential websoft9-apphub:/websoft9/credentials
    docker cp websoft9-proxy:/var/websoft9/credential websoft9-apphub:/websoft9/credentials
    sleep 3
done