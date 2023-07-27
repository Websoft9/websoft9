# Install and Upgrade

## Install

### Install Path

便于升级、便于用户使用的产品文件目录组织结构

- 微服务容器：/websoft9/docker
- Cockpit 插件：/websoft9/cockpit
- 安装和升级脚本: /websoft9/install
- Appstore 后台源码: /websoft9/appmanage
- cli: /websoft9/cli(待定)

## Upgrade

升级主要分成软件商店升级和内核升级。

#### 软件商店升级

主要是软件商店插件更新后引起的升级。
当本地 appstore 版本小于最新 version.json 的版本时，升级 appstore 插件以及 library 制品。

#### 内核升级

内核升级会将所有组件升级到最新，除了软件商店升级外，还需要升级以下内容：

1. docker， cockpit 系统组件
2. 后台微服务容器
3. cockpit 对应插件

升级都会从制品库获取 version.json 对应版本的制品。

#### 升级限制

内核升级可能会因为架构系统等原因无法升级，在 version.json 中含有支持升级操作系统依赖，据此来判断是否能升级。
