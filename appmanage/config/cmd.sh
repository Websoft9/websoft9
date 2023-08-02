#!/bin/bash

# start by supervisord
internal_ip=$(ip addr show eth0 | awk '/inet /{split($2, a, "/"); print a[1]}')
python3 /usr/src/app/hostname.py
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null
