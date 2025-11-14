# GitHub Copilot Instructions for Websoft9

## 项目概述

Websoft9 是一个基于容器化的应用管理平台，旨在简化企业应用的部署、管理和维护。该项目由 Cockpit 系统管理界面和四个核心容器服务组成，为用户提供完整的应用生命周期管理解决方案。

### 核心架构组件

1. **Cockpit** - 系统管理界面，提供 Web 控制台
2. **AppHub** - 自研应用管理服务 (Python + FastAPI)
3. **Deployment** - 基于 Portainer 的容器部署管理
4. **Git** - 基于 Gitea 的代码仓库服务
5. **Proxy** - 基于 Nginx 的反向代理和网关服务

## 技术栈

### 主要技术
- **后端**: Python 3.11+, FastAPI, Docker, Docker Compose
- **前端**: HTML5, JavaScript, Bootstrap, CSS3
- **数据库**: SQLite, PostgreSQL (可选)
- **容器**: Docker, Docker Compose
- **代理**: Nginx, 反向代理配置
- **系统**: Linux (主要支持 Ubuntu, CentOS, Debian)

### 开发工具
- **API文档**: FastAPI 自动生成的 OpenAPI/Swagger
- **日志**: Python logging, 结构化日志
- **测试**: pytest (Python 测试框架)
- **构建**: Docker 多阶段构建

## 项目结构

```
websoft9/
├── apphub/                     # 主要应用服务 (Python FastAPI)
│   ├── src/                    # 源代码目录
│   │   ├── api/v1/            # API 路由定义
│   │   ├── core/              # 核心业务逻辑
│   │   ├── schemas/           # Pydantic 模型定义
│   │   └── main.py            # FastAPI 应用入口
│   ├── requirements.txt        # Python 依赖
│   └── README.md              # 服务文档
├── docker/                    # Docker 容器配置
│   ├── docker-compose.yml     # 主要服务编排
│   ├── proxy/config/          # Nginx 代理配置
│   └── .env                   # 环境变量配置
├── cockpit/                   # Cockpit 系统管理配置
├── scripts/                   # 自动化脚本
├── tools/                     # 工具和实用程序
└── docs/                      # 项目文档
```

## 开发指南

### 代码规范

#### Python 代码规范
- **使用 Python 3.11+ 特性**，包括类型提示和异步编程
- **遵循 PEP 8** 代码风格标准
- **使用 FastAPI 最佳实践**:
  - 路径操作函数使用类型提示
  - 使用 Pydantic 模型进行数据验证
  - 实现适当的错误处理和状态码
- **异步编程**: 优先使用 `async/await` 模式
- **日志记录**: 使用结构化日志，包含适当的日志级别

```python
# ✅ 好的示例
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class ItemRequest(BaseModel):
    name: str
    description: str | None = None

@app.post("/api/v1/items", response_model=ItemResponse)
async def create_item(item: ItemRequest) -> ItemResponse:
    """创建新项目"""
    try:
        # 业务逻辑
        result = await item_service.create(item)
        logger.info(f"Item created: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Invalid item data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item data"
        )
```

#### Docker 和配置规范
- **容器命名**: 使用 `websoft9-{service}` 格式
- **网络**: 所有服务使用 `websoft9` 网络
- **卷管理**: 使用命名卷进行数据持久化
- **环境变量**: 敏感配置使用 `.env` 文件

#### API 设计规范
- **RESTful 设计**: 遵循 REST API 设计原则
- **版本控制**: API 路径包含版本号 (`/api/v1/`)
- **响应格式**: 统一的 JSON 响应格式
- **错误处理**: 使用标准 HTTP 状态码和错误消息

### 常见开发任务

#### 添加新的 API 端点
1. 在 `apphub/src/api/v1/routers/` 中创建新路由文件
2. 定义 Pydantic 模型在 `schemas/` 目录
3. 实现业务逻辑在 `core/` 目录
4. 添加适当的错误处理和日志记录
5. 更新 API 文档

#### 修改 Nginx 配置
1. 编辑 `docker/proxy/config/initproxy.conf`
2. 测试配置: `docker exec websoft9-proxy nginx -t`
3. 重新加载: `docker exec websoft9-proxy nginx -s reload`

#### 容器服务管理
```bash
# 重启所有服务
docker-compose -f docker/docker-compose.yml restart

# 重启特定服务
docker-compose -f docker/docker-compose.yml restart apphub

# 查看日志
docker logs websoft9-apphub --tail 50 -f

# 进入容器调试
docker exec -it websoft9-apphub bash
```

## 开发工作流

### 本地开发环境设置
```bash
# 1. 克隆项目
git clone https://github.com/websoft9/websoft9.git
cd websoft9

# 2. 设置 Python 环境 (AppHub)
cd apphub
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 启动开发服务器
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8080

# 4. 启动完整环境
cd ../docker
docker-compose up -d
```

### 调试和测试

#### AppHub (FastAPI) 调试
- **API 文档**: 访问 `http://localhost:8080/api/docs`
- **日志调试**: 使用 `logger.debug()` 添加调试信息
- **交互式调试**: 使用 `pytest` 运行测试

```python
# 在代码中添加调试断点
import pdb; pdb.set_trace()

# 或者使用现代调试器
import ipdb; ipdb.set_trace()
```

#### 容器服务调试
```bash
# 检查容器状态
docker ps -a

# 查看服务健康状态
docker-compose ps

# 进入容器调试
docker exec -it websoft9-apphub /bin/bash
```

### 部署和发布

#### 构建和测试
```bash
# 构建 Docker 镜像
docker build -t websoft9dev/apphub:latest apphub/

# 运行集成测试
docker-compose -f docker/docker-compose.yml up -d
# 运行测试套件
pytest apphub/tests/
```

## AI 辅助开发建议

### 使用 GitHub Copilot 时的最佳实践

#### 1. 上下文提供
为 Copilot 提供清晰的上下文信息：
```python
# 为 Websoft9 AppHub 创建一个新的 API 端点
# 用于管理应用部署状态，支持启动、停止、重启操作
# 需要包含权限验证和错误处理
```

#### 2. 类型提示和文档字符串
```python
async def deploy_application(
    app_id: str, 
    deployment_config: DeploymentConfig
) -> DeploymentResult:
    """
    部署应用到 Websoft9 平台
    
    Args:
        app_id: 应用唯一标识符
        deployment_config: 部署配置信息
    
    Returns:
        DeploymentResult: 部署结果和状态信息
        
    Raises:
        HTTPException: 当部署失败时
    """
```

#### 3. 常用代码模式

##### FastAPI 路由模式
```python
# Websoft9 标准 API 路由模式
@router.get("/apps/{app_id}/status")
async def get_app_status(
    app_id: str = Path(..., description="应用ID"),
    current_user: User = Depends(get_current_user)
) -> AppStatus:
    """获取应用状态"""
```

##### 错误处理模式
```python
# Websoft9 标准错误处理
try:
    result = await service.operation()
    return result
except ServiceError as e:
    logger.error(f"Service error: {e}")
    raise HTTPException(status_code=500, detail="Internal service error")
except ValueError as e:
    logger.warning(f"Invalid input: {e}")
    raise HTTPException(status_code=400, detail=str(e))
```

##### Docker 操作模式
```python
# Websoft9 Docker 容器操作模式
import docker
client = docker.from_env()

try:
    container = client.containers.get(container_name)
    container.restart()
    logger.info(f"Container {container_name} restarted successfully")
except docker.errors.NotFound:
    raise HTTPException(status_code=404, detail="Container not found")
```

### 提示词建议

#### 针对 Websoft9 的特定提示
- "为 Websoft9 AppHub 创建一个管理 Docker 容器的 API"
- "实现 Websoft9 应用生命周期管理功能"
- "为 Websoft9 代理服务添加新的路由配置"
- "创建 Websoft9 应用部署的状态监控功能"

#### 最佳提示格式
```
# 上下文: 在 Websoft9 AppHub (FastAPI) 中
# 任务: 创建应用备份管理 API
# 要求: 
# - 支持创建、删除、恢复备份
# - 包含进度跟踪
# - 异步操作
# - 完整的错误处理
# - 符合 Websoft9 代码规范
```

## 常见问题和解决方案

### 开发常见问题

#### Q: API 认证失败
A: 检查 `x-api-key` 请求头是否正确设置，确认 API 密钥配置：
```python
# 在 AppHub 中验证 API 密钥
API_KEY = ConfigManager().get_value("api_key", "key")
```

#### Q: 容器间通信问题
A: 确保所有容器在同一 Docker 网络 (`websoft9`)：
```yaml
networks:
  default:
    name: websoft9
    external: true
```

#### Q: 代理配置不生效
A: 检查 Nginx 配置并重新加载：
```bash
docker exec websoft9-proxy nginx -t
docker exec websoft9-proxy nginx -s reload
```

### 性能优化建议

1. **异步编程**: 在 FastAPI 中使用异步操作
2. **连接池**: 配置数据库连接池
3. **缓存策略**: 实现适当的缓存机制
4. **日志优化**: 避免过多的调试日志在生产环境

### 安全考虑

1. **API 密钥管理**: 使用环境变量存储敏感信息
2. **输入验证**: 使用 Pydantic 模型验证输入
3. **CORS 配置**: 正确配置跨域资源共享
4. **容器安全**: 使用非 root 用户运行服务

## 贡献指南

### 提交代码前检查清单
- [ ] 代码遵循项目规范
- [ ] 添加了适当的类型提示
- [ ] 包含单元测试
- [ ] 更新了相关文档
- [ ] 通过了所有测试
- [ ] 适当的日志记录

### Git 提交格式
```
<type>(<scope>): <description>

feat(apphub): add application backup API
fix(proxy): resolve CORS issue for deployment service
docs(readme): update installation instructions
```

### 代码审查关注点
1. **安全性**: API 权限验证，输入验证
2. **性能**: 异步操作，数据库查询优化
3. **可维护性**: 代码清晰度，注释完整性
4. **测试覆盖率**: 关键业务逻辑的测试

---

这份指南将帮助您和 AI 助手更有效地协作开发 Websoft9 项目。请根据项目发展持续更新此文档。
