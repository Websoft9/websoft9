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
- locale 目前限制为 zh 或 en。
- 数据来源: media 目录中的 catalog_{locale}.json。

### GET /apps/available/{locale}

- 用途: 获取可安装应用列表。
- 当前会结合 docker-library 下各应用 env 配置推导 settings 和 is_web_app。

### GET /apps

- 用途: 获取已安装应用列表。
- 实现特点: 当前主要依赖 Portainer 栈和容器数据汇总，同时合并内存中的安装中与失败状态。

### GET /apps/{app_id}

- 用途: 查看单个应用详情。
- 实现特点: 依赖 Portainer 栈信息和 Nginx 代理信息。

### POST /apps/install

- 用途: 安装应用。
- 当前特点: 校验后在后台线程里调用安装，不是显式任务系统。

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

### GET /proxys/ssl/certificates

- 用途: 获取 SSL 证书列表。

### POST /proxys/{app_id}

- 用途: 基于域名列表为应用创建代理。

### PUT /proxys/{proxy_id}

- 用途: 更新代理域名列表。

### DELETE /proxys/{proxy_id}

- 用途: 删除代理。

当前代理能力本质上是对 Nginx Proxy Manager 的 API 封装。

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

### GET /settings/{section}

- 用途: 获取某个设置节。

### PUT /settings/{section}?key=&value=

- 用途: 更新某个节中的单个键值。
- 当前限制: 仍是 config.ini 级别的键值写入，不具备审计、版本、权限隔离能力。

## 7. 当前 API 对新架构的适配判断

### 可复用

- 应用目录、应用可用列表。
- 应用列表和部分详情聚合逻辑。
- 备份相关接口框架。
- 代理相关封装思路。

### 需要重构

- 认证层，需要从单 API Key 升级到用户、会话、权限体系。
- 设置层，需要脱离 ini 文件和敏感凭据明文管理。
- 任务层，需要把线程和临时内存状态升级为标准任务系统。
- 资源模型，需要从“第三方服务代理”逐步改为“产品自己的资源与控制平面”。

## 8. 对新前端的意义

当前 AppHub 可以作为新前端第一阶段的业务后端基础，但还不能直接承担完整 BFF 或控制平面职责。

最现实的路径是:

1. 先复用现有应用、代理、备份、设置接口中稳定部分。
2. 新增用户认证、权限、日志、服务、文件管理、终端桥接等新 API。
3. 再逐步削弱对 Portainer、Gitea、NPM 当前接口和凭据桥接的依赖。