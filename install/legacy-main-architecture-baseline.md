# `main` 分支旧产品架构与实现基线

本文档记录 `main` 分支旧版 Websoft9 的产品架构和实际实现方式，目标是为后续安装、跨代升级、卸载重构提供旧系统事实基线。

这里不把旧安装脚本当成唯一信息源，但也不把历史说明文档当成事实锚点，而是只综合 `main` 分支中仍可直接核对的 compose、安装脚本、卸载脚本、AppHub 与相关实现痕迹来描述。

## 1. 分析范围

本基线主要依据以下旧代码与旧运行时实现面：

1. `main:install/install.sh`
2. `main:install/uninstall.sh`
3. `main:install/install_cockpit.sh`
4. `main:docker/docker-compose.yml`
5. `main:apphub`
6. `main` 分支下仍可直接核对的 Cockpit plugin 相关实现痕迹

## 2. 旧版产品总体模型

旧版 Websoft9 的核心不是一个单体控制台容器，而是四层组合架构：

1. Cockpit 作为产品前端壳和宿主机能力桥接层
2. AppHub 作为业务 API 与应用编排协调层
3. Portainer、Gitea、Nginx Proxy Manager 等第三方服务作为集成运行时
4. Docker、systemd、宿主机目录和宿主机命令作为底层控制面

因此旧版产品本质上是“宿主机控制面 + 多容器集成产品”，不是单容器产品。

## 3. 旧版前端壳与交互模型

### 3.1 Cockpit 是产品壳，不是普通依赖

从旧版安装脚本、compose 和当前仓库中仍可直接核对的实现痕迹可以确认，Cockpit 在旧系统中承担了多重角色：

1. 菜单与页面容器
2. 国际化上下文提供者
3. 宿主机命令执行桥
4. 宿主机文件读写桥
5. 宿主机会话与权限入口

旧系统中的 UI 不是一个统一的自带前端 SPA，而是多个 Cockpit plugin 的组合。

从当前仓库能直接确认的一点是：旧版 plugin 代码并不完整驻留在 `main` 分支中，相关插件长期以独立仓库形式存在。因此，`main` 分支中的 AppHub 和安装脚本只能解释旧版后端与宿主机控制面，不能单独代表旧版完整前端实现。

### 3.2 页面能力来源

旧版很多页面能力并不是 Websoft9 自己完整实现，而是把第三方产品或接口集成到 Cockpit 中：

1. 应用管理围绕 AppHub API
2. 容器与编排管理围绕 Portainer
3. 仓库能力围绕 Gitea
4. 代理、域名、证书能力围绕 Nginx Proxy Manager

这意味着旧版产品边界很大一部分来自“集成外部系统”，而不是单一自研控制面。

更细地说，旧版至少存在三种不同性质的页面能力：

1. 通过 AppHub API 暴露的产品能力，例如应用目录、已安装应用、代理、备份、设置
2. 通过 Cockpit plugin 承载的宿主机或控制面桥接能力，例如命令执行、文件访问、导航与嵌入
3. 直接依赖第三方系统 UI 或 API 的能力，例如 Portainer、Gitea、Nginx Proxy Manager

如果继续按能力来源拆分，旧版“应用管理”本身也不是单一来源能力，而是至少包含：

1. AppHub 暴露的应用目录和状态接口
2. Portainer 提供的堆栈、容器和卷操作能力
3. Gitea 提供的自定义 Compose 源码与仓库能力
4. Nginx Proxy Manager 提供的访问入口和证书能力

## 4. 旧版后端与控制面模型

### 4.1 AppHub 的角色

旧版 AppHub 是业务 API 中枢，但不是完整的产品控制平面。

从仓库结构和旧文档可确认，AppHub 主要提供：

1. 应用管理 API
2. 代理管理 API
3. 备份管理 API
4. 设置管理 API
5. 与 Portainer、Gitea、Nginx Proxy Manager 的凭据转发或接口封装

从 `main` 分支的 `apphub/src/main.py` 可以直接确认，旧版主 API 入口注册的核心路由主要是：

1. `app`
2. `proxy`
3. `backup`
4. `settings`

这进一步说明旧版 AppHub 的职责范围比当前新版明显更窄。

继续下钻到旧版 service 层，可以把这几个路由域的实现边界说得更具体：

1. `app_manager` 负责把应用目录、已安装应用、堆栈状态和容器元数据组织成产品视图，但容器查询、堆栈管理和卷操作明显依赖 Portainer
2. `proxy_manager` 本质上是对 Nginx Proxy Manager API 的封装，域名、证书和代理主机管理依赖其 HTTP API 与 JWT 认证
3. 旧版自定义应用或源码仓库相关能力依赖 Gitea API 与本地 git 命令的混合调用，而不是自研 Git 服务
4. 这说明旧版 AppHub 更像“业务编排与 API 聚合层”，而不是一个完全自足的产品后端

### 4.2 旧版认证与控制边界

旧版的安全与控制边界存在明显历史特征：

1. AppHub 主要依赖 API key，而非产品内用户体系
2. 多个产品能力通过 Cockpit 相关机制触达宿主机命令、文件和系统配置
3. 一部分操作能力直接依赖宿主机权限与宿主机控制面
4. 产品能力和宿主机管理能力边界不清晰

这也是旧版到新版升级必须作为“架构切换”而不是普通升级来处理的核心原因之一。

## 5. 旧版运行时实现模型

### 5.1 多容器拓扑

`main:docker/docker-compose.yml` 可确认旧版的核心运行时至少包含：

1. `websoft9-apphub`
2. `websoft9-deployment`
3. `websoft9-git`
4. `websoft9-proxy`

从容器名、卷名和旧文档可以高置信推断这些容器分别承担以下角色：

1. AppHub API
2. Deployment 或容器编排相关服务
3. Gitea 服务
4. Proxy 或网关相关服务

### 5.2 运行时特征

旧版运行时有三个重要实现特征：

1. Websoft9 自身能力和第三方服务能力共构产品边界
2. 容器命名、卷命名和端口暴露对安装升级脚本有强依赖
3. 前端能力并不运行在一个产品容器内，而是通过 Cockpit 统一承载

## 6. 旧版数据与持久化模型

旧版持久化模型是分散式的命名卷布局，而不是统一数据根：

1. `apphub_logs`
2. `apphub_config`
3. `portainer`
4. `gitea`
5. `nginx_data`
6. `nginx_letsencrypt`
7. `nginx_modsec`
8. `nginx_var`

这套数据面意味着：

1. 升级必须先识别旧卷是否存在
2. 迁移不能只看容器镜像，还必须看卷级资产
3. 证书、日志、配置、自定义代理规则都要分别处理

## 7. 旧版宿主机依赖面

旧版不仅依赖 Docker，还依赖大量宿主机面：

1. `cockpit` 与 `cockpit.socket`
2. `websoft9.service`
3. `/etc/cockpit`
4. `/usr/share/cockpit`
5. `/data/websoft9/source`
6. 包管理器对 Cockpit 套件的安装与卸载

这说明旧版卸载和跨代升级都包含显著的宿主机治理动作，不是简单删除容器。

## 8. 旧版安装、升级、卸载的实现含义

### 8.1 安装

旧安装脚本做的不只是部署产品，还包括：

1. 安装或配置 Docker
2. 安装或配置 Cockpit
3. 安装或更新 Cockpit 相关配置与菜单覆盖
4. 安装或更新 systemd 单元
5. 启动旧多容器运行时

此外，`main:install/install_cockpit.sh` 还能直接证明旧安装面会处理 Cockpit 的宿主机配套事项，例如：

1. 端口探测与 Cockpit 监听端口调整
2. 仓库配置或包管理器安装逻辑
3. firewalld 放行
4. SELinux 调整
5. Cockpit 配置文件与菜单覆盖

### 8.2 升级

旧升级本质上是“同一旧模型内”的宿主机与多容器升级：

1. 自动判断 install 或 upgrade
2. 继承旧路径和旧端口
3. 依赖 Cockpit、systemd 和旧容器仍存在

### 8.3 卸载

旧卸载脚本会：

1. 删除 Websoft9 相关容器
2. 停止并移除旧 systemd 单元
3. 停止并移除 Cockpit 相关组件
4. 清理旧安装路径和 plugin 目录

因此旧卸载的影响范围明显大于当前新系统卸载。

## 9. 对下一轮生命周期设计的直接约束

旧系统给安装、升级、卸载重构带来的约束主要有五条：

1. 旧版到新版必须被定义为跨模型迁移
2. 旧环境识别必须基于容器、卷、systemd、路径等可观察信号
3. 迁移设计必须承认旧版的核心依赖是 Cockpit 和多容器集成运行时
4. 卸载与回退必须区分“运行时删除”和“宿主机遗留清理”
5. 不能把旧版文档中未被代码验证的描述直接当成实现事实

## 10. 旧版能力分类矩阵

为了避免把旧版所有能力都笼统归类成“Websoft9 自己提供”，旧版能力也需要按来源拆开：

1. AppHub 原生 API 能力：由 AppHub 直接提供的业务接口和聚合逻辑
2. 集成封装能力：由 AppHub 组织业务流程，但执行依赖第三方系统 API
3. Cockpit/第三方入口能力：由 Cockpit plugin 承载页面入口，或直接嵌入第三方产品能力

| 能力 | 旧版分类 | 代码事实依据 | 迁移关注点 |
|---|---|---|---|
| 应用目录 / 应用列表 | AppHub 原生 API 能力 | `main` 分支 `apphub/src/main.py` 注册 `app` 路由，`app_manager` 聚合目录与状态 | 关注目录元数据和状态聚合逻辑，但它本身不是最重的数据迁移项 |
| 应用安装 / 启停 / 重启 / 卸载 | 集成封装能力 | `app_manager` 组织应用生命周期，但容器、堆栈和卷操作明显依赖 Portainer | 关注 Portainer 堆栈、卷、endpoint 和应用状态的联合迁移或替代 |
| 自定义 Compose / 仓库相关能力 | 集成封装能力 | 依赖 Gitea API 与本地 git 命令混合调用，不是自研 Git 服务 | 关注仓库是否保留、源码是否迁移、git 语义是否还能成立 |
| 代理 / 域名 / 证书 | 集成封装能力 | `proxy_manager` 本质上是 Nginx Proxy Manager API 封装，依赖其 HTTP API 和 JWT 认证 | 关注域名绑定、证书、代理主机和 NPM 认证信息的迁移或归档 |
| 备份 | AppHub API 能力，但实现来源仍需谨慎表述 | 旧版有 `backup` 路由，但底层是否完全自研仍需结合更深实现核对 | 关注它背后真正依赖的运行时和数据位置，避免误迁空壳功能 |
| 设置 | AppHub 原生 API 能力 | 旧版主 API 入口直接暴露 `settings` 路由 | 关注哪些设置属于产品配置、哪些其实是第三方或宿主机配置 |
| Portainer 页面能力 | Cockpit/第三方入口能力 | 旧版页面通过 Cockpit plugin 和第三方产品提供容器编排 UI | 关注入口替换，不把它当成 Websoft9 自研页面迁移 |
| Gitea 页面能力 | Cockpit/第三方入口能力 | 旧版页面通过 Cockpit plugin 提供仓库服务入口 | 关注入口替换与仓库数据存续 |
| Nginx Proxy Manager 页面能力 | Cockpit/第三方入口能力 | 旧版页面通过 Cockpit plugin 提供代理和证书入口 | 关注入口替换与代理/证书数据存续 |
| 宿主机命令 / 文件 / 导航桥接 | Cockpit/第三方入口能力 | 旧版核心依赖 Cockpit 提供宿主机命令、文件和页面壳能力 | 关注这些桥接能力在新版中是替代、收缩还是明确放弃 |

这张矩阵的直接用途是：后续设计旧版到新版迁移时，不能把旧版所有能力都等价看作“数据迁移”或“容器迁移”问题，其中相当一部分其实是第三方系统能力和 Cockpit 壳能力的替换问题。