# Websoft9 当前架构基线

## 1. 文档目的

本文档描述 2026-04-21 时点 Websoft9 仓库中可验证的真实实现，用于支撑后续去 Cockpit 化、单容器化、多用户体系重建和升级兼容设计。

这不是旧 PRD 或旧架构文档的摘要，而是面向重构前的代码事实基线。

## 2. 当前系统由哪些部分组成

当前 Websoft9 不是单一应用，而是由四层拼接而成:

1. AppHub 后端
   以 FastAPI 提供应用、代理、备份、设置等业务 API，是当前业务中枢。

2. Cockpit 插件层
   pluings 目录下的多个 React 插件提供应用商店、我的应用、设置、Nginx、Portainer、Gitea 等 UI。

3. 外部服务容器层
   docker-compose 启动 AppHub、Portainer、Gitea、Nginx Proxy Manager 等多个容器，并通过容器网络互连。

4. 宿主机安装与运维层
   install、systemd、scripts 目录负责在宿主机上安装 Cockpit、Docker、systemd 服务和外围配置。

## 3. 当前真实运行拓扑

按 docker/docker-compose.yml，当前核心服务为:

- apphub: 业务 API 服务，挂载 docker.sock 和配置目录。
- deployment: Portainer 包装镜像，用于栈和容器编排管理。
- git: Gitea，用于仓库服务。
- proxy: Nginx Proxy Manager 包装镜像，负责网关、证书和入口。

这说明当前“Websoft9 产品能力”有一部分其实来自被集成的第三方产品，而不是 Websoft9 自己实现。

## 4. AppHub 的职责边界

当前 AppHub 提供四类主要接口:

- 应用管理: 应用目录、可安装应用、已安装应用、安装、启停、重启、重部署。
- 代理管理: 查询应用代理、创建代理、更新代理、删除代理、证书列表。
- 备份管理: 创建备份、列出快照、删除快照、恢复备份。
- 设置管理: 读取和修改 config.ini 中的部分配置。

当前 AppHub 不是完整的控制平面，还具有以下特征:

- 认证仅是 x-api-key，不是产品用户登录体系。
- 配置大量依赖本地 ini 文件，而不是数据库配置中心。
- 对 Portainer、Gitea、Nginx Proxy Manager 的控制主要通过存量凭据转发实现。

## 5. Cockpit 在当前系统里的真实作用

从代码和配置看，Cockpit 当前不只是一个菜单容器，而是承担了以下关键职责:

1. 插件运行容器
   各插件通过 public/index.html 引入 cockpit.js，并运行在 Cockpit 插件机制中。

2. 国际化上下文提供者
   多个插件通过 cockpit.language、cockpit.gettext 和 po.js 获取当前语言及翻译能力。

3. 宿主机命令执行代理
   多个插件直接通过 cockpit.spawn 执行 shell、docker exec、curl、apphub CLI 等命令。

4. 文件读写与跳转桥接
   多处逻辑通过 cockpit.file 读取或修改宿主机文件，也通过 cockpit.jump 做应用内跳转。

5. 宿主机权限放大入口
   代码里大量使用 superuser try，这意味着当前很多产品能力默认建立在宿主机 sudo 能力之上。

因此，去 Cockpit 化后不能只替换前端框架，必须补齐这些能力缺口。

## 6. 当前插件层的事实

pluings 目录下至少包含以下核心插件:

- plugin-appstore: 应用商店。
- plugin-myapps: 我的应用与应用详情页。
- plugin-settings: 设置页。
- plugin-nginx: Nginx Proxy Manager 集成入口。
- plugin-portainer: Portainer 集成入口。
- plugin-gitea: Gitea 集成入口。

这些插件大多是 CRA + React 18 + react-app-rewired + MUI/Bootstrap 的独立项目，不是单一前端工程。

## 7. 与重构目标直接相关的结论

### 7.1 去 Cockpit 化

当前去 Cockpit 化要同时处理五个问题:

- 新前端壳替代 Cockpit 插件容器。
- 新国际化体系替代 cockpit.language 和 po.js。
- 新命令代理或控制平面替代 cockpit.spawn。
- 新导航与会话机制替代 cockpit.jump 和共享宿主机会话。
- 新文件操作能力替代 cockpit.file。

### 7.2 单容器化

当前多容器架构不是简单部署细节，而是产品边界的一部分。单容器化至少有三种可选方向:

1. 将多个现有上游服务内聚到一个大容器中，以多进程方式共存。
2. 保留 AppHub，自研替代 Portainer/Gitea/NPM 的关键能力。
3. 对外仍允许连接宿主机 Docker，但 Websoft9 自身只保留必要核心服务。

这三条路线的升级成本、维护成本和最终产品边界完全不同，必须在新架构里明确。

### 7.3 多用户管理

当前系统没有真正的产品内多用户模型。新需求中的“初始化系统管理员、简单多用户管理模块”意味着至少要新增:

- 用户表和角色模型。
- 登录、会话、密码管理。
- 权限边界，例如系统设置、应用管理、日志查看、服务管理的授权范围。
- 对第三方或内建服务的凭据隔离策略。

### 7.4 文件管理

你已明确: 新文件管理不再面向宿主机，而是面向容器挂载文件。这意味着新能力应以“卷、挂载点、应用目录”为模型，而不是直接暴露宿主机文件树。

### 7.5 终端

你已明确: 终端仍然需要连接宿主机。这个需求是去 Cockpit 化里最敏感的一块，因为它触及安全边界。至少有三种方案需要后续架构决策:

1. 浏览器到 AppHub，再到宿主机 agent 的 WebSocket 终端桥接。
2. 浏览器到容器内终端服务，再通过受控跳板连接宿主机。
3. 不内置交互式宿主机终端，只提供受限命令模板与诊断任务。

### 7.6 服务与日志

你已明确:

- 服务页只显示容器内运行的 Websoft9 核心服务及状态。
- 日志页只显示 Websoft9 自己的运行日志。

这会显著缩小原先依赖宿主机 systemd 和 Cockpit 内建页面的范围，是合理的收敛方向。

## 8. 当前升级模型为什么不能直接沿用

当前升级体系依赖以下前提:

- root 用户在宿主机执行安装脚本。
- systemd 管理 websoft9 服务。
- Cockpit 已被安装且可配置。
- Docker 和若干容器以既定名称运行。

如果目标是自定义前端 + 单容器 + 产品内用户体系，那么升级路径至少要重新设计以下内容:

- 旧配置如何迁移到新配置模型。
- 旧入口 URL、端口与证书如何兼容。
- 旧插件页面收藏和语言设定是否保留。
- 旧 Portainer/Gitea/NPM 数据是否保留、替代或旁路迁移。
- 老用户如何从 OS 用户体系过渡到产品用户体系。

## 9. 面向下一阶段的建议

建议按这个顺序进入新一轮产品与架构定义:

1. 先重写 PRD，明确哪些旧能力保留，哪些降级，哪些重做。
2. 再做目标架构，特别是单容器边界和宿主机连接方案。
3. 把升级迁移单列为一级专题，不要作为实现细节附带处理。