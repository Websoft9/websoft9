# Administrator 管理手册

## 数据同步

1. 将 APP 的版本号、最小 CPU、内存、磁盘空间同步到 Contenful 数据表，通过自动化[Github Action](https://github.com/Websoft9/docker-library/blob/main/.github/workflows/requirement_to_contentful.yml)实现。

2. 将 logo 图片同步到 Stackhub 项目的静态文件夹(/static/images)，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/logo.yml)实现。

## AppManage 镜像生成

发布镜像到 Dockhub 的 websoft9dev 组织下，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/appmanage_docker.yml)实现。

## 版本管理

### 命名规则

[major:大版本].[minor:功能版本].[patch:Bug 修复版本]

- major 主版本号，软件架构或软件界面发生重大变化。
- minor 次版本号，软件功能新增或删减。
- patch 错误修复版本号，软件缺陷修复。

> 版本通过 release 发布时指定，主版本号小于 1 时为预发布(pre-release)

### 软件内部组件版本

StackHub 的 release 的版本号由项目主版本号和各微服务和插件版本号构成说明：

```
{
    "SERVICES": {
        "PORTAINER": "2.18.3", // portainer 版本号，即对应docker镜像的版本号
        "NGINX": "2.10.3",  // nginxproxymanager 版本号，即对应docker镜像的版本号
        "APPMANAGE": "0.3.0", // app管理后台 版本号，即对应docker镜像的版本号
        "REDIS": "7.0.11"  // app管理后台 版本号，即对应docker镜像的版本号
    },
    "PLUGINS": {
        "PORTAINER": "1.0.0", // cockpit插件 PORTAINER 版本号
        "NGINX": "1.0.0",   // cockpit插件 nginx 版本号
        "MYAPPS": "1.0.1", // cockpit插件 myapps 版本号
        "APPSTORE": "1.0.0" // cockpit插件 myapps 版本号
    },
    "LIBRARY": {
        "VERSION": "1.0.0" // app项目应用库 docker-library 版本号
    },
    "VERSION": "0.3.0" // StackHub项目版本号，上面所有组件的更新都会引起其版本更新
}
```

### 版本更新内容

通过项目下 CHANGELOG.md 来进行管理，格式如下：

```
## 0.3.0 release on 2023-06-06

1. appmanage docker 镜像更新到 0.3.0
2. 修复 prestashop 无法访问的 bug
3. 修复 odoo 无法安装的 bug

support min_version: 0.1.0

```

## 升级

升级主要分成软件商店升级和内核升级。

### 软件商店升级

主要是软件商店支持的 app 应用发生变化后引起的升级。
当 docker-library 项目发布新的 release 版本后，升级软件商店 app 源码以及 app 对应图片和元数据

> 先发布 stackhub-web 再发布 docker-library, 保持数据一致性

### 内核升级

内核升级是会需要停止软件服务来运行的，除了软件商店升级外，还需要升级以下内容：

1. docker， cockpit 系统组件
2. 后台微服务容器
3. cockpit 对应插件

#### 升级限制

内核升级可能会因为架构系统等原因无法升级，在 CHANGELOG 中含有支持升级的最小版本号，根据此信息来升级到具体版本。

## 日志

Appmanage 日志采用 logging 生成，按自然日分割日志文件。日志路径：/var/lib/docker/volumes/w9appmanage_logs/\_data  
其他微服务采用 Dockhub 公开镜像，用 docker 容器的日志访问命令即可查看。
