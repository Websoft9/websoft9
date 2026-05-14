# AppHub API 基线

## 1. 范围说明

本文档仅基于当前 apphub/src/api/v1/routers 下可见路由整理当前 AppHub API 能力，用于识别后续前端重构和控制平面改造的可复用部分。

## 2. 全局约束

- 所有 API 默认受 x-api-key 保护。
- docs、openapi、redoc 为例外。
- FastAPI root_path 配置为 /api。

这意味着当前 API 适合作为系统间调用接口，但不适合作为未来多用户前台 API 直接暴露层。

## 3. 应用管理接口

### GET /apps/catalog/{locale}

- 用途: 获取应用分类目录。
- 当前定位: compatibility-only 回退接口。产品内应用商店应优先读取 `/media/json/catalog_{locale}.json`，仅在静态目录不可用时回退到该接口。
- locale 目前限制为 zh 或 en。
- 数据来源: media 目录中的 catalog_{locale}.json。

### GET /apps/available/{locale}

- 用途: 获取可安装应用列表。
- 当前定位: compatibility-only 回退接口。产品内应用商店应优先读取 `/media/json/product_{locale}.json` 与 `/media/json/app-store-install-metadata.json`，仅在静态资源异常时回退到该接口。
- 当前会结合 docker-library 下各应用 env 配置推导 settings 和 is_web_app。

### GET /apps

- 用途: 获取已安装应用列表。
- 实现特点: 当前主要依赖 Portainer 栈和容器数据汇总，同时合并内存中的安装中与失败状态。
- 当前过渡契约: 对于安装中或安装失败的瞬态项，响应会带出 `tracking_id`、`status`、`logs`、`error`，供产品内 My Apps 页面持续跟踪安装反馈。

### GET /apps/{app_id}

- 用途: 查看单个应用详情。
- 实现特点: 依赖 Portainer 栈信息和 Nginx 代理信息。

### POST /apps/install

- 用途: 安装应用。
- 当前特点: 校验后仍在线程中异步调用安装，不是完整显式任务系统。
- 当前过渡契约: 成功受理后会立即返回 `app_id` 与 `tracking_id`，前端可据此从 App Store 自然切到 My Apps 跟踪安装中、失败和最终落库后的应用状态。

### POST /apps/install/compose/validate

- 用途: 校验自定义 compose 安装请求的基础结构与 YAML 语法。
- 当前特点: 这是 Story 3.3A 引入的 AppHub-owned 校验端点，只负责解析单个 compose 文本、确认存在至少一个 service，并回显环境变量键与服务列表。
- 当前返回: 成功时返回 `services`、`environment_keys` 和可读 `details`；失败时返回 400，并把 YAML 语法或缺失 services 等问题作为可操作错误透出。
- 当前边界: 该端点不执行真实 compose 安装，也不承担最终策略准入和任务提交；真正执行路径继续留给后续 compose 安装故事。

### POST /apps/{app_id}/start
### POST /apps/{app_id}/stop
### POST /apps/{app_id}/restart

- 用途: 应用生命周期控制。
- 当前主要依赖 Portainer。

### PUT /apps/{app_id}/redeploy

- 用途: 重部署应用，可选择 pull image。
- 当前特点: 使用队列流式返回日志，是相对更接近未来异步任务接口的能力。

## 4. 代理接口

### GET /proxys/{app_id}

- 用途: 查询应用对应代理。
- 当前特点: 通过 AppHub 统一代理 Nginx Proxy Manager API，已可作为 My Apps access tab 的应用级代理读取面。

### GET /proxys/ssl/certificates

- 用途: 获取 SSL 证书列表。
- 当前特点: 现阶段主要提供基础证书库存状态，用于产品内访问配置页展示“可用证书”基线。

### POST /proxys/{app_id}

- 用途: 基于域名列表为应用创建代理。
- 当前特点: 兼容同步调用仍可用；新增 `async_task=true` 后，接口会返回代理任务受理结果，供原生 access tab 轮询统一任务状态。

### PUT /proxys/{proxy_id}

- 用途: 更新代理域名列表。
- 当前特点: 兼容同步调用仍可用；新增 `async_task=true` 后，接口会返回代理任务受理结果，并支持证书绑定字段一并提交。

### GET /proxys/tasks/{task_id}

- 用途: 查询代理变更任务状态。
- 当前特点: 为 My Apps access tab 提供统一任务轮询面，任务完成后返回规范化的 `proxy_id`、域名和证书绑定状态。

### DELETE /proxys/{proxy_id}

- 用途: 删除代理。

当前代理能力本质上是对 Nginx Proxy Manager 的 API 封装，已经足够支撑 access tab 的第一版读写闭环，但后续仍需补齐任务反馈与更细的证书绑定语义。

## 5. 备份接口

### POST /backup/{app_id}

- 用途: 为应用创建备份。

### GET /backup/snapshots

- 用途: 查询备份快照，可按 app_id 过滤。

### DELETE /backup/snapshots/{snapshot_id}

- 用途: 删除备份快照。

### POST /backup/restore/{app_id}/{snapshot_id}

- 用途: 恢复应用备份。

## 6. 设置接口

### GET /settings

- 用途: 获取全部设置。
- 当前数据结构包含 nginx_proxy_manager、gitea、portainer、api_key、domain、cockpit 等节。

### GET /settings/summary

- 用途: 获取原生设置页摘要。
- 当前特点: 按域名、证书、镜像源、内部访问、升级和版本分组返回数据，并默认掩码敏感字段，避免前端长期持有明文秘密值。

### GET /settings/{section}

- 用途: 获取某个设置节。

### PUT /settings/{section}?key=&value=

- 用途: 更新某个节中的单个键值。
- 当前限制: 仍是 config.ini 级别的键值写入，不具备审计、版本、权限隔离能力。

## 7. 当前 API 对新架构的适配判断

### 可复用

- 应用目录、应用可用列表聚合逻辑仍可复用，但对产品内 App Store 前端而言更适合作为兼容回退层，而不是主浏览数据源。
- 应用列表和部分详情聚合逻辑。
- 备份相关接口框架。
- 代理相关封装思路。

### 需要重构

- 认证层，需要从单 API Key 升级到用户、会话、权限体系。
- 设置层，需要脱离 ini 文件和敏感凭据明文管理。
- 任务层，虽然当前已经补上 `tracking_id` 与 My Apps 过渡反馈闭环，但仍需要把线程和临时内存状态升级为标准任务系统与 SSE 推送模型。
- 访问代理层，当前已具备 AppHub 统一代理的读写接口，可支撑 My Apps access tab 的域名与基础证书状态管理，但代理变更尚未进入统一任务模型。
- 资源模型，需要从“第三方服务代理”逐步改为“产品自己的资源与控制平面”。

## 8. 对新前端的意义

当前 AppHub 可以作为新前端第一阶段的业务后端基础，但还不能直接承担完整 BFF 或控制平面职责。

最现实的路径是:

1. 先复用现有应用、代理、备份、设置接口中稳定部分。
2. 在应用域先沿用当前 `app_id + tracking_id + /api/apps` 的过渡反馈模型，为后续 SSE 任务流、My Apps 详情和生命周期动作提供连续性基线。
3. 新增用户认证、权限、日志、服务、文件管理、终端桥接等新 API。
4. 再逐步削弱对 Portainer、Gitea、NPM 当前接口和凭据桥接的依赖。

## 9. 平台运行时标准日志契约

### 目标边界

- `logs` 模块只消费 Websoft9 平台运行时标准日志。
- `services` 模块只消费第三方服务原生日志。
- 混合的单容器 `docker logs` 不再作为 `logs` 模块的长期数据合同。

### 标准日志源

- 标准日志文件路径: `/var/log/websoft9/platform-runtime.log`
- 格式: JSON Lines，每行一个独立 JSON 对象
- 时间统一使用 UTC ISO 8601，例如 `2026-05-06T01:35:03Z`

### 必填字段

- `ts`: 事件时间，UTC ISO 8601 字符串
- `level`: `info`、`warning`、`error`
- `component`: 产生日志的 Websoft9 平台组件，例如 `platform-entrypoint`、`apphub-api`
- `domain`: 固定为 `runtime`
- `event`: 稳定事件名，建议使用 `phase.action` 或 `component.action` 风格
- `message`: 面向运维展示的文本消息

### 可选字段

- `context`: 结构化上下文对象，用于附带 URL、状态码、资源名等补充信息

### 示例

```json
{"ts":"2026-05-06T01:35:03Z","level":"info","component":"platform-entrypoint","domain":"runtime","event":"workspace-bootstrap.bootstrap-gitea","message":"phase=workspace-bootstrap action=bootstrap-gitea"}
```

### 当前实现约束

- `platform-entrypoint` 和 AppHub 运行时日志应写入该标准日志源。
- `runtime-console` API 应从该标准日志源读取，而不是从混合容器输出做语义筛选。
- Nginx Proxy Manager、Gitea、Portainer 等第三方服务原生日志不得写入该标准日志源。