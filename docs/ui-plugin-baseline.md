# Websoft9 插件与交互基线

## 1. 文档目的

本文档记录当前 pluings 目录下核心插件的职责、技术栈与对 Cockpit 的依赖方式，用于评估去 Cockpit 化后的迁移范围。

## 2. 插件清单与当前职责

### plugin-appstore

- 职责: 应用商店、分类浏览、详情展示、安装入口、收藏和部分安装参数输入。
- 技术栈: React 18、CRA、react-app-rewired、MUI、Bootstrap、Redux 相关依赖。
- 关键耦合:
  - 通过 cockpit.language 和 po.js 获得语言环境。
  - 通过 cockpit.file 和 cockpit.jump 完成设置页跳转。
  - 通过 cockpit.spawn 做部分端口校验和宿主机命令执行。

### plugin-myapps

- 职责: 我的应用列表、应用详情、容器信息、访问入口、Compose、卷、数据库、监控、卸载、备份等。
- 技术栈: React 18、CRA、react-app-rewired、MUI、Bootstrap、Redux Saga。
- 关键耦合:
  - 通过 cockpit.js 获取语言和跳转能力。
   - 通过 cockpit.spawn 直接执行 docker exec、curl 和 websoft9 CLI。
  - 通过封装的 apiCore 先在宿主机执行命令拿配置，再访问 AppHub API。

### plugin-settings

- 职责: API Key、域名、证书、镜像源、端口、升级入口等设置。
- 技术栈: React 18、CRA、MUI、Bootstrap。
- 关键耦合:
  - 通过 cockpit.spawn 重置 API Key、校验端口和执行脚本。
  - 通过 cockpit.file 直接修改宿主机上的 docker daemon 配置。
  - 当前设置页里仍然保留 Cockpit 端口概念。

### plugin-nginx

- 职责: 进入 Nginx Proxy Manager。
- 实现方式: 通过 cockpit.spawn 读取 listen_port，构造 iframe 地址。
- 关键耦合: 依赖 cockpit.superuser 和宿主机命令能力读取配置。

### plugin-portainer

- 职责: 进入 Portainer，并尝试完成单点登录。
- 实现方式:
  - 通过 cockpit.spawn 读取 Portainer 与 Nginx 配置。
  - 在前端里请求 Portainer API 获取 JWT。
  - 通过 iframe 嵌入 Portainer 页面。
- 关键问题: 这是 UI 聚合而不是一体化产品能力。

### plugin-gitea

- 职责: 进入 Gitea，并尝试自动登录。
- 实现方式:
  - 通过 cockpit.spawn 读取 Gitea 与 Nginx 配置。
  - 通过前端抓取 Gitea 登录页和 CSRF，再自动提交登录表单。
  - 通过 iframe 嵌入 Gitea 页面。

## 3. 插件层的共同问题

当前插件层存在四个共同特征:

1. 每个插件是独立 React 工程
   当前没有统一的前端 workspace、统一设计系统、统一路由和统一状态模型。

2. 对 Cockpit 运行时有强依赖
   几乎所有插件都默认 cockpit.js 一定存在，并依赖其 i18n、文件、跳转、命令执行能力。

3. 配置获取路径不纯
   插件通常不是直接消费标准后端 API，而是先通过 cockpit.spawn 或 docker exec 拿配置，再调用 API 或 iframe 第三方服务。

4. 产品边界不清晰
   有些页面是 Websoft9 自研业务能力，有些页面只是第三方服务入口，这会直接影响去 Cockpit 化后的优先级和实现方式。

## 4. 对新产品形态的迁移启示

### 4.1 应优先保留的能力基线

- 应用商店的信息架构和安装流程。
- 我的应用列表和详情页节奏。
- 设置页中与 Websoft9 自身运行相关的设置。

### 4.2 不应原样继承的模式

- 通过前端直接触发宿主机命令。
- 通过 iframe + 前端自动登录拼装第三方服务后台。
- 将 Cockpit 的导航、语言、文件和权限模型隐式作为产品能力。

### 4.3 去 Cockpit 化后的拆分建议

建议将现有菜单拆成三种能力面:

1. 产品原生模块
   例如应用商店、我的应用、设置、日志、服务。

2. 受控系统能力
   例如容器文件管理、宿主机终端、诊断任务。

3. 兼容期集成能力
   如仍暂时保留某些第三方管理界面，应作为外部能力集成，而不是内建主界面的一部分。

## 5. 与本次新需求的直接对照

你新增的约束可以直接映射为:

- 文件管理: 从宿主机文件树改为容器挂载文件模型。
- 终端: 保留宿主机连接需求，但必须设计安全桥接方案。
- 服务: 只展示 Websoft9 容器内核心服务及状态。
- 日志: 只展示 Websoft9 自己的运行日志。

这些约束说明新产品边界比旧系统更清晰，也更适合真正脱离 Cockpit。