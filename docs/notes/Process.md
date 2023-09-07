# Process

所有的微操作一定归属于如下三个类别：

- CI：持续集成，即源码准确性
- CD：持续部署，即让软件 running 起来
- CP：持续发布，即通过域名让用户可以访问

另外还有与系统维护相关的：

- Settings
- Install
- Upgrade
- Fix
- CLI

## CI

CI 遵循几个法则：

* 为 CD 准备一个完全可用的编排物料
* Git 驱动，保证编排物料与应用运行环境分离，编排物料可修改可复原
* 编排物料中的资源（包/镜像）具备良好的网络可达性

CI 过程中除了直接使用 [Gitea API](https://docs.gitea.cn/api/1.19/) 之外，还需增加如下业务：  

### integation/repository/prepare

准备一个可用的项目：

1. 基于 library/apps/app_name 目录创建一个临时目录 app_id
   > app_name 是软件名称，例如：wordpress。app_id 是用户安装的应用名称，例如：mywordpress

2. 根据安装输入，更改临时目录 .env 文件中的重要参数: 

   - APP_*_PORT 值确保未被使用或将被使用
   - APP_URL 用域名/公网IP替换
   - POWER_PASSWORD 使用 16位 【大小写数字特殊字符】 替代
   - APP_VERSION 根据安装输入参数替换
   - APP_NAME 更换为 app_id

###  integation/repository/create

创建一个符合 Websoft9 规范格式的 repository：

1. 在 Gitea 中创建一个名称为 app_id 的 repository
2. 修改 Gitea repository 仓库的设置属性，只保留【代码】栏

## CD

CD 遵循几个法则：

* 可以管理应用的完全生命周期
* 应用可以指定部署到local之外的服务器或集群环境（portainer 中对应的术语为 endpoint 或 environment）
* 部署编排物料(CI 的产出物)可以是 docker-compose，也可以是 helm
* 也可以支持源码编译成镜像后自动部署（参考：waypoint）

### deploy/apps/create/standalone/repository

基于 repository 创建应用，100% 使用 Portainer API /stacks/create/standalone/repository

### deploy/apps/{id}/git

设置 portainer 与 repository 之间的连接关系，100% 使用 Portainer API /stacks/{id}/git

### deploy/apps

List all apps，继承 Portainer API /stacks：

额外需要增加如下几类数据：

1. 将 app 主容器的 "Env" 合并到 Portainer API 返回的 env[] 中
   > portaier 中的 repository 安装方式中，.env 并不会被 portainer 保存到接口中

2. portainer 中的应用目录的 variables.json 或 repository variables.json

### deploy/apps{id}

与 Portainer API /stacks{id} 雷同，支持 get, put, delete

### deploy/apps/{id}/git/redeploy

100% 使用 Portainer API /stacks/{id}/git/redeploy

### deploy/apps/{id}/start

100% 使用 Portainer API /stacks/{id}/start

### deploy/apps/{id}/stop

100% 使用 Portainer API /stacks/{id}/stop

### deploy/apps/{id}/restart

Portainer 未提供对应的 API，可以创建此操作，也可以直接在前端通过 stop & start 组合实现。

### deploy/apps/{id}/migrate

将 Docker 应用迁移到另外一台服务器上。此需求暂不实现

100% 使用 Portainer API /stacks/{id}/migrate

## CP

### publish/nginx/proxy

function proxy(host，domains[], Optional:port, Optional:exra_proxy.conf)

**init()**

也可以使用 getPort(), getExra_proxy()

1. 获取 Port: 从 portainer.containers 接口中 Label 属性集中获取 http 或 https

   > com.docker.compose.http.port": "9001"  | com.docker.compose.https.port": "9002"
   
2. 获取 exra_proxy.conf: 从 Gitea 接口中获取 repository 的 src/nginx_proxy.conf

**update()**

修改 proxy 中的 domain

**add()**

查询 Nginx 中是否有此应用的 Proxy？

   - Y：将新的域名插入到 Proxy 中（忽略 nginx_proxy.conf？）
   - N：新增 Proxy
   
**delete()**

删除所有相关的 proxys

**list()**

查询所有相关的 proxys

**enable()**

enable所有相关的 proxys

**disable()**

disable 所有相关的 proxys

## App

### Install

功能：安装应用并自动绑定域名  

输入参数：  

- app_name 
- app_id
- domains[]  可选
- default_domain  可选
- version{}

过程：  

1. CI：App_Manage 准备 repository
2. CI：Gitea 创建 repository
3. CD: Portainer 基于 repository 创建项目（staus: [active,inactive]）
4. CP：Nginx 为应用创建 Proxy 访问

以上步骤是有状态操作（产生对后续操作有影响的记录），故需考虑事务完整性。 

### Lists



### Manage

#### Uninstall

- App_Manage API 接受输入并接受语法检查（app_id）
- APP_Manage 后端调用 Gitea API，删除 Repository
- APP_Manage 后端调用 Nginx API，删除 Proxy
- APP_Manage 后端调用 Portainer API，删除应用

> 卸载必须是一个事务操作，确保完成所有步骤，以上先后顺序非常关键

#### Stop

APP_Manage 后端调用 Portainer API 的 stop

#### Start

APP_Manage 后端调用 Portainer API 的 start

#### Restart

APP_Manage 后端调用 Portainer API 的 [stop + start]

#### Modify

Gitea API 列出当前 APP 的 repository 之 URL，提供访问链接

#### Redeploy

- APP_Manage 后端调用 Portainer API 的 redeploy



## Settings

## Upgrade

## CLI