# Process

所有的微操作一定归属于如下三个类别：

- CI：持续集成，即源码准确性
- CD：持续部署，即让软件 running 起来
- CP：持续发布，即通过域名让用户可以访问

## App

### Install

> app_name 是软件名称，例如：wordpress，app_id 是用户安装的应用名称

1. App_Manage API 接受输入并接受语法检查（app_name, app_id, domains[], default_domain, version{}）
2. App_Manage 后端准备源码：Copy app_name from Library -> Modify .env (*port/url/app_name/POWER_PASSWORD/version)
3. APP_Manage 后端调用 Gitea API，创建仓库

   > 1-3 CI过程

4. APP_Manage 后端调用 Portainer API，基于 Gitea Repository 创建应用 staus: [active,inactive]

   > 4 CD过程

5. APP_Manage 后端调用 Nginx API，为应用创建 Proxy(port,domains{},customer_proxy)

   > 5 CP过程

步骤 3-5 是有状态操作（产生对后续操作有影响的记录），故需考虑事务完整性。 

### Lists

完全来源于 Portainer API stacks，但其中的 env[] 属性来自 app 主容器

> portaier 中的 repository 安装方式中，.env 并不会被 portainer 保存到接口中

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

## Publish

### publish/nginx(app_id，Optional:domains[], Optional:port, Optional:nginx_proxy.conf)

#### init()

1. 从 portainer.containers 接口中 Label 属性集中获取 http 或 https 端口：

   > com.docker.compose.http.port": "9001"  | com.docker.compose.https.port": "9002"
   
2. 从 Gitea 接口中获取 repository 的 src/nginx_proxy.conf

#### update()

修改 proxy 中的 domain

#### add()

查询 Nginx 中是否有此应用的 Proxy？

   - Y：将新的域名插入到 Proxy 中（忽略 nginx_proxy.conf？）
   - N：新增 Proxy
   
#### delete()

删除所有相关的 proxys

#### list()

查询所有相关的 proxys



3. Gitea API 修改app_url

4. Portainer API 重新发布Publish app


## Settings

## Upgrade

## CLI