# Epic 2: 反向代理管理 - User Stories

**Epic ID:** epic-2  
**Epic Title:** 反向代理管理  
**Status:** In Development  
**Priority:** P0

---

## Story 2-1: 获取应用代理配置列表

**Story ID:** 2-1-get-proxys  
**Title:** 实现获取应用的代理配置列表功能  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 查看应用关联的所有代理配置  
**So that** 我可以了解应用的域名访问配置

### Acceptance Criteria

- [x] AC1: GET `/api/v1/proxys/{app_id}` 返回代理主机列表
- [x] AC2: 支持 endpointId 参数（默认本地）
- [x] AC3: 返回 `list[ProxyHost]` 格式
- [x] AC4: 包含域名、SSL 状态、证书信息
- [x] AC5: 应用不存在返回 404
- [x] AC6: 响应时间 < 1秒

### Tasks

- [x] 实现 `/proxys/{app_id}` GET 路由
  - [x] Path 参数: app_id
  - [x] Query 参数: endpointId (可选)
  - [x] 调用 `AppManager.get_proxys_by_app()`
- [x] 实现 `get_proxys_by_app()` 方法
  - [x] 验证 app_id 存在
  - [x] 调用 NPM API 获取 proxy hosts
  - [x] 过滤出关联该应用的代理
  - [x] 返回代理列表
- [x] 定义 `ProxyHost` Pydantic 模型
  - [x] proxy_id, domain_names
  - [x] forward_host, forward_port
  - [x] ssl_enabled, certificate_id
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/proxy.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/schemas/proxyHosts.py`
- `tests/test_proxy_list.py`

---

## Story 2-2: 创建代理主机

**Story ID:** 2-2-create-proxy  
**Title:** 为应用创建反向代理配置，支持多域名  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 3 days

### User Story

**As a** Websoft9 用户  
**I want to** 为应用配置自定义域名访问  
**So that** 我可以通过友好的域名访问应用

### Acceptance Criteria

- [x] AC1: POST `/api/v1/proxys/{app_id}` 创建代理配置
- [x] AC2: 请求体包含 `domain_names` 数组
- [x] AC3: 自动检测应用容器的 forward_host 和 forward_port
- [x] AC4: 调用 NPM API 创建 proxy host
- [x] AC5: 返回创建的 proxy 配置（包含 proxy_id）
- [x] AC6: 域名格式验证（FQDN 格式）
- [x] AC7: 域名冲突检测（已被使用）
- [x] AC8: 创建时间 < 30秒

### Tasks

- [x] 实现 `/proxys/{app_id}` POST 路由
  - [x] Path 参数: app_id
  - [x] Body: DomainNames 模型
  - [x] 调用 `AppManager.create_proxy_by_app()`
- [x] 实现 `create_proxy_by_app()` 方法
  - [x] 获取应用容器信息（forward_host, port）
  - [x] 验证域名格式（FQDN）
  - [x] 检查域名是否已被使用
  - [x] 调用 ProxyManager 创建代理
  - [x] 返回代理配置
- [x] 实现 ProxyManager.create_proxy_host()
  - [x] 调用 NPM API
  - [x] 传递域名、转发配置
  - [x] 处理 NPM API 错误
- [x] 定义 `DomainNames` 模型
  - [x] domain_names: List[str]
  - [x] 域名格式验证
- [x] 编写测试
  - [x] 测试域名验证
  - [x] 测试域名冲突检测
  - [x] 测试创建成功流程
  - [x] 测试 NPM API 失败场景

### Test Scenarios

**场景 1: 成功创建代理**
```
Given: app_id "wordpress001" 存在
And: 域名 "blog.example.com" 未被使用
When: POST /api/v1/proxys/wordpress001
  {
    "domain_names": ["blog.example.com", "www.blog.example.com"]
  }
Then: 返回 200，包含 proxy_id
And: NPM 中创建了 proxy host
```

**场景 2: 域名格式无效**
```
Given: 任何状态
When: POST /api/v1/proxys/app001
  {
    "domain_names": ["invalid domain"]
  }
Then: 返回 400 "域名格式无效"
```

**场景 3: 域名已被使用**
```
Given: 域名 "blog.example.com" 已配置给其他应用
When: POST /api/v1/proxys/app001
  {
    "domain_names": ["blog.example.com"]
  }
Then: 返回 409 "域名已被使用"
```

### File List

- `apphub/src/api/v1/routers/proxy.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/services/proxy_manager.py`
- `apphub/src/schemas/domainNames.py`
- `apphub/src/schemas/proxyHosts.py`
- `tests/test_proxy_create.py`

---

## Story 2-3: 更新代理配置

**Story ID:** 2-3-update-proxy  
**Title:** 更新代理配置的域名列表  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 修改代理的域名配置  
**So that** 我可以更新或添加新的访问域名

### Acceptance Criteria

- [x] AC1: PUT `/api/v1/proxys/{proxy_id}` 更新代理配置
- [x] AC2: 请求体包含新的 `domain_names` 列表
- [x] AC3: 支持 endpointId 参数
- [x] AC4: 域名格式验证
- [x] AC5: 返回更新后的代理配置
- [x] AC6: proxy_id 不存在返回 404
- [x] AC7: 配置变更生效时间 < 5秒

### Tasks

- [x] 实现 `/proxys/{proxy_id}` PUT 路由
  - [x] Path 参数: proxy_id (int)
  - [x] Body: DomainNames
  - [x] 调用 `AppManager.update_proxy_by_app()`
- [x] 实现 `update_proxy_by_app()` 方法
  - [x] 验证 proxy_id 存在
  - [x] 验证新域名格式
  - [x] 调用 ProxyManager 更新
  - [x] 返回更新结果
- [x] 实现 ProxyManager.update_proxy_host()
  - [x] 调用 NPM API PUT
  - [x] 错误处理
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/proxy.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/services/proxy_manager.py`
- `tests/test_proxy_update.py`

---

## Story 2-4: 删除代理配置

**Story ID:** 2-4-delete-proxy  
**Title:** 删除应用的代理配置  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 删除不需要的代理配置  
**So that** 我可以停止通过该域名访问应用

### Acceptance Criteria

- [x] AC1: DELETE `/api/v1/proxys/{proxy_id}` 删除代理
- [x] AC2: 从 NPM 中删除 proxy host 配置
- [x] AC3: 删除成功返回 204
- [x] AC4: proxy_id 不存在返回 404
- [x] AC5: 删除不会影响应用运行（只删除代理）
- [x] AC6: 特殊处理：检测 client_host 避免删除当前访问的代理

### Tasks

- [x] 实现 `/proxys/{proxy_id}` DELETE 路由
  - [x] Path 参数: proxy_id
  - [x] 从 Request headers 获取 Host
  - [x] 调用 `AppManager.remove_proxy_by_id()`
- [x] 实现 `remove_proxy_by_id()` 方法
  - [x] 验证 proxy_id 存在
  - [x] 检查 client_host 是否匹配该代理域名
  - [x] 如果匹配，阻止删除（防止自己删除自己）
  - [x] 调用 ProxyManager 删除
- [x] 实现 ProxyManager.delete_proxy_host()
  - [x] 调用 NPM API DELETE
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/proxy.py`
- `apphub/src/services/app_manager.py`
- `apphub/src/services/proxy_manager.py`
- `tests/test_proxy_delete.py`

---

## Story 2-5: 获取 SSL 证书列表

**Story ID:** 2-5-list-certificates  
**Title:** 获取系统中所有 SSL 证书信息  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 管理员  
**I want to** 查看所有 SSL 证书及其过期状态  
**So that** 我可以监控证书健康状况

### Acceptance Criteria

- [x] AC1: GET `/api/v1/proxys/ssl/certificates` 返回证书列表
- [x] AC2: 包含证书 ID、域名、过期时间、状态
- [x] AC3: 区分 Let's Encrypt 和自定义证书
- [x] AC4: 标识即将过期的证书（< 30天）
- [x] AC5: 返回 `list[dict]` 格式

### Tasks

- [x] 实现 `/proxys/ssl/certificates` GET 路由
  - [x] 调用 `ProxyManager.get_all_certificates()`
- [x] 实现 `get_all_certificates()` 方法
  - [x] 调用 NPM API 获取证书
  - [x] 解析证书信息
  - [x] 计算过期剩余天数
  - [x] 标识即将过期证书
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/proxy.py`
- `apphub/src/services/proxy_manager.py`
- `tests/test_ssl_certificates.py`

---

## Story 2-6: NPM API 客户端集成

**Story ID:** 2-6-npm-client  
**Title:** 实现 Nginx Proxy Manager API 客户端  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 3 days

### User Story

**As a** 开发人员  
**I want to** 封装 NPM API 调用逻辑  
**So that** 其他模块可以方便地使用代理管理功能

### Acceptance Criteria

- [x] AC1: 实现 Token 认证机制
- [x] AC2: 封装 CRUD 操作方法
- [x] AC3: 实现错误处理和重试
- [x] AC4: 支持配置管理（URL、凭据）
- [x] AC5: 记录 API 调用日志

### Tasks

- [x] 创建 `ProxyManager` 类
  - [x] 初始化：加载配置、获取 token
  - [x] `get_token()` - NPM 认证
  - [x] `get_all_certificates()` - 获取证书列表
  - [x] `create_proxy_host()` - 创建代理
  - [x] `update_proxy_host()` - 更新代理
  - [x] `delete_proxy_host()` - 删除代理
  - [x] `get_proxy_hosts()` - 获取代理列表
- [x] 实现 HTTP 客户端封装
  - [x] 使用 requests 或 httpx
  - [x] 添加 Authorization header
  - [x] 错误响应处理
  - [x] 超时控制
  - [x] 重试机制（3次）
- [x] 配置管理
  - [x] 从 ConfigManager 读取 NPM 配置
  - [x] URL、用户名、密码
- [x] 日志记录
  - [x] API 请求日志
  - [x] 错误日志
- [x] 编写单元测试
  - [x] Mock NPM API 响应
  - [x] 测试认证流程
  - [x] 测试 CRUD 操作
  - [x] 测试错误处理

### File List

- `apphub/src/services/proxy_manager.py` - 主类
- `apphub/src/core/config.py` - 配置
- `tests/test_proxy_manager.py` - 单元测试
- `tests/fixtures/npm_responses.json` - Mock 数据

---

## Story 2-7: Let's Encrypt 证书自动申请（未来增强）

**Story ID:** 2-7-letsencrypt-auto  
**Title:** 创建代理时自动申请 Let's Encrypt 证书  
**Priority:** P1  
**Status:** backlog  
**Estimated Effort:** 4 days

### User Story

**As a** Websoft9 用户  
**I want to** 创建代理时自动申请 HTTPS 证书  
**So that** 我可以直接使用 HTTPS 访问应用

### Acceptance Criteria

- [ ] AC1: 创建代理时可选启用 SSL
- [ ] AC2: 自动调用 NPM Let's Encrypt 集成
- [ ] AC3: HTTP-01 挑战自动完成
- [ ] AC4: 证书申请成功率 > 95%
- [ ] AC5: 失败时返回详细错误信息

### Tasks

- [ ] 扩展 `create_proxy_host()` 支持 SSL 选项
- [ ] 实现证书申请逻辑
- [ ] DNS 预检查（域名是否解析）
- [ ] 证书申请状态轮询
- [ ] 错误处理和用户提示
- [ ] 编写测试（使用 Let's Encrypt Staging）

### File List

- `apphub/src/services/proxy_manager.py`
- `apphub/src/utils/dns_checker.py`
- `tests/test_letsencrypt.py`

### Dependencies

- DNS 域名必须解析到服务器
- 80 端口可访问

---

## Story 2-8: SSL 证书自动续期（未来增强）

**Story ID:** 2-8-cert-renewal  
**Title:** 实现 SSL 证书自动续期服务  
**Priority:** P1  
**Status:** backlog  
**Estimated Effort:** 3 days

### User Story

**As a** Websoft9 管理员  
**I want to** SSL 证书在过期前自动续期  
**So that** 我不用手动管理证书生命周期

### Acceptance Criteria

- [ ] AC1: 定时任务每天检查证书
- [ ] AC2: 过期前 30 天自动续期
- [ ] AC3: 续期失败发送告警
- [ ] AC4: 续期成功记录日志

### Tasks

- [ ] 实现定时任务服务
- [ ] 证书过期检测逻辑
- [ ] 调用 NPM 续期 API
- [ ] 告警通知机制
- [ ] 编写测试

### File List

- `apphub/src/services/cert_renewal_service.py`
- `apphub/src/tasks/scheduler.py`
- `tests/test_cert_renewal.py`

---

**Total Stories: 8** (6 ready-for-dev + 2 backlog)  
**Total Estimated Effort: 16 days** (ready stories: 11 days)  
**Epic Status: Ready for Sprint Planning**
