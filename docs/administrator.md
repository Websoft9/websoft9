# Administrator 管理手册

## 数据同步

1. 将 APP 的版本号、最小 CPU、内存、磁盘空间同步到 Contenful 数据表，通过自动化[Github Action](https://github.com/Websoft9/docker-library/blob/main/.github/workflows/requirement_to_contentful.yml)实现。

2. 将 logo 图片同步到 Stackhub 项目的静态文件夹(/static/images)，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/logo.yml)实现。

## AppManage 镜像生成

发布镜像到 Dockhub 的 websoft9dev 组织下，通过自动化[Github Action](https://github.com/Websoft9/StackHub/blob/main/.github/workflows/appmanage_docker.yml)实现。

## 日志

Appmanage 日志采用 logging 生成，按自然日分割日志文件。日志路径：/var/lib/docker/volumes/w9appmanage_logs/\_data  
其他微服务采用 Dockhub 公开镜像，用 docker 容器的日志访问命令即可查看。
