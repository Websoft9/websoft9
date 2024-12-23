#!/bin/bash

source_path="/websoft9/apphub-dev"

echo "Start to cp source code"
if [ ! "$(ls -A $source_path)" ]; then
   cp -r /websoft9/apphub/* $source_path
fi
cp -r /websoft9/apphub/swagger-ui $source_path

echo "Install apphub cli"
pip uninstall apphub -y
pip install -e $source_path

echo "Running the apphub"
cd $source_path
exec uvicorn src.main:app --reload --host 0.0.0.0 --port 8080 --log-config /etc/supervisor/conf.d/logging_config.yaml
