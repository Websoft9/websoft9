# Developer Guide




## Release



#### 制品库自动化

- 插件制品管理：开发人员开发测试完成后，修改插件版本，触发 Action 构建 Github packages 制品
- docker-libaray 库制品管理：开发人员测试完成后，修改 library 版本，触发 Action 构建 Github packages 制品
- websoft9 制品管理：开发人员修改 appmanage 源码或微服务 docker-compose 测试完成后，修改 微服务 版本，触发 Action 构建 Dockerhub 镜像制品以及后台微服务 Github packages 制品

> Portainer,redis,nginxproxymanager 使用外部 dockerhub 镜像

### 自动化测试

当各个制品更新后，项目管理者修改 version_test.json 对应的组件的版本，构建 Action 触发自动化系统测试。
自动化测试失败，通知各开发人员，删除制品，修改后重新生成制品。
自动化测试成功，同步 version_test.json 到 version.json， 新制品正式发布。


