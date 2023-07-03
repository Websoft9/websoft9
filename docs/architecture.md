## 架构图

![image](https://github.com/Websoft9/stackhub/assets/43192516/3b52f27a-8dff-477b-acea-cf971096540c)

## 详细

### 微服务

存在的微服务以及选型：

- Cockpit(Monitor,SSH Ternimal,File Browser)
- Cockpit plugins(Nodejs web)
- Container Manager(portainer container)
- Proxy&DNS(nginxproxymanager container)
- backup(kopia container)
- appstore(appmanager container)
- API gateway: Kong（待定）
- CLI（待定）

### 基础组件

技术选型如下：

- 前端：Nodejs, react, cockpit app
- 后端：Python, Docker, Docker-compose, FastAPI
- API DOCS 生成与测试：swagger
- 安全：pwgen（随机密码），md5(htpasswd)
- 身份验证：（待定）
- CLI：（待定）

### 产品文件目录

便于升级、便于用户使用的产品文件目录组织结构

- 微服务容器：/stackhub/docker
- Cockpit 插件：/stackhub/cockpit
- 安装和升级脚本: /stackhub/install
- Appstore 后台源码: /stackhub/appmanage
- cli: /stackhub/cli(待定)

### Contributor

- 类型标签：Bug, enhancement, Documetation
- 过程标签：PRD, Dev, QA(include deployment), Documetation
