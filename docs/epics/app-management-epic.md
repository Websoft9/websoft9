# Epic: 应用管理

**关联 PRD:** [FR-APP-001](../prd.md#21-应用管理)  
**负责人:** Product Manager  
**状态:** In Development  
**优先级:** P0 (必需)  
**预估工作量:** 4-5 周

---

## 1. Epic 概述

### 1.1 业务目标

提供完整的容器化应用生命周期管理能力，支持从应用目录浏览、一键安装到运维管理的全流程。

### 1.2 核心价值

- 用户可快速浏览并安装 200+ 开源应用
- 通过 docker-compose 实现标准化部署
- 集成 Portainer 实现可视化容器管理
- 应用状态实时监控和日志查看
- 简化的运维操作（启动、停止、重启、卸载）

### 1.3 验收标准

✅ 应用目录支持分类浏览（中英文）  
✅ 应用安装成功率 > 95%  
✅ 平均安装时间 < 2分钟  
✅ 应用状态变更响应 < 3秒  
✅ 卸载应用清理所有相关资源  
✅ 实时日志查看无延迟 (< 500ms)  

---

## 2. 技术规范

### 2.1 架构设计

#### 系统架构

```
用户请求 → AppHub API → App Manager Service
                              ↓
                        Portainer API
                              ↓
                        Docker Engine
```

#### 数据流

```
应用目录 (media.json) → 解析元数据 → API 响应
安装请求 → 生成 docker-compose → Portainer Stack → Docker 部署
```

### 2.2 API 端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/v1/apps/catalog/{locale}` | GET | 获取应用目录（locale: zh/en） | API Key |
| `/api/v1/apps/available/{locale}` | GET | 获取可用应用列表（未安装） | API Key |
| `/api/v1/apps` | GET | 获取已安装应用列表 | API Key |
| `/api/v1/apps/{app_id}` | GET | 获取应用详情 | API Key |
| `/api/v1/apps/install` | POST | 安装应用（异步后台执行） | API Key |
| `/api/v1/apps/{app_id}/start` | POST | 启动应用 | API Key |
| `/api/v1/apps/{app_id}/stop` | POST | 停止应用 | API Key |
| `/api/v1/apps/{app_id}/restart` | POST | 重启应用 | API Key |
| `/api/v1/apps/{app_id}/redeploy` | PUT | 重新部署应用（支持拉取镜像，流式日志） | API Key |
| `/api/v1/apps/{app_id}/uninstall` | DELETE | 卸载应用（支持清除数据） | API Key |
| `/api/v1/apps/{app_id}/remove` | DELETE | 移除空应用（状态为inactive） | API Key |
| `/api/v1/apps/{app_id}/error/remove` | DELETE | 移除错误应用（状态为error） | API Key |

#### 示例：安装应用

**请求:**
```http
POST /api/v1/apps/install
X-API-Key: <key>
Content-Type: application/json

{
  "app_name": "wordpress",
  "app_id": "wordpress001",
  "endpointId": 1,
  "domain": "myblog.example.com",
  "env": {
    "MYSQL_ROOT_PASSWORD": "secret123",
    "WORDPRESS_DB_NAME": "wp_db"
  }
}
```

**响应:**
```json
{
  "code": 200,
  "message": "App installed successfully",
  "data": {
    "app_id": "wordpress001",
    "app_name": "wordpress",
    "status": "running",
    "domain": "myblog.example.com",
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### 2.3 数据模型

#### 应用元数据（media.json）

```python
class AppCatalog(BaseModel):
    key: str                           # 应用唯一标识
    name: str                          # 应用名称
    trademark: str                     # 商标名
    category: str                      # 分类
    description: str                   # 描述
    compose_file: str                  # docker-compose.yml 路径
    logo_url: str                      # Logo URL
    requirements: Dict[str, Any]       # 系统要求
    default_port: int                  # 默认端口
```

#### 已安装应用（从 Portainer）

```python
class InstalledApp(BaseModel):
    app_id: str                        # Stack ID
    app_name: str                      # 应用名称
    status: str                        # running, stopped, error
    created_at: datetime
    containers: List[Dict]             # 容器列表
    env_vars: Dict[str, str]           # 环境变量
```

### 2.4 核心服务设计

#### app_manager.py

```python
class AppManager:
    def __init__(self):
        self.portainer = PortainerAPI()
        self.media = self.load_media_catalog()
    
    def get_catalog_apps(self, locale: str) -> List[AppCatalog]:
        """获取应用目录"""
        pass
    
    def get_available_apps(self, locale: str) -> List[Dict]:
        """获取可用应用（未安装）"""
        installed = self.get_apps()
        all_apps = self.get_catalog_apps(locale)
        return [app for app in all_apps if app.key not in installed]
    
    def install_app(self, app_install: AppInstall) -> Dict:
        """
        安装应用流程:
        1. 验证应用是否存在
        2. 生成 docker-compose.yml
        3. 通过 Portainer 创建 Stack
        4. 等待容器启动
        5. 返回安装结果
        """
        pass
    
    def start_app(self, app_id: str) -> Dict:
        """启动应用 - 调用 Portainer Stack Start"""
        pass
    
    def stop_app(self, app_id: str) -> Dict:
        """停止应用 - 调用 Portainer Stack Stop"""
        pass
    
    def uninstall_app(self, app_id: str, remove_volumes: bool = False) -> Dict:
        """
        卸载应用:
        1. 停止所有容器
        2. 删除容器
        3. 删除网络
        4. 可选删除数据卷
        """
        pass
```

### 2.5 与 Portainer 集成

```python
class PortainerAPI:
    def __init__(self):
        self.base_url = "http://portainer:9000/api"
        self.token = self.authenticate()
    
    def create_stack(self, stack_name: str, compose_content: str, 
                     endpoint_id: int, env: Dict) -> Dict:
        """创建 Stack"""
        url = f"{self.base_url}/stacks"
        payload = {
            "Name": stack_name,
            "StackFileContent": compose_content,
            "Env": [{"name": k, "value": v} for k, v in env.items()]
        }
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def start_stack(self, stack_id: int, endpoint_id: int) -> Dict:
        """启动 Stack"""
        url = f"{self.base_url}/stacks/{stack_id}/start"
        response = requests.post(url, params={"endpointId": endpoint_id})
        return response.json()
    
    def delete_stack(self, stack_id: int, endpoint_id: int) -> None:
        """删除 Stack"""
        url = f"{self.base_url}/stacks/{stack_id}"
        requests.delete(url, params={"endpointId": endpoint_id})
```

### 2.6 配置

```yaml
# config/app.yaml
app_management:
  media_url: "https://websoft9.github.io/docker-library/media.json"
  cache_duration: 3600  # 应用目录缓存时间（秒）
  
  portainer:
    url: "http://portainer:9000"
    username: "admin"
    password: "${PORTAINER_PASSWORD}"
  
  defaults:
    network_mode: "bridge"
    restart_policy: "unless-stopped"
    compose_version: "3.8"
  
  limits:
    max_concurrent_installs: 3
    install_timeout: 300  # 5分钟
```

---

## 3. Stories 拆分

### Story 1: 应用目录浏览

**优先级:** P0  
**工作量:** 2 天

**任务:**
- 实现 `/apps/catalog/{locale}` 端点
- 从 media.json 加载应用元数据
- 支持中英文分类
- 添加缓存机制
- 编写单元测试

### Story 2: 应用安装流程

**优先级:** P0  
**工作量:** 4 天

**任务:**
- 实现 `/apps/install` 端点
- 生成 docker-compose 文件
- Portainer Stack 创建逻辑
- 安装参数验证
- 错误处理和回滚
- 编写集成测试

### Story 3: 应用生命周期管理

**优先级:** P0  
**工作量:** 3 天

**任务:**
- 实现启动/停止/重启端点
- Portainer API 集成
- 状态同步机制
- 编写功能测试

### Story 4: 应用卸载

**优先级:** P0  
**工作量:** 2 天

**任务:**
- 实现 `/apps/{app_id}/uninstall` 端点
- 资源清理逻辑（容器、网络、卷）
- 卸载确认机制
- 编写清理测试

### Story 5: 应用日志查看

**优先级:** P1  
**工作量:** 2 天

**任务:**
- 实现 `/apps/{app_id}/logs` 端点
- 实时日志流式传输
- 日志过滤和搜索
- 编写日志测试

### Story 6: 已安装应用列表

**优先级:** P0  
**工作量:** 2 天

**任务:**
- 实现 `/apps` 端点
- 从 Portainer 获取 Stack 列表
- 状态聚合和格式化
- 编写查询测试

---

## 4. 依赖关系

### 技术依赖

- **Docker Engine** 20.10+
- **Portainer** 2.19+
- **FastAPI** 0.104+
- **Pydantic** 2.0+

### 模块依赖

- **配置模块** - 读取系统配置
- **日志模块** - 记录操作日志
- **API Key 认证** - 接口安全验证

### 外部依赖

- **media.json** - 应用元数据（GitHub）
- **Docker Registry** - 镜像仓库

---

## 5. 风险与挑战

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Portainer API 变更 | 中 | 版本锁定，API 变更监控 |
| 应用安装失败 | 高 | 详细错误日志，自动回滚机制 |
| 并发安装冲突 | 中 | 队列机制，限制并发数 |
| Docker 资源不足 | 高 | 安装前资源检查，磁盘空间预警 |
| 应用目录不可用 | 中 | 本地缓存，降级方案 |

---

## 6. 测试策略

### 单元测试

- 应用元数据解析
- docker-compose 生成逻辑
- 参数验证规则
- API 响应格式化

### 集成测试

- 完整安装流程（选择 → 安装 → 运行）
- Portainer API 调用
- 错误场景处理
- 卸载清理验证

### 性能测试

- 应用目录加载时间 < 2秒
- 并发安装 3 个应用
- 1000+ 应用目录响应时间

### 用户验收测试

- 安装 WordPress 并访问
- 安装 GitLab 并配置
- 批量安装常用应用组合

---

## 7. 监控指标

```python
# Prometheus 指标
app_install_total                      # 应用安装总数
app_install_success_total              # 安装成功数
app_install_failed_total               # 安装失败数
app_install_duration_seconds           # 安装耗时
app_uninstall_total                    # 卸载总数
app_running_total                      # 运行中应用数
app_api_request_duration_seconds       # API 响应时间
```

---

## 附录

### A. 错误码定义

| 错误码 | HTTP | 说明 |
|--------|------|------|
| APP_NOT_FOUND | 404 | 应用不存在 |
| APP_ALREADY_INSTALLED | 409 | 应用已安装 |
| APP_INSTALL_FAILED | 500 | 安装失败 |
| APP_START_FAILED | 500 | 启动失败 |
| APP_STOP_FAILED | 500 | 停止失败 |
| APP_INVALID_CONFIG | 400 | 配置参数无效 |
| PORTAINER_API_ERROR | 502 | Portainer API 错误 |
| DOCKER_RESOURCE_INSUFFICIENT | 507 | Docker 资源不足 |

### B. 相关文档

- [PRD - 应用管理](../prd.md#21-应用管理)
- [技术架构文档](../architecture.md)
- [Portainer API 文档](https://docs.portainer.io/api/docs)

---

**文档维护:** PM Agent  
**最后更新:** 2026-01-05
