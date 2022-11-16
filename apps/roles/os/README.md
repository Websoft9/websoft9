Ansible Role: OS
=========

本 Role 在是一个模块化role的模板格式，用于规范化模块化role的创作。接来下的内容是模块化role的readme格式

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 AmazonLinux|
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime |  |


## Related roles

本 Role 在语法上不依赖其他 role 的变量，但程序运行时需要确保已经运行: common。以下为例：

```
  roles:
    - {role: role_common, tags: "role_common"}
    - {role: role_cloud, tags: "role_cloud"}
    - {role: role_os, tags: "role_os"}
```


## Variables

本 Role 主要变量以及使用方法如下：

| **Items**      | **Details** | **Format**  | **是否初始化** |
| ------------------| ------------------|-----|-----|
| os_gui | gnome,kde | 字符串 | 否 |
| os_connection | vnc | 字符串 | 否 |

注意： 

1. os_connection 目前只支持vnc

## Example

```
- name: Memcached
  hosts: all
  become: yes
  become_method: sudo 
  vars_files:
    - vars/main.yml 

  roles:
    - {role: role_common, tags: "role_common"}
    - {role: role_cloud, tags: "role_cloud"}
    - {role: role_os, tags: "role_os"}
```

## FAQ

1. 注意变量命名一定要符合role名称在前的规范
2. 尽量减少role之间的依赖关系
3. role默认变量设置要科学，即默认变量下语法是顺畅的