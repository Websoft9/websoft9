Ansible Role: Nginx
=========

本 Role 用于在PHP运行环境下安装 [Nginx](http://nginx.org/)。

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 AmazonLinux |
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime |  |


## Related roles

本 Role 在运行时需要确保已经运行：common。以 LNMP 为例：

```
roles:
    - {role: role_common, tags: "role_common"}
    - {role: role_nginx, tags: "role_nginx"}
```


## Variables

本 Role 主要变量以及使用方法如下：

| **Items**      | **Details** | **Format**  | **是否初始化** |
| ------------------| ------------------|-----|-----|
| nginx_vhost_mode | default.conf template, selected from [reverse,www,alias]  | String | No |
| nginx_reverse_proxy_port | when use reverse template, this var must used  | String | No |
| nginx_listen_port | "80"  | String | No |
| nginx_htpasswd | True,False  | Boolean | No |

Notes:


## Example

```
- name: LNMP
  hosts: all
  become: yes
  become_method: sudo 
  vars_files:
    - vars/main.yml 

  roles:
    - { role: role_common }
    - { role: role_nginx }
    ...
```

## FAQ


#### How to set init for Ngnix password?

```
htpasswd -b /etc/nginx/.htpasswd username password
systemctl restart nginx
```
