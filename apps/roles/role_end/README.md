Ansible Role: end
=========

本 Role 用于在 CentOS, Ubuntu 和 AmazonLinux 服务器上结束部署后期的任务。

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 AmazonLinux|
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime |  |


## Related roles

本 Role 在语法上不依赖其他 role 的变量, 且需要放在最后运行。

```
  roles:
   - {role: role_common, tags: "role_common"}   
   - {role: role_cloud, tags: "role_cloud"}
   - {role: role_postgresql, tags: "role_postgresql"}
   - {role: role_docker, tags: "role_docker", when: phppgadmin_install_docker}
   - {role: role_docker_phppgadmin, tags: "role_docker_phppgadmin", when: phppgadmin_install_docker}
   - {role: role_init_password, tags: "role_init_password"}
   - {role: role_end, tags: "role_end"} 
```


## Variables

暂无

## Example

```
- name: PostgreSQL
  hosts: all
  become: yes
  become_method: sudo 
  vars_files:
    - vars/main.yml 

  roles:
   - {role: role_common, tags: "role_common"}   
   - {role: role_cloud, tags: "role_cloud"}
   - {role: role_postgresql, tags: "role_postgresql"}
   - {role: role_docker, tags: "role_docker", when: phppgadmin_install_docker}
   - {role: role_docker_phppgadmin, tags: "role_docker_phppgadmin", when: phppgadmin_install_docker}
   - {role: role_init_password, tags: "role_init_password"}
   - {role: role_end, tags: "role_end"}
```

## FAQ


