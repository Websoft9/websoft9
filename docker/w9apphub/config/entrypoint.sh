#!/bin/bash

# start by supervisord

/usr/local/bin/supervisord
supervisorctl start all
tail -f /dev/null