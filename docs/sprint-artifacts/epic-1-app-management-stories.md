# Epic 1: 应用管理 - User Stories

**Epic ID:** epic-1  
**Epic Title:** 应用管理  
**Status:** In Development  
**Priority:** P0

---

## Story 1-1: 应用目录浏览 API

**Story ID:** 1-1-app-catalog  
**Title:** 实现应用目录浏览功能，支持中英文分类  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 浏览可用的应用目录并按分类查看  
**So that** 我可以快速找到需要安装的应用

### Acceptance Criteria

- [x] AC1: GET `/api/v1/apps/catalog/{locale}` 端点返回应用目录（locale 支持 zh/en）
- [x] AC2: 应用目录从 media.json 加载并解析为 `AppCatalogResponse` 模型
- [x] AC3: 支持按分类筛选应用（数据库、CMS、开发工具等）
- [x] AC4: 响应包含应用的 key、name、category、description、logo_url
- [x] AC5: API 响应时间 < 2秒（包含缓存）
- [x] AC6: 应用目录缓存 3600 秒，减少远程请求
- [x] AC7: locale 参数验证，只接受 zh 或 en

### Tasks

- [x] 实现 `/apps/catalog/{locale}` 路由处理器
  - [x] 添加路径参数验证（regex: `^(zh|en)$`）
  - [x] 调用 `AppManager.get_catalog_apps(locale)` 方法
  - [x] 返回 `list[AppCatalogResponse]` 模型
- [x] 实现 `AppManager.get_catalog_apps()` 业务逻辑
  - [x] 从配置获取 media_url
  - [x] HTTP GET 请求获取 media.json
  - [x] 解析 JSON 为 AppCatalog 对象列表
  - [x] 根据 locale 返回对应语言的数据
  - [x] 实现缓存机制（3600秒）
- [x] 定义 `AppCatalogResponse` Pydantic 模型
  - [x] key: str
  - [x] name: str
  - [x] category: str
  - [x] description: str
  - [x] logo_url: str
  - [x] trademark: str
  - [x] default_port: int
- [x] 编写单元测试
  - [x] 测试 media.json 解析
  - [x] 测试 locale 参数验证
  - [x] 测试缓存机制
  - [x] 测试错误处理（网络失败）
- [x] 编写 API 集成测试
  - [x] 测试 GET /api/v1/apps/catalog/zh
  - [x] 测试 GET /api/v1/apps/catalog/en
  - [x] 测试无效 locale（返回 400）

### Test Scenarios

**场景 1: 成功获取中文应用目录**
```
Given: media.json 可访问
When: GET /api/v1/apps/catalog/zh
Then: 返回 200，包含中文应用列表
And: 每个应用包含 key, name, category
```

**场景 2: 无效的 locale 参数**
```
Given: 任何系统状态
When: GET /api/v1/apps/catalog/fr
Then: 返回 400，错误信息 "Invalid locale"
```

**场景 3: media.json 不可用**
```
Given: media.json URL 返回 404
When: GET /api/v1/apps/catalog/zh
Then: 返回 500，错误信息 "Failed to load catalog"
```

### File List

- `apphub/src/api/v1/routers/app.py` - 路由定义
- `apphub/src/services/app_manager.py` - 业务逻辑
- `apphub/src/schemas/appCatalog.py` - Pydantic 模型
- `apphub/src/core/config.py` - 配置管理
- `tests/test_app_catalog.py` - 单元测试
- `tests/integration/test_app_routes.py` - 集成测试

### Dependencies

- 外部: media.json URL 可访问
- 内部: ConfigManager 配置模块

---

## Story 1-2: 可用应用列表 API

**Story ID:** 1-2-available-apps  
**Title:** 实现获取可用（未安装）应用列表功能  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 查看哪些应用还未安装  
**So that** 我可以选择新应用进行安装

### Acceptance Criteria

- [x] AC1: GET `/api/v1/apps/available/{locale}` 返回未安装的应用列表
- [x] AC2: 过滤掉已安装的应用（通过对比 app key）
- [x] AC3: 返回 `list[AppAvailableResponse]` 格式
- [x] AC4: 支持中英文（locale: zh/en）
- [x] AC5: API 响应时间 < 2秒

### Tasks

- [x] 实现 `/apps/available/{locale}` 路由
  - [x] 路径参数验证（zh|en）
  - [x] 调用 `AppManager.get_available_apps(locale)`
- [x] 实现 `get_available_apps()` 方法
  - [x] 获取所有应用目录
  - [x] 获取已安装应用列表
  - [x] 过滤：catalog - installed
  - [x] 返回可用应用列表
- [x] 定义 `AppAvailableResponse` 模型
- [x] 编写测试
  - [x] 测试过滤逻辑正确
  - [x] 测试返回格式

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/schemas/appAvailable.py`
- `tests/test_available_apps.py`

---

## Story 1-3: 已安装应用列表 API

**Story ID:** 1-3-installed-apps  
**Title:** 获取已安装应用列表并展示状态  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 查看所有已安装的应用及其状态  
**So that** 我可以管理和监控我的应用

### Acceptance Criteria

- [x] AC1: GET `/api/v1/apps` 返回已安装应用列表
- [x] AC2: 支持 endpointId 参数（默认本地 endpoint）
- [x] AC3: 从 Portainer API 获取 Stack 列表
- [x] AC4: 返回应用状态（running, stopped, error）
- [x] AC5: 包含容器信息和环境变量
- [x] AC6: 响应时间 < 3秒

### Tasks

- [x] 实现 `/apps` GET 路由
  - [x] 添加可选 Query 参数 endpointId
  - [x] 调用 `AppManager.get_apps(endpointId)`
- [x] 实现 Portainer API 集成
  - [x] 认证获取 token
  - [x] 调用 GET /api/stacks
  - [x] 解析 Stack 为 AppResponse 模型
  - [x] 聚合容器状态
- [x] 定义 `AppResponse` 模型
  - [x] app_id, app_name, status
  - [x] created_at, containers
  - [x] env_vars
- [x] 错误处理
  - [x] Portainer API 失败处理
  - [x] 认证失败处理
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/external/portainer_client.py`
- `apphub/src/schemas/appResponse.py`
- `tests/test_installed_apps.py`

---

## Story 1-4: 应用详情查询 API

**Story ID:** 1-4-app-detail  
**Title:** 查询单个应用的详细信息  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 查看单个应用的详细配置和运行状态  
**So that** 我可以深入了解应用的运行情况

### Acceptance Criteria

- [x] AC1: GET `/api/v1/apps/{app_id}` 返回应用详细信息
- [x] AC2: 从 Portainer 获取 Stack 详情
- [x] AC3: 包含所有容器信息
- [x] AC4: 应用不存在返回 404
- [x] AC5: 响应时间 < 1秒

### Tasks

- [x] 实现 `/apps/{app_id}` GET 路由
- [x] 实现 `get_app_by_id()` 方法
- [x] Portainer API: GET /stacks/{id}
- [x] 错误处理（404）
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `tests/test_app_detail.py`

---

## Story 1-5: 应用安装功能

**Story ID:** 1-5-app-install  
**Title:** 实现应用一键安装功能（异步）  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 4 days

### User Story

**As a** Websoft9 用户  
**I want to** 通过简单的 API 调用安装应用  
**So that** 我可以快速部署所需的服务

### Acceptance Criteria

- [x] AC1: POST `/api/v1/apps/install` 接收安装请求
- [x] AC2: 支持 appInstall 请求体（app_name, app_id, env, domain）
- [x] AC3: 安装在后台线程执行（非阻塞）
- [x] AC4: 立即返回 200 响应"正在安装"
- [x] AC5: 生成 docker-compose.yml 内容
- [x] AC6: 通过 Portainer API 创建 Stack
- [x] AC7: 安装参数验证（app_name 存在、env 格式正确）
- [x] AC8: 安装失败记录错误日志
- [x] AC9: 防止重复安装同名应用

### Tasks

- [x] 实现 `/apps/install` POST 路由
  - [x] 定义 `appInstall` Pydantic 模型
  - [x] 调用 `install_validate()` 验证
  - [x] 启动后台线程执行安装
  - [x] 立即返回 200 响应
- [x] 实现 `install_validate()` 验证逻辑
  - [x] 检查 app_name 在 media.json 中存在
  - [x] 检查 app_id 未被占用
  - [x] 验证 env 参数格式
  - [x] 验证 endpointId 有效性
- [x] 实现 `AppManager.install_app()` 异步逻辑
  - [x] 从 media.json 获取应用元数据
  - [x] 生成 docker-compose.yml
  - [x] 调用 Portainer API 创建 Stack
  - [x] 等待容器启动完成
  - [x] 记录安装日志
  - [x] 错误处理和清理
- [x] 实现 docker-compose 生成逻辑
  - [x] 从模板生成 compose 文件
  - [x] 注入环境变量
  - [x] 配置网络和卷
- [x] Portainer API 集成
  - [x] POST /api/stacks 创建 Stack
  - [x] 传递 compose 内容和 env
- [x] 编写测试
  - [x] 单元测试：验证逻辑
  - [x] 单元测试：compose 生成
  - [x] 集成测试：完整安装流程
  - [x] 集成测试：错误场景

### Test Scenarios

**场景 1: 成功安装 WordPress**
```
Given: WordPress 在 media.json 中存在
And: app_id "wordpress001" 未被使用
When: POST /api/v1/apps/install
  {
    "app_name": "wordpress",
    "app_id": "wordpress001",
    "env": {"MYSQL_ROOT_PASSWORD": "secret"}
  }
Then: 返回 200 "正在安装"
And: 后台创建 Portainer Stack
And: 容器启动成功
```

**场景 2: 应用不存在**
```
Given: app_name "invalid_app" 不在 media.json
When: POST /api/v1/apps/install
Then: 返回 400 "应用不存在"
```

**场景 3: 重复安装**
```
Given: app_id "wordpress001" 已存在
When: POST /api/v1/apps/install
Then: 返回 409 "应用已安装"
```

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/services/common_check.py`
- `apphub/src/schemas/appInstall.py`
- `apphub/src/utils/compose_generator.py`
- `tests/test_app_install.py`
- `tests/integration/test_install_flow.py`

---

## Story 1-6: 应用生命周期管理（启动/停止/重启）

**Story ID:** 1-6-app-lifecycle  
**Title:** 实现应用的启动、停止、重启操作  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 控制应用的运行状态  
**So that** 我可以按需启动或停止服务

### Acceptance Criteria

- [x] AC1: POST `/api/v1/apps/{app_id}/start` 启动应用（204）
- [x] AC2: POST `/api/v1/apps/{app_id}/stop` 停止应用（204）
- [x] AC3: POST `/api/v1/apps/{app_id}/restart` 重启应用（204）
- [x] AC4: 操作响应时间 < 3秒
- [x] AC5: 应用不存在返回 404
- [x] AC6: 操作失败返回 500 和详细错误

### Tasks

- [x] 实现 `/apps/{app_id}/start` POST 路由
- [x] 实现 `/apps/{app_id}/stop` POST 路由
- [x] 实现 `/apps/{app_id}/restart` POST 路由
- [x] 实现 `start_app()`, `stop_app()`, `restart_app()`
- [x] Portainer API 调用
  - [x] POST /stacks/{id}/start
  - [x] POST /stacks/{id}/stop
  - [x] POST /stacks/{id}/restart
- [x] 错误处理
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `tests/test_app_lifecycle.py`

---

## Story 1-7: 应用重新部署功能（Redeploy）

**Story ID:** 1-7-app-redeploy  
**Title:** 实现应用重新部署功能，支持拉取最新镜像和流式日志  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 3 days

### User Story

**As a** Websoft9 用户  
**I want to** 重新部署应用并获取实时日志  
**So that** 我可以更新应用到最新版本并监控部署过程

### Acceptance Criteria

- [x] AC1: PUT `/api/v1/apps/{app_id}/redeploy` 触发重新部署
- [x] AC2: 支持 pullImage 参数（是否拉取最新镜像）
- [x] AC3: 返回流式日志（StreamingResponse, text/plain）
- [x] AC4: 日志包含时间戳和操作状态
- [x] AC5: 部署成功/失败在日志流中明确标识
- [x] AC6: 错误时返回结构化错误消息

### Tasks

- [x] 实现 `/apps/{app_id}/redeploy` PUT 路由
  - [x] 添加 pullImage Query 参数（bool）
  - [x] 实现异步流式响应
- [x] 实现 `redeploy_app()` 异步方法
  - [x] 使用 asyncio.Queue 传递日志消息
  - [x] 停止现有容器
  - [x] 可选：拉取最新镜像
  - [x] 重新启动容器
  - [x] 发送进度日志到 Queue
- [x] 实现 log_generator() 异步生成器
  - [x] 从 Queue 读取消息
  - [x] 格式化为 JSON 日志行
  - [x] 处理错误和结束信号
  - [x] 返回最终状态
- [x] 错误处理
  - [x] CustomException 转换为结构化错误
  - [x] 未预期异常处理
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `tests/test_app_redeploy.py`

---

## Story 1-8: 应用卸载功能

**Story ID:** 1-8-app-uninstall  
**Title:** 实现应用卸载功能，支持选择是否清除数据  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 卸载不需要的应用  
**So that** 我可以释放系统资源

### Acceptance Criteria

- [x] AC1: DELETE `/api/v1/apps/{app_id}/uninstall` 卸载应用
- [x] AC2: 支持 purge_data 参数（是否删除数据卷）
- [x] AC3: 停止并删除所有容器
- [x] AC4: 删除关联的网络
- [x] AC5: 可选删除数据卷（purge_data=true）
- [x] AC6: 卸载成功返回 204
- [x] AC7: 应用不存在返回 404

### Tasks

- [x] 实现 `/apps/{app_id}/uninstall` DELETE 路由
  - [x] 添加 purge_data Query 参数
- [x] 实现 `uninstall_app()` 方法
  - [x] 调用 Portainer API 删除 Stack
  - [x] 传递 purge_data 参数
  - [x] 验证删除成功
- [x] Portainer API: DELETE /stacks/{id}
- [x] 编写测试
  - [x] 测试保留数据卸载
  - [x] 测试完全清除卸载

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `tests/test_app_uninstall.py`

---

## Story 1-9: 移除空应用和错误应用

**Story ID:** 1-9-app-remove  
**Title:** 实现移除 inactive 和 error 状态应用的功能  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 管理员  
**I want to** 清理系统中的空应用和错误应用记录  
**So that** 保持应用列表整洁

### Acceptance Criteria

- [x] AC1: DELETE `/api/v1/apps/{app_id}/remove` 移除空应用（status=inactive）
- [x] AC2: DELETE `/api/v1/apps/{app_id}/error/remove` 移除错误应用（status=error）
- [x] AC3: 返回 204 状态码
- [x] AC4: 只能删除对应状态的应用

### Tasks

- [x] 实现 `/apps/{app_id}/remove` DELETE 路由
- [x] 实现 `/apps/{app_id}/error/remove` DELETE 路由
- [x] 实现 `remove_app()` 和 `remove_error_app()` 方法
- [x] 状态验证逻辑
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/app.py`
- `apphub/src/services/app_manager.py`
- `tests/test_app_remove.py`

---

**Total Stories: 9**  
**Total Estimated Effort: 18 days**  
**Epic Status: Ready for Sprint Planning**
