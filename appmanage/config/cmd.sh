#!/bin/bash

# start by supervisord
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null
