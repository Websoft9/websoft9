# RabbitMQ Notes

组件名称：RabbitMQ-Server  
安装文档：https://www.rabbitmq.com/download.html  
配置文档：https://www.rabbitmq.com/admin-guide.html  
支持平台： Debian家族 | RHEL家族 | Windows | Kubernetes |Docker  

责任人：helin

## 概要

RabbitMQ是一款开源的MQ系统，它包含RabbitMQ-Server和RabbitMQ-Client，服务器上运行的是RabbitMQ-Server

## 环境要求

* 程序语言：Java 
* 应用服务器：自带
* 数据库：无
* 依赖组件：Erlang
* 服务器配置：最低1核2G
* 其他：

## 安装说明

官方建议使用其自身提供的erlang和rabbitmq-server的仓库，不建议使用操作系统自带的仓库或其他第三方仓库。同时，官方提供了自动安装仓库的自动化脚本。

下面基于不同的安装平台，分别进行安装说明。

### CentOS

```shell
# 分别安装erlang源和rabbitmq-server源
curl -s https://packagecloud.io/install/repositories/rabbitmq/erlang/script.rpm.sh | sudo bash
curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.rpm.sh | sudo bash

# 安装
yum install erlang rabbitmq-server -y
```

### Ubuntu

```shell
# 分别安装erlang源和rabbitmq-server源
curl -s https://packagecloud.io/install/repositories/rabbitmq/erlang/script.deb.sh | sudo bash
curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.deb.sh | sudo bash

# 安装
sudo apt-get update -y
apt install erlang rabbitmq-server -y
```

## 配置

安装完成后，需要依次完成如下配置

```shell
# Set RabbitMQ
- name: Restart RabbitMQ
  shell: systemctl start rabbitmq-server

- name: Enable the management console of RabbitMQ
  shell: rabbitmq-plugins enable rabbitmq_management

- name: Create administrator for RabbitMQ console
  shell: |
    rabbitmqctl add_user admin admin
    rabbitmqctl set_user_tags admin administrator
```

## 路径

* 程序路径：/usr/lib/rabbitmq/lib/rabbitmq_server-*
* 日志路径：/var/log/rabbitmq  
* 配置文件路径：  
* 其他...

## 账号密码

### 数据库密码

如果有数据库

* 数据库安装方式：包管理工具自带 or 自行安装
* 账号密码：

### 后台账号

如果有后台账号

* 登录地址
* 账号密码
* 密码修改方案：最好是有命令行修改密码的方案


## 服务

本项目安装后自动生成：rabbitmq-server 服务

备注：如果开机没有服务，程序无法运行的情况下，需要自行编写服务后存放到项目中

服务的模板如下：

```
[Unit]
Description=Redmine
After=nginx.service
[Service]
Environment=RAILS_ENV=production
Type=simple
WorkingDirectory=/data/wwwroot/redmine
ExecStart=/usr/local/bin/puma -b tcp://127.0.0.1:9292 -e production 
User=redmine
[Install]
WantedBy=multi-user.target
```

## 环境变量

列出需要增加的环境变量以及增加环境变量的命令：

* 名称 | 路径

## 版本号

通过如下的命令获取主要组件的版本号: 

```
# Check RabbitMQ version
sudo rabbitmqctl status | grep RabbitMQ*

# Check Erlang version
ls /usr/lib64/erlang
```

## 常见问题

#### 有没有管理控制台？

*http:// 公网 IP:15672* 即可访问控制台，系统默认存在一个无法通过外网访问的guest/guest账号

#### 本项目需要开启哪些端口？

| item      | port  |
| --------- | ----- |
| lustering | 25672 |
| AMQP      | 5672  |
| http      | 15672 |

#### 有没有CLI工具？

有，通过 `rabbitmqctl` 查看工具的说明

#### 安装后是否需要创建普通用户？

有，rabbitmq
