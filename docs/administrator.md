# Administrator 管理手册

## 数据同步

1. 将 APP 的版本号、最小 CPU、内存、磁盘空间同步到 Contenful 数据表，通过自动化[Github Action](https://github.com/Websoft9/docker-library/blob/main/.github/workflows/requirement_to_contentful.yml)实现。

2. 将 logo 图片同步到 Stackhub 项目的静态文件夹(/static/images)，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/logo.yml)实现。

## AppManage 镜像生成

发布镜像到 Dockhub 的 websoft9dev 组织下，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/appmanage_docker.yml)实现。

## Release

### 版本管理

StackHub 的 release 的版本号由项目主版本号和各微服务和插件版本号构成，详见[版本管理文件](https://github.com/Websoft9/StackHub/blob/main/install/version.json)

### 成果物

1. 代码包本身
2. CHANGELOG 文件，来记录每次变更的具体内容
   Release 目前手动进行，将合并 appmanage 和 cockpit 插件的 CHANGELOG

## 日志

Appmanage 日志采用 logging 生成，按自然日分割日志文件。日志路径：/var/lib/docker/volumes/w9appmanage_logs/\_data
其他微服务采用 Dockhub 公开镜像，用 docker 容器的日志访问命令即可查看。

## 更新与升级

执行升级脚本(/install/update.sh)来实现自动升级。
