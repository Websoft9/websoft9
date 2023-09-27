#!/bin/bash

# 在这个脚本中，我们将运行两个脚本
/bin/bash send_credentials.sh
/bin/bash set_hosts.sh
tail -f /dev/null