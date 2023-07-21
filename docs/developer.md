# Developer Guide


## Version

Use *[[major].[minor].[patch]](https://semver.org/lang/zh-CN/)* for version serial number and [version.json](../version.json) for version dependencies

## Artifact

The core of DevOps is continue publish, the format of software publish is [Artifact（制品库）](https://jfrog.com/devops-tools/article/what-is-a-software-artifact/).  

Websoft9 use below Artifact for different usage:  

#### Dockerhub for image

Access [Websoft9 docker images](https://hub.docker.com/u/websoft9dev) on Dockerhub

#### Azure Storage package

Access [packages list](https://w9artifact.blob.core.windows.net/release?restype=container&comp=list) at Azure Storage


## Release

#### CHANGELOG format

```
## 0.3.0 release on 2023-06-06

1. appmanage docker update to 0.3.0
2. fix prestashop 502
```

### 制品库管理

版本管理部仅仅是对代码的管理，还需要对软件可执行成果物-制品的管理，websoft9 项目会将所有成果作为公开制品。

#### 制品库选型

Dockerhub, Github packages, Azure artifacts, CODING 制品库

> 非容器类制品优先选择 Github packages

#### 制品库自动化

- 插件制品管理：开发人员开发测试完成后，修改插件版本，触发 Action 构建 Github packages 制品
- docker-libaray 库制品管理：开发人员测试完成后，修改 library 版本，触发 Action 构建 Github packages 制品
- websoft9 制品管理：开发人员修改 appmanage 源码或微服务 docker-compose 测试完成后，修改 微服务 版本，触发 Action 构建 Dockerhub 镜像制品以及后台微服务 Github packages 制品

> Portainer,redis,nginxproxymanager 使用外部 dockerhub 镜像

### 自动化测试

当各个制品更新后，项目管理者修改 version_test.json 对应的组件的版本，构建 Action 触发自动化系统测试。
自动化测试失败，通知各开发人员，删除制品，修改后重新生成制品。
自动化测试成功，同步 version_test.json 到 version.json， 新制品正式发布。


### Contributor

- 类型标签：Bug, enhancement, Documetation
- 过程标签：PRD, Dev, QA(include deployment), Documetation