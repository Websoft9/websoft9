#!/bin/bash

# start by supervisord
internal_ip=$(ip addr show eth0 | awk '/inet /{split($2, a, "/"); print a[1]}')
nsenter -m -u -i -n -p -t 1 sh -c "sed -i '/websoft9-apphub/d' /etc/hosts"
nsenter -m -u -i -n -p -t 1 sh -c "echo $internal_ip websoft9-apphub>> /etc/hosts"
/usr/bin/supervisord
supervisorctl start all
tail -f /dev/null
