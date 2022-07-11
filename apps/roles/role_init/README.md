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


## Variables

本 Role 主要变量以及使用方法如下：

| **Items**      | **Details** | **Format**  | **是否初始化** |
| ------------------| ------------------|-----|-----|
| init_db | 参考下方  | 字典 | 否 |
| init_application | [...]   | 字典 | 否 |

注意：
1. init_db, init_application, init_docker 初始化在项目主变量文件中统一修改。
2. 默认数据库管理员密码初始化范例（程序已经自动处理随机密码脚本与其service的先后关系）
    ```
    init_db: 
      mongodb:
        admin: root
        users: ["react"]
        password: "123456"

    init_db: 
      mysql:
        admin: root
        users: ["wordpress","discuz"]
        password: "123456"

    init_db: 
      postgresql:
        admin: postgres
        users: ["wordpress","discuz"]
        password: "123456"
        service_before:
        service_after: php-fpm.service
    
    init_db: 
      postgresql:
        admin: postgres
        users: ["wordpress","discuz"]
        password: "123456"
        
    init_db: 
      mysql:
        admin: root
        users: ["discuz"]
        password: "123456"  
        config_paths:
          - /data/wwwroot/discuz/upload/config/config_global_default.php
          
    init_db: 
      mysql:
        admin: root
        users: ["discuz"]
        password: "123456"  
        config_paths:
          - /data/wwwroot/discuz/upload/config/config_global_default.php
        commands:
          - sudo wp change -u default_account -p default_password to $new_password
          - sudo systemctl restart xxxx 
    ```
3. 默认应用管理员密码初始范例（此方案只适用于修改文件）
    ```
    init_application:
      wordpress:
        username: admin
        password: "123456"
        service_before:
        service_after: php-fpm.service
        config_paths: 
          - /data/wwwroot/wordpress/wp-config.php
          - /data/wwwroot/wordpress/wp-config2.php
        commands: 
          - sudo wp change -u default_account -p default_password to $new_password
          - sudo systemctl restart xxxx  
          
       discuz:   
         username: admin
         password: "123456"
         service_before:
         service_after: php-fpm.service
         config_paths: 
            - /data/wwwroot/wordpress/wp-config.php
            - /data/wwwroot/wordpress/wp-config3.php
         commands: 
            - sudo wp change -u default_account -p default_password to $new_password
            - sudo systemctl restart xxxx  
       
    init_application:
      grafana:
        username: admin
        password: "admin"
        service_before:
        service_after: grafana-server
        commands: 
          - sudo grafana-cli admin reset-admin-password $new_password        
    ```
4. 默认Docker应用管理员密码初始范例（此方案适用于修改Docker相关）
    ```
    init_docker:
      pgadmin:
        admin_username: user@domain.com
        admin_password: "SuperSecret"
        service_after: "docker.service"
        compose_path: "/data/apps/pgadmin/docker-compose.yml"
        compose_commands:
          - sudo sed -i "s/SuperSecret/$new_password/g" /data/apps/pgadmin/docker-compose.yml
        
    init_docker:
      seafile:
        admin_username: me@example.com
        admin_password: "admin123"
        db: mysql
        db_name: seafile_db
        db_username: root
        db_password: "123456"
        service_after: "docker.service"
        compose_path: "/data/docker-compose.yml"
        compose_commands:
          - 'sudo sed -i "s/MYSQL_ROOT_PASSWORD=.*/MYSQL_ROOT_PASSWORD=$new_password/g" /data/docker-compose.yml'
          - 'sudo sed -i "s/DB_ROOT_PASSWD=.*/DB_ROOT_PASSWD=$new_password/g" /data/docker-compose.yml'
          - 'sudo sed -i "s/SEAFILE_ADMIN_PASSWORD=.*/SEAFILE_ADMIN_PASSWORD=$new_password/g" /data/docker-compose.yml'
        volumes: 
          - /opt/seafile-mysql
          - /opt/seafile-data
        commands: 
          - sudo sudo sh -c "cat /data/config/onlyoffice.conf 1>> /opt/seafile-data/seafile/conf/seahub_settings.py"
          - sudo sed -i "s/seafile.example.com/$(curl ifconfig.me)/g" /opt/seafile-data/seafile/conf/seahub_settings.py
          - sudo sed -i "s/seafile.example.com/$(curl ifconfig.me)/g" /opt/seafile-data/seafile/conf/ccnet.conf
          - sudo docker restart seafile
    ```

## Example

```
- name: MySQL
  hosts: all
  become: yes
  become_method: sudo 
  vars_files:
    - vars/main.yml 

  roles:
   - {role: role_common, tags: "role_common"}   
   - {role: role_cloud, tags: "role_cloud"}
   - {role: role_mysql, tags: "role_mysql"}
   - {role: role_docker, tags: "role_docker"}
   - {role: role_docker_phpmyadmin, tags: "role_docker_phpmyadmin"}
   - {role: role_init_password, tags: "role_init_password"}
   - {role: role_end, tags: "role_end"} 
```

## FAQ

#### 采用哪种方式实现开机运行一次？

systemd

