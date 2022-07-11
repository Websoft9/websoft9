# CHANGELOG

## To do

1. 服务器最低配置判断
2. OracleLinux 支持 CentOS7-base.repo
3. Centos snapd install waiting for rhel official(snapd-selinux-2.47.1-1.el7.noarch.rpm) update repo

## Logs

### Bug Fixes

* 2020-08-14  add CentOS7_base.repo for AmazonLinux2
* 2020-06-20  add Check OS support in main.yml
* 2020-02-25  去掉pip install requests, 此模块不是python核心模块
* 2020-11-11  use yumdownloader and rpm install requires package,waiting for rhel official update repo


### Features

* 2020-08-22  add install apps_cockpit.yml
* 2020-07-25  add intall centos-release-scl for CentOS
* 2020-07-02  add `apt install acl`
* 2020-05-31  add locate for search
* 2020-05-20  Don't update when init=0
* 2020-03-20  增加两个安装变量common_install_python_modules,common_install_components用于控制组件的安装
* 2020-02-24  将main.yml按照os_family拆分
* 2020-02-21  增加中国地区DNS地址
