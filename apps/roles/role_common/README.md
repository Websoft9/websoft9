Ansible Role: common
=========

本 Role 用于在CentOS或者Ubuntu服务器上安装常见工具和配置系统自动更新

## Requirements

运行本 Role，请确认符合如下的必要条件：

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 AmazonLinux|
| Python 版本 | Python2  |
| Python 组件 |    |
| Runtime |  Linux |


## Related roles

本 Role 在其他 roles 之前运行。


## Variables

本 Role 主要变量以及使用方法如下：

| **Items**      | **Details** | **Format**  | **是否初始化** |
| ------------------| ------------------|-----|-----|
| common_install_python_modules | 布尔类型，默认 True| 字符串 |否|
| common_install_components |布尔类型，默认 True| 字符串 |否|
| common_os_support |["CentOS", "Ubuntu", "Amazon", "OracleLinux"]| 队列 |否|
| common_install_tools |- cockpit| 队列 |否|


## Example

```
common_os_support: ["CentOS", "Ubuntu", "Amazon", "OracLinux"]
common_install_tools
  - cockpit
```

## FAQ


