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
| Runtime | Docker and DB |


## Related roles

本 Role 引用范例：

```
  roles:
   - {role: role_init, tags: "role_init"} 
```


