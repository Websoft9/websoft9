# 概述

## 需求草稿

|                | Cloudron | [casaos](https://www.casaos.io/)                         | umbrel       | runtipi |
| -------------- | -------- | -------------------------------------------------------- | ------------ | ------- |
| 应用编排       |          | 单一镜像                                                 |              |   多镜像，compose 编排      |
| 市场应用来源   |          | 官方+社区                                                | 官方+社区    |         |
| 一键安装程度   |          | 不需任何配置                                             | 不需任何配置 |         |
| 应用访问方式   |          | 端口                                                     | 端口         |         |
| 自定义安装应用 |          | Y                                                        | N            | N       |
| Web 管理容器   |          | Y                                                        | N            |         |
| 默认镜像仓库   |          | DockerHub                                                |              |         |
| 自适应         |          | Y                                                        | Y            |         |
| 多语言         |          | Y                                                        | N            |         |
| 用户管理       |          | 单一用户                                                 | 单一用户     |         |
| 自带应用       |          | 文件，服务器终端，容器终端，监控，日志                   | 监控，日志   |         |
| 应用管理       |          | 完整容器参数设置，克隆，绑定域名？备份？证书？           | 无           |         |
| 应用更新       |          | N                                                        |              |         |
| 后端语言       |          | Go                                                       |              |         |
| API            |          | HTTP API                                                 |              |         |
| 前端           |          | vue.js                                                   |              |         |
| CLI            |          | Y                                                        |              |         |
| HTTP 服务器      |          | 无，端口访问应用                                         |              |    traefik    |
| 公共数据库     |          | 无                                                       |              |         |
| 开发文档       |          | [wiki](https://wiki.casaos.io/en/contribute/development) |              |         |
| 2FA            |          | N                                                        | Y            |         |
| 安装方式       |          | 服务器安装                                               | 容器安装     |         |
| 商店更新       |          | N                                                        | Y            |     Y    |
| 商店绑定域名   | Y        | N                                                        | N            |         |
| DNS服务        | Y        | N                                                        |              |         |

* 应用自动分配4级域名后，如何再 CNAME 二级域名？

### casaos 架构分析

#### 安装脚本

1. Check硬件、操作系统、cpu架构
2. 安装依赖包
3. 安装docker
4. 下载各源码包
5. 启动个源码对应服务

#### 源码解析

|     运行时项目         | 对应项目源码 | 说明                         |
| -------------- | -------- | -------------------------------------------------------- |
| casaos       |    CasaOS      | 每隔5秒通过websocekt推送内存/CPU/网络等系统信息;提供ssh登录操作的http接口;提供"sys", "port", "file", "folder", "batch", "image", "samba", "notify"这些http接口的访问|
| casaos-message-bus   |  CasaOS-MessageBus        | 类似一个MQ提供消息的发布/订阅                                                | 
| casaos-local-storage   |  CasaOS-LocalStorage      | 每隔5S统计磁盘/USB信息,提供监控信息;提供http接口访问disk/usb/storage信息                                           |
| casaos-user-service   | CasaOS-UserService         | 通过http server提供用户管理的接口                                                   |
| casaos-app-management | CasaOS-AppManagement         | 使用CasaOS-AppStore中App的元数据;提供所有appList的分类/列表/详细信息;通过docker来管理app,提供安装/启动/关闭/重启/日志查看等相关接口;docker-compose管理（V2）;|
| casaos-gateway   | CasaOS-Gateway         | 提供Gateway自身管理接口,比如切换Gateway的port的接口,查看所有路由的接口;提供CasaOS-UI的静态资源访问服务;根据请求的PATH将请求代理转发至其它模块                                                      |
| casaos-cli   |  CasaOS-CLI        | 通过命令行的方式来调用CasaOS-Gateway的接口,该模块未完全实现,实现了部分命令                                                |
| linux-all-casaos      |  CasaOS-UI        | VUE2,CasaOS的Web源码,编译后的html/js/image/css等由CasaOS-Gateway提供访问入口,所有API接口指向CasaOS-Gateway                                                        |
| -        |  CasaOS-Common        | Common structs and functions for CasaOS                                                       |
