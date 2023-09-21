#!/bin/bash

# start by supervisord
/usr/bin/supervisord
supervisorctl start all
# change user and password
bash /user.sh
tail -f /dev/null