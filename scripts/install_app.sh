#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# About this Script and command-line options
# ==============================================================================
#
# --dist
# Use the --dist option to install distribution at variable.json file. default is community, for example:
#
#  $ sudo bash install_app.sh --dist community
#
# --version "2.0.1"
# Use the --version option to set application version. default is lastest, for example:
#
#   $ sudo bash install_app.sh --version "2.0.1"
#
# --appanme "wordpress"
# Use the --appanme option for install which application. default is wordpress, for example:
#
#  $ sudo bash install_app.sh --appanme "wordpress"
#
# --appid "mywp"
# Use the --appid option to distinguish installed application, default is mywp, for example:
#
#  $ sudo bash install_app.sh --appid "mywp"
#
# --domain_names "www.websoft9.com,dev.websoft9.com"
# Use the --domain_names option to binding domains for application,it can use any strings (not more than 2), default is "", for example:
#
#  $ sudo bash install.sh --domain_names "test.websoft9.com"
#  $ sudo bash install.sh --domain_names "47.92.175.174"
#  $ sudo bash install.sh --domain_names "test1.websoft9.com,test2.websoft9.com"
# ==============================================================================



# Get Internet IP by path/scripts/get_ip.sh
# if have W9_URL, then proxy_enabled=true
# Get the installed application status
# if active, docker compose ps 