Ansible Role: preend
=========

本 Role 用于处理一些比较极端的问题。

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 AmazonLinux |
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime |  |


## Related roles

本 Role 在运行时需要确保已经运行：common, apache, nginx。以 LAMP 为例：

```
  roles:
    - {role: role_common, tags: "role_common"}
    - {role: role_cloud, tags: "role_cloud"}
    - {role: role_apache, tags: "role_apache"}
    - {role: role_php-fpm, tags: "role_php-fpm"}
    - {role: role_lamp, tags: "role_lamp"}
    - {role: role_preend, tags: "role_preend"}
```


## Variables

本 Role 主要变量以及使用方法如下：

| **Items**      | **Details** | **Format**  | **是否初始化** |
| ------------------| ------------------|-----|-----|
| preend_certbot | [ True | False ] | 字符串 | 否 |


## Example

```
- name: LAMP
  hosts: all
  become: yes
  become_method: sudo 
  vars_files:
    - vars/main.yml 

  roles:
    - {role: role_common, tags: "role_common"}
    - {role: role_cloud, tags: "role_cloud"}
    - {role: role_apache, tags: "role_apache"}
    - {role: role_redis, tags: "role_redis"}
    - {role: role_mysql, tags: "role_mysql"}
    - {role: role_php-fpm, tags: "role_php-fpm"}
    - {role: role_lamp, tags: "role_lamp"}
    - {role: role_phpmyadmin, tags: "role_phpmyadmin"}
    - {role: role_9panel, tags: "role_9panel"}
    - {role: role_inotify_watch, tags: "inotify_watch"}
    - {role: role_init_password, tags: "init_password"}
    - {role: role_preend, tags: "role_preend"}
    - {role: role_end, tags: "role_end"}
```

## FAQ


