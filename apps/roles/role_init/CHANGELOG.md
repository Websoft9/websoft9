# CHANGELOG

## To do

1. mongodb init can't connect in service: AuthenticationFailed: SCRAM-SHA-1 authentication failed, storedKey mismatch

## Logs

### Bug Fixes

* 2020-09-17  set User=root, Group=root for init service
* 2020-07-09  set TimeoutSec=120s on init-password for adapt some application, e.g canvas init need 50s
* 2020-05-20  abandon rc.local, use systemd
* 2020-05-15  去掉MongoDB随机密码中等待10s的操作

### Features

* 2020-08-03  add compose_commands items in docker init
* 2020-06-25  add docker init
* 2020-05-29  Optimize data construct, simplify the init_application
* 2020-05-20  add init log to: /tmp/init_password.txt
