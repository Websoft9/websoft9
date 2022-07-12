Ansible Role: init
=========

本 Role 用于在 Cloud Installer 项目的随机密码处理，确保任何用户每一次安装都可以生成随机密码

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu AmazonLinux |
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime | MySQL, MariaDB, PostgreSQL, MongoDB |


## Related roles

本 Role 在语法上引用了主变量，程序运行时需要确保已经运行： mysql | mariadb | postgresql | mongodb 等 Role。以 mysql 为例：

```
  roles:
   - {role: role_common, tags: "role_common"}   
   - {role: role_cloud, tags: "role_cloud"}
   - {role: role_mysql, tags: "role_mysql"}
   - {role: role_docker, tags: "role_docker"}
   - {role: role_docker_phpmyadmin, tags: "role_docker_phpmyadmin"}
   - {role: role_init_password, tags: "role_init_password"} 
```


