# 当前新版产品架构与实现基线

本文档描述当前分支中“新版 Websoft9 产品本身是如何实现的”，重点不是 `install` 草稿脚本，而是当前代码架构、运行时拓扑、前后端协作方式和容器内部编排方式。

这份文档用于回答两个问题：

1. 当前新版产品到底是什么架构
2. 安装、迭代升级、跨代迁移、卸载未来应当围绕什么真实实现来设计

## 1. 分析范围

本基线主要依据以下当前代码面：

1. `docker/Dockerfile`
2. `docker/docker-compose.yml`
3. `docker/supervisord.conf`
4. `docker/scripts/platform-entrypoint.sh`
5. `docker/scripts/platform-service-control.sh`
6. `docker/scripts/platform-healthcheck.sh`
7. `docker/scripts/platform-sync-config.sh`
8. `apphub/src/main.py` 及 `apphub/src` 结构
9. `console/src/main.tsx`
10. `console/src/app`

## 2. 当前新版总体模型

当前新版产品不是旧版那种 Cockpit 多容器系统，而是一个“单容器交付的集成控制平面”：

1. 交付层是一个 `websoft9` 产品容器
2. 容器内封装了前端壳、AppHub API、Gitea、Portainer、Nginx Proxy Manager 和辅助服务
3. 对外入口由产品容器统一暴露
4. 数据以 `/data` 为核心数据根进行组织
5. 容器内通过 supervisor 进行多进程编排

因此，当前新版的本质是“单容器交付，多进程集成运行时”。

## 3. 当前新版前端壳实现

### 3.1 前端工作区

`console` 已经是当前新版的前端入口工作区，而不是旧版 Cockpit plugin 模式。

从代码结构可以确认：

1. 使用 `Vite + React + TypeScript`
2. 前端入口是 `console/src/main.tsx`
3. 应用根通过 `console/src/app/App.tsx` 创建路由并挂载 provider 栈
4. Provider 层组合了主题、React Query、i18n、Router 和产品认证上下文

### 3.2 路由与壳模型

`console/src/app/router/index.tsx` 表明当前新版已有统一的浏览器路由壳：

1. `auth/setup`
2. `auth/login`
3. `dashboard`
4. `appstore`
5. `myapps`
6. `settings`
7. `users`
8. `files`
9. `terminal`
10. `logs`
11. `services`
12. `integrations`

这说明当前新版已经拥有自带产品前端壳，不再依赖 Cockpit 提供导航、页面容器和会话壳。

### 3.3 前端集成方式

当前前端不是把所有能力都重写成单一 UI，而是采用两类方式并存：

1. 直接实现的产品页面，例如 app store、my apps、settings、users、files、terminal、logs、services、overview
2. 集成工作区页面，例如 Portainer、Nginx Proxy Manager、Gitea 的 integration workspace

这说明当前新版虽然摆脱了 Cockpit，但仍保留“集成外部能力”的产品策略。

从当前 `console/src/features` 和对应后端代码继续下钻，可以把新版前端能力进一步分成三类：

1. 相对完整的产品页面，例如 overview、app store、my apps、users、logs
2. 有明确边界的产品页面，例如 settings、files、terminal、services
3. 明确的第三方集成入口，例如 Portainer、Nginx Proxy Manager、Gitea 的 integration workspace

其中几项边界需要特别注意：

1. `files` 当前面向 Docker 卷或应用数据范围，不等于宿主机全盘文件管理
2. `services` 当前更接近服务监控和日志查看，不应直接表述为完整服务管理
3. `applications/deploy` 与 `applications/custom-install` 更接近应用入口和定制安装入口，不应和完整应用编排能力混写
4. `app-store`、`my-apps` 与 `compose-apps` 虽然已经形成完整产品页面，但后端执行层仍大量建立在 Portainer、Gitea、Nginx Proxy Manager 等集成系统之上

## 4. 当前新版后端控制面实现

### 4.1 AppHub 仍是核心 API 中枢

`apphub/src/main.py` 表明 AppHub 仍是当前新版的核心 API 中枢。

当前主 API 至少包含以下路由域：

1. `app`
2. `auth`
3. `files`
4. `host_access`
5. `integrations`
6. `logs`
7. `overview`
8. `services`
9. `settings`
10. `proxy`
11. `backup`
12. `compose_app`
13. `appstore_sync`

相比旧版，当前 AppHub 的职责已经明显扩大，不再只是旧式应用与代理 API。

从当前路由和服务分工看，AppHub 中至少同时存在两类能力：

1. Websoft9 自己承载的产品控制面能力，例如 auth、overview、logs、files、host_access、settings、services
2. 对第三方系统或集成运行时的封装与编排，例如 app、proxy、compose_app、integrations

这意味着“当前新版是完全原生控制面”这种说法并不准确。更符合代码事实的表述是：当前新版已拥有自带控制台和自带 API 中枢，但其中相当一部分业务能力仍以集成系统为实现基础。

继续下钻到 service 和 router 实现后，可以把几条最核心的业务边界说得更具体：

1. `app_manager` 负责把应用目录、安装状态、容器清单、代理信息和自定义应用元数据聚合成产品视图，但实际容器编排仍明显依赖 Portainer，仓库和源码元数据仍明显依赖 Gitea，代理信息仍明显依赖 Nginx Proxy Manager
2. `proxy_manager` 本质上是对 Nginx Proxy Manager API 的封装，而不是自研反向代理实现
3. `app_access_manager` 负责把应用访问配置、候选端口、域名绑定和证书选择组织成产品能力，但配置存储依赖 Gitea，代理生效依赖 Nginx Proxy Manager
4. `compose_app` 路由明确定义了自定义 Compose 应用的更新、重部署和移除围绕 Gitea 仓库内容与 Portainer 重部署流程展开，而不是独立的原生编排引擎

### 4.2 当前认证边界

当前新版代码中可以直接确认三类认证相关边界同时存在：

1. API 层仍有 `x-api-key` 检查
2. 同时存在内部 gateway trust key 机制
3. 前端层已有 `ProductAuthProvider` 与 `ProductAuthRouteGuard`

基于当前可见代码，更稳妥的结论是：当前产品同时存在 API key、内部网关信任和产品内认证相关实现，但不能仅凭这些入口文件把它概括成已经收敛完成的单一认证模型。

## 5. 当前新版运行时实现

### 5.1 单容器交付

`docker/docker-compose.yml` 表明当前生产运行时的外部交付单元就是一个容器：

1. 服务名 `product`
2. 容器名 `websoft9`
3. 统一暴露 `9000`、`80`、`443`

### 5.2 容器内多进程编排

`docker/supervisord.conf` 表明当前产品容器内部至少编排以下进程：

1. `platform-gateway`
2. `apphub-api`
3. `apphub-media`
4. `files-agent`
5. `gitea`
6. `portainer`
7. `npm-backend`
8. `npm-nginx`
9. `cron`

因此，当前新版并不是“前后端二进程产品”，而是一个容器内集成多个业务与基础服务的运行时。

### 5.3 容器入口与引导过程

`docker/scripts/platform-entrypoint.sh` 表明容器启动时会完成以下动作：

1. 准备 `/data/config` 和 `/data/logs`
2. 建立 `/etc/custom` 与 `/var/log/websoft9` 的兼容软链
3. 启动 supervisor
4. 等待 AppHub 核心服务健康
5. 引导 product auth
6. 引导 platform gateway
7. 引导 Gitea、Portainer 等集成服务
8. 持续更新 runtime status
9. 持续做运行时配置同步

这说明当前新版已经把很多旧版宿主机初始化动作内聚到了容器入口阶段。

## 6. 当前新版数据与持久化模型

### 6.1 主数据根

当前新版的持久化核心是 `/data` 数据根。

从当前 `docker/docker-compose.yml` 可以直接确认，外部命名卷当前收敛为一个主卷：`websoft9_data:/data`。

从 `Dockerfile` 与入口脚本可确认，当前运行时围绕 `/data` 管理以下关键区域：

1. `/data/config`
2. `/data/logs`
3. `/data/gitea`
4. `/data/portainer`
5. `/data/nginx-proxy-manager`
6. `/data/nginx/*`

### 6.2 数据模型特征

这套数据模型有三个重要特征：

1. 当前新版试图把配置、日志和集成服务数据都收敛到统一数据根
2. 当前新版的“卷级模型”已经从历史拆分卷收敛到单主卷 + `/data` 子树模型
3. 仍保留一部分兼容性路径和兼容软链，以吸收历史遗留路径
4. 当前运行时代码明确处理的是兼容路径和兼容软链；至于旧系统迁移数据最终落在哪些子树，应视迁移脚本和迁移实现而定，不能仅凭当前容器入口脚本把它上升为产品运行时架构事实

## 7. 当前新版对外入口模型

当前新版的对外入口已经收敛到产品自己的入口体系：

1. `9000` 为控制台与平台入口，当前通过 `CONSOLE_PORT` 变量暴露
2. `80/443` 为 HTTP/HTTPS 网关入口，当前 compose 中固定暴露为 `80:80` 与 `443:443`
3. `/api` 为 AppHub API 根路径
4. 统一通过平台网关和产品壳组织入口体验

这与旧版的 Cockpit 入口模型已经有本质差异。

但入口统一不等于能力完全原生化。当前代码仍然保留了把第三方能力纳入统一入口的模式，因此在描述新版能力时，应区分：

1. 统一入口体验
2. 自研控制面能力
3. 第三方集成能力

## 8. 对安装、升级、卸载设计的真实约束

从当前新版产品实现来看，后续生命周期设计必须围绕下面这些事实，而不是围绕当前 `install.sh` 草稿：

1. 安装的真实目标是部署“单容器交付、多进程集成运行时”
2. 迭代升级至少需要围绕产品容器与 `/data` 数据根的持续兼容来设计
3. 旧版到新版迁移至少需要解决旧多容器、旧卷与当前统一入口和统一数据根之间的映射问题
4. 卸载设计至少需要区分“停止或删除产品运行时”和“是否清理数据与历史遗留资产”

如果进一步落到能力实现层，还要补充三条约束：

1. 应用升级、重部署和自定义 Compose 生命周期设计不能脱离 Portainer 编排现实
2. 自定义应用源码、访问配置和部分产品配置的生命周期设计不能脱离 Gitea 存储现实
3. 域名、证书和代理相关升级或回退设计不能脱离 Nginx Proxy Manager 的数据与认证现实

## 9. 当前新版能力分类矩阵

为了避免后续设计时把“统一入口”误写成“原生实现”，当前新版能力可先按下面三类理解：

1. 原生产品能力：主要由 Websoft9 自己的前端、后端和运行时逻辑实现
2. 集成封装能力：由 Websoft9 提供产品页面和业务编排，但执行依赖第三方系统
3. 第三方入口能力：Websoft9 主要提供统一入口、认证或会话桥接，实际功能由第三方产品提供

| 能力 | 当前分类 | 代码事实依据 | 迁移关注点 |
|---|---|---|---|
| Overview | 原生产品能力 | 控制台页面 + AppHub `overview` 路由和服务聚合主机、应用、运行时状态 | 主要关注运行时状态接口、缓存和产品元数据兼容，不是重点数据迁移对象 |
| Users / Product Auth | 原生产品能力 | 控制台 `product-auth` 与 `users` 页面 + AppHub `auth` 路由和产品认证服务 | 必须保护用户、凭据、会话与初始化状态；涉及产品内身份模型兼容 |
| Logs | 原生产品能力 | 控制台 `logs` 页面 + AppHub `logs` 路由和运行时日志服务 | 关注日志根路径、日志保留策略与是否保留历史日志 |
| Services | 原生产品能力，但当前边界偏监控 | 控制台 `services` 页面 + AppHub `services` 路由；当前更偏状态与日志，不宜写成完整服务运维 | 关注服务名、健康检查和日志路径兼容，不必把它当独立迁移单元 |
| Files | 原生产品能力，但当前边界受限 | 控制台 `files` 页面 + AppHub 文件路由与 files-agent；作用域是卷和应用数据，不是宿主机全盘 | 关注卷根路径、文件代理可达性和权限模型；不应扩展成宿主机文件迁移 |
| Terminal / Host Access | 原生产品能力，但依赖宿主机连接链路 | 控制台 `terminal` 页面 + AppHub `host_access` 路由和主机访问服务 | 关注宿主机连接配置、密钥和会话状态，避免与应用数据迁移混写 |
| Settings | 原生产品能力，但当前只暴露精选配置 | 控制台 `settings` 页面 + AppHub `settings` 路由；不是完整内部配置中心 | 关注哪些配置属于产品配置、哪些仍属于集成系统配置 |
| App Store | 集成封装能力 | 控制台页面与 AppHub 应用目录能力由 Websoft9 提供，但安装编排明显依赖 Portainer | 关注目录元数据、应用模板与 Portainer 编排兼容，不只看前端页面 |
| My Apps | 集成封装能力 | 控制台页面与状态聚合由 Websoft9 提供，但应用生命周期执行仍明显依赖 Portainer，访问信息依赖 NPM，部分元数据依赖 Gitea | 关注堆栈状态、访问绑定、元数据存储三者的联合迁移 |
| Compose Apps | 集成封装能力 | `compose_app` 路由明确围绕 Gitea 仓库内容和 Portainer 重部署流程展开 | 关注仓库内容、重部署流程、W9_* 环境变量和卷清理语义 |
| App Access / Domain Binding | 集成封装能力 | `app_access_manager` 由 Websoft9 组织访问配置，但配置存储依赖 Gitea，代理生效依赖 NPM | 关注访问配置文件、代理主机、证书绑定和端口候选逻辑的兼容 |
| Integrations: Portainer / NPM / Gitea | 第三方入口能力 | 控制台 `integration workspace` 统一入口，实际能力来自第三方产品本身 | 关注入口重定向、会话桥接和第三方自身数据存续，不应误当成 Websoft9 原生数据迁移 |

这张矩阵的直接用途是：后续在设计安装、升级、卸载和回退时，不要把集成封装能力或第三方入口能力当成完全由 Websoft9 单独负责的运行时能力。

## 10. 为什么当前 `install` 草稿不能主导设计

当前 `install/install.sh` 只能算过渡实现，原因不是它写得长，而是它不是当前产品实现的唯一真相来源：

1. 当前产品的真实实现重点已经转移到 `console`、`apphub`、`docker/Dockerfile` 和容器入口编排
2. install 脚本只是一层宿主机生命周期控制逻辑
3. 如果只围绕 install 脚本设计，会把很多过渡期兼容逻辑误当成产品标准

因此，后续重写安装、迭代升级、跨代迁移、卸载时，应优先以当前新版产品架构与实现基线为准。