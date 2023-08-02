#!/bin/bash

# start by supervisord
nsenter -m -u -i -n -p -t 1 sh -c  "echo test_host >> /tmp/hosts"
nsenter -m -u -i -n -p -t 1 sh -c  "echo $(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-appmanage) websoft9-appmanage >> /etc/hosts"
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null
