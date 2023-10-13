#!/bin/bash

# start by supervisord
/usr/bin/supervisord
supervisorctl start apphub
tail -f /dev/null