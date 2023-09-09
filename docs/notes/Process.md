# Process

要理解整个架构设计，先打开[组件图](https://www.canva.cn/design/DAFt2DhfqYM/3uwKe09X5xaD4QPc47rNMQ/view?utm_content=DAFt2DhfqYM&utm_campaign=designshare&utm_medium=link&utm_source=publishsharelink)，然后结合一下内容进行阅读：  

所有的微操作一定归属于如下三个类别：

- CI：持续集成，即源码准确性
- CD：持续部署，即让软件 running，目前采用拉式方式与CI协作
- CP：持续发布，即通过域名让用户可以访问

另外还有与系统维护相关的：

- Settings
- CLI

## API

API 接口功能设计：

### app/install

功能：安装应用并自动绑定域名  

输入参数：  

```
body:
{
- app_name # 产品名
- app_id   # 自定义应用名称
- domains[]  #域名-可选
- default_domain  #默认域名-可选：设置.env中APP_URL
- edition{dist:community, version:5.0} #应用版本，来自variable.json，但目前variable.json中只有 version 的数据
- endpointId: 安装目的地（portainer中有定义），默认为 local
}
```

过程：  

1. 参数验证：  
   app_id 验证：  
      业务要求：gitea 中是否存在同名的 repository，Portainer中是否存在同名stack  
      技术要求-【非空，容器要求：2位-20位，字母数字以及-组成 gitea：todo portainer：todo】   
   app_name 验证: 在gitea容器的library目录下验证  
   domains[]验证：是否绑定过，数量不能超过2：泛域名+其他域名  
   default_domain验证：来自domains[]中，自定义域名优先  
   edition: community这个不做验证，保留扩展，只做version处理  
   endpointId：通过Portainer容器取名称【local】的endpointId，不存在报错  
2. CI：Gitea 创建 repository：通过Gitea创建仓库，并修改.env文件  
3. CD: Portainer ：  
      创建websoft9网络，判断 websoft9 network (先判断是否存在)  
      Portainer 基于 Gitea Repository 在对应的 endpointId 中创建项目（staus: [active,inactive]）  
4. CP：Nginx 为应用创建 Proxy 访问：如果Proxy创建失败，应用安装成功，但提示Proxy创建失败，不做应用安装回滚  

2-3 步骤是有状态操作（产生对后续操作有影响的记录），故需考虑事务完整性。 

### apps

查询所有apps的信息，返回完整数据。等同于 CD: deploy/apps

### apps/{id}/*

对单个 apps 的增删改查：  

- 查询：deploy/apps/{id} with **get** method
- 启动：deploy/apps/{id}/start
- 停止：deploy/apps/{id}/stop
- 重启：deploy/apps/{id}/restart
- 迁移：deploy/apps/{id}/migrate
- 重建：deploy/apps/{id}/git/redeploy + deploy/apps/{id}/restart
- 卸载：
   - APP_Manage 调用 integration/，删除 Repository
   - APP_Manage 调用 publish/nginx/proxy，删除 Proxy
   - APP_Manage 调用 deploy/apps/{id} with **delete** method，删除应用
   
   > 卸载必须是一个事务操作，确保完成所有步骤，以上先后顺序非常关键

### app/domains

App 域名的：增、删、改、查。   

输入参数：  

pulisherId: 默认为本地 nginx，将来可扩展支持云平台的应用访问网关。  

```
body:
{
- app_id
- domains[]  可选
- default_domain  可选
}
```

流程：

- CP: publish/nginx/proxy
- CI: Gitea 修改 repository 的 .env 文件中的 APP_URL 为默认域名
- CD：deploy/apps/{id}/git/redeploy + deploy/apps/{id}/restart

## Settings



配置文件可以通过接口和CLI进行更改

### 系统配置

系统配置，需重启服务后生效。

system.ini


### 应用配置

app.ini

应用配置一般会提供API，供前端调用。应用配置更改后，不需要重启。

功能：

- settings 增删改查

```
[system]
# websoft9 install path, it can not modify now
install_path=/data/websoft9

# apps install path, it can not modify now
apps_path=/data/compose

# enable appstore preview, it use for CLI upgrade COMMAND
appstore_preview=false

[address]
# Wildcard Domain Name for application 
wildcard_domain=test.websoft9.com


[smtp]
smtp_port=743
smtp_server=smtp.websoft9.com
smtp_tls/ssl=true
smtp_user=admin
smtp_password=password

[receive]
# receive the notify of system
email=help@websoft9.com
wechat=
```


## CLI

CLI 是安装到服务器的服务端命令行工具。它的功能有几种来源：

1. 继承：由 API 直接转换
2. 相关：多个 API 以及 组合
3. 无关：与 API 无关，

具体指令以及参数设计如下：

```
Usage:  w9 [OPTIONS] COMMAND sub-COMMAND

Common Commands
  version       查询 websoft9 版本
  repair        修复 websoft9
  clean         清空 websoft9 使用过程中不需要的残留资源
  upgrade       检查并更新 [core|plugin], --check 只检查
  uninstall     删除 Websoft9 所有服务以及组件，除了 Docker 以及 Docker 应用之外
  environments  list all Environments
  apikey        生产以及管理 AppManage keys
  ip            --replace newIP，直接更改 gitea 和 Nginx IP相关的配置

App Commands:
  install     安装应用
  ls          List 应用列表 [app_id, app_name, status, time, endpointId]
  inspect     显示 APP 详细信息
  start       启动一个停止的应用
  stop        停止一个运行中的应用
  restart     重启应用
  redeploy    重建应用（包含更新镜像后重建）
  delete      删除应用

Global Options:
  -c, --context string     
  -D, --debug              Enable debug mode
  -e, --environment        which environment you used

Run 'w9 COMMAND --help' for more information on a command.
```

## Core

### CI

CI 遵循几个法则：

* 为 CD 准备一个完全可用的编排物料
* Git 驱动，保证编排物料与应用运行环境分离，编排物料可修改可复原
* 编排物料中的资源（包/镜像）具备良好的网络可达性

CI 过程中除了直接使用 [Gitea API](https://docs.gitea.cn/api/1.19/) 之外，还需增加如下业务：  


####  integation/repository/create

功能：  

基于本地目录 library/apps/app_name，创建一个符合 Websoft9 规范格式的 repository（名称为：app_id）：
> app_name 是软件名称，例如：wordpress。app_id 是用户安装的应用名称，例如：mywordpress

步骤：
1. 在 Gitea 中创建一个名称为 app_id 的 repository
2. 修改 Gitea repository 仓库的设置属性，只保留【代码】栏

#### integation/repository/modify

更改临时目录 .env 文件中的重要参数: 

   - APP_URL 用域名/公网IP替换
   - POWER_PASSWORD 使用 16位 【大小写数字特殊字符】 替代
   - APP_VERSION 根据安装输入参数替换
   - APP_NAME 更换为 app_id

然后 git push

#### integation/repository/delete

### CD

CD 遵循几个法则：

* 可以管理应用的完全生命周期
* 应用可以指定部署到local之外的服务器或集群环境（portainer 中对应的术语为 endpoint 或 environment）
* 部署编排物料(CI 的产出物)可以是 docker-compose，也可以是 helm
* 也可以支持源码编译成镜像后自动部署（参考：waypoint）

#### deploy/apps/create/standalone/repository

基于 repository 创建应用，100% 使用 Portainer API /stacks/create/standalone/repository

#### deploy/apps/{id}/git

设置 portainer 与 repository 之间的连接关系，100% 使用 Portainer API /stacks/{id}/git

#### deploy/apps

List all apps，继承 Portainer API /stacks：

额外需要增加如下几类数据：

1. 将 app 主容器的 "Env" 合并到 Portainer API 返回的 env[] 中。
   > portaier 中的 repository 安装方式中，.env 并不会被 portainer 保存到接口中

2. portainer 中的应用目录的 variables.json 或 repository variables.json
3. Gitea API 列出当前 APP 的 repository 之 URL，提供访问链接?
4. 所用应用的数据目录：/var/lib/docker/volumes/...
5. Portainer 通过主容器的 Label 标签和 Ports，获取 app_*_port等

#### deploy/apps/{id}

与 Portainer API /stacks{id} 雷同，支持 get(查询), delete（删除）

#### deploy/apps/{id}/git/redeploy

100% 使用 Portainer API /stacks/{id}/git/redeploy

#### deploy/apps/{id}/start

100% 使用 Portainer API /stacks/{id}/start

#### deploy/apps/{id}/stop

100% 使用 Portainer API /stacks/{id}/stop

#### deploy/apps/{id}/restart

Portainer 未提供对应的 API，可以创建此操作，也可以直接在前端通过 stop & start 组合实现。

#### deploy/apps/{id}/migrate

将 Docker 应用迁移到另外一台服务器上。此需求暂不实现

100% 使用 Portainer API /stacks/{id}/migrate

### CP

#### publish/nginx/proxy

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
