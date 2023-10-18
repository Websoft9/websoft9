#!/bin/bash

echo "Start to cp source code"
if [ ! "$(ls -A /websoft9/apphub-dev)" ]; then
   cp -r /websoft9/apphub/* /websoft9/apphub-dev
fi

echo "Running the apphub"
cd /websoft9/apphub-dev
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080 --log-level error'