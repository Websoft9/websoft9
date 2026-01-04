# API 设计规范

**Websoft9 项目 - FastAPI 最佳实践**

**创建日期**: 2026-01-04  
**维护者**: Winston (Architect Agent)  
**版本**: 1.0  
**状态**: Active

---

## 目录

1. [RESTful API 规范](#1-restful-api-规范)
2. [HTTP 方法](#2-http-方法)
3. [请求规范](#3-请求规范)
4. [响应规范](#4-响应规范)
5. [错误处理](#5-错误处理)
6. [认证与授权](#6-认证与授权)
7. [分页与过滤](#7-分页与过滤)
8. [异步操作](#8-异步操作)
9. [API 文档](#9-api-文档)
10. [最佳实践](#10-最佳实践)

---

## 1. RESTful API 规范

### 1.1 基本原则

- **资源导向**: URL 表示资源,HTTP 方法表示操作
- **无状态**: 每个请求包含完整的认证和上下文信息
- **统一接口**: 使用标准的 HTTP 方法和状态码
- **异步优先**: 所有 I/O 操作使用 async/await

### 1.2 URL 设计

#### 1.2.1 命名规范

```python
# ✅ 推荐
GET  /api/v1/apps              # 资源用复数名词
GET  /api/v1/apps/myapp        # 使用 app_name 标识具体资源
POST /api/v1/apps              # 创建资源
GET  /api/v1/apps/myapp/ports  # 嵌套资源

# ❌ 避免
GET  /api/v1/getApps           # 不要在 URL 中包含动词
GET  /api/v1/app               # 不要使用单数
GET  /api/v1/apps-list         # 不要使用连字符表示操作
```

#### 1.2.2 版本控制

```python
# URL 路径版本（当前采用）
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/apps")
async def list_apps():
    pass

# 未来版本升级
router_v2 = APIRouter(prefix="/api/v2")
```

#### 1.2.3 资源层级

```python
# 浅层级（推荐）
GET /api/v1/apps/{app_name}/ports

# 深层级（避免超过 3 层）
# ❌ GET /api/v1/apps/{app_name}/containers/{container_id}/logs/files
# ✅ GET /api/v1/containers/{container_id}/logs
```

---

## 2. HTTP 方法

### 2.1 标准方法

| 方法 | 用途 | 幂等性 | 安全性 | Websoft9 示例 |
|------|------|--------|--------|---------------|
| **GET** | 查询资源 | ✅ | ✅ | `GET /api/v1/apps/wordpress` |
| **POST** | 创建资源 | ❌ | ❌ | `POST /api/v1/apps` |
| **PUT** | 完整更新资源 | ✅ | ❌ | `PUT /api/v1/apps/wordpress` |
| **PATCH** | 部分更新资源 | ✅ | ❌ | `PATCH /api/v1/apps/wordpress` |
| **DELETE** | 删除资源 | ✅ | ❌ | `DELETE /api/v1/apps/wordpress` |

### 2.2 FastAPI 实现示例

```python
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/apps", tags=["applications"])

# Pydantic Schema
class AppCreate(BaseModel):
    app_name: str
    image: str
    domain: Optional[str] = None
    ports: Optional[List[int]] = []

class AppResponse(BaseModel):
    app_name: str
    status: str
    image: str
    created_at: str

# GET - 列表查询
@router.get("/", response_model=List[AppResponse])
async def list_apps(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> List[AppResponse]:
    """
    获取应用列表
    
    Args:
        status: 过滤状态 (running, stopped, error)
        page: 页码
        page_size: 每页大小
        
    Returns:
        应用列表
    """
    try:
        apps = await app_service.list_apps(status=status, page=page, page_size=page_size)
        logger.info(f"Listed {len(apps)} applications")
        return apps
    except Exception as e:
        logger.exception(f"Failed to list applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# GET - 详情查询
@router.get("/{app_name}", response_model=AppResponse)
async def get_app(app_name: str) -> AppResponse:
    """
    获取应用详情
    
    Args:
        app_name: 应用名称
        
    Returns:
        应用详细信息
    """
    try:
        app = await app_service.get_app(app_name)
        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {app_name} not found"
            )
        return app
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get application {app_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# POST - 创建资源
@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_app(app: AppCreate) -> AppResponse:
    """
    创建新应用
    
    Args:
        app: 应用配置
        
    Returns:
        创建的应用信息
    """
    try:
        # 验证应用名称唯一性
        existing = await app_service.get_app(app.app_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Application {app.app_name} already exists"
            )
        
        # 创建应用
        result = await app_service.create_app(app)
        logger.info(f"Application created: {result.app_name}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid application config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Failed to create application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# PATCH - 部分更新
@router.patch("/{app_name}", response_model=AppResponse)
async def update_app(app_name: str, updates: dict) -> AppResponse:
    """
    部分更新应用配置
    
    Args:
        app_name: 应用名称
        updates: 更新字段
        
    Returns:
        更新后的应用信息
    """
    try:
        result = await app_service.update_app(app_name, updates)
        logger.info(f"Application updated: {app_name}")
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Failed to update application {app_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# DELETE - 删除资源
@router.delete("/{app_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(app_name: str):
    """
    删除应用
    
    Args:
        app_name: 应用名称
    """
    try:
        await app_service.delete_app(app_name)
        logger.info(f"Application deleted: {app_name}")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Failed to delete application {app_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
```

---

## 3. 请求规范

### 3.1 请求头

```http
# 必需的请求头
Content-Type: application/json
Accept: application/json
Authorization: Bearer <token>

# 可选的请求头
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000  # 请求追踪 ID
X-Client-Version: 2.0.0                             # 客户端版本
Accept-Language: zh-CN,en                           # 语言偏好
```

### 3.2 查询参数

```python
from fastapi import Query
from typing import Optional

@router.get("/apps")
async def list_apps(
    # 分页
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    
    # 过滤
    status: Optional[str] = Query(None, regex="^(running|stopped|error)$"),
    
    # 排序
    sort: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    
    # 搜索
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    
    # 字段选择
    fields: Optional[str] = Query(None, description="逗号分隔的字段列表")
):
    pass
```

### 3.3 请求体验证

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List

class AppCreate(BaseModel):
    app_name: str = Field(..., min_length=3, max_length=50, regex="^[a-z0-9-]+$")
    image: str = Field(..., description="Docker 镜像名称")
    domain: Optional[str] = Field(None, regex="^[a-z0-9.-]+$")
    ports: List[int] = Field(default_factory=list)
    env_vars: Optional[dict] = Field(default_factory=dict)
    
    @validator('app_name')
    def validate_app_name(cls, v):
        """验证应用名称"""
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('应用名称不能以连字符开头或结尾')
        return v
    
    @validator('ports')
    def validate_ports(cls, v):
        """验证端口号范围"""
        for port in v:
            if not (1024 <= port <= 65535):
                raise ValueError(f'端口号 {port} 超出范围 (1024-65535)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "app_name": "wordpress",
                "image": "wordpress:latest",
                "domain": "blog.example.com",
                "ports": [8080],
                "env_vars": {
                    "WORDPRESS_DB_HOST": "mysql",
                    "WORDPRESS_DB_NAME": "wordpress"
                }
            }
        }
```

---

## 4. 响应规范

### 4.1 统一响应格式

#### 4.1.1 成功响应

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ResponseModel(BaseModel, Generic[T]):
    """统一响应模型"""
    success: bool = True
    code: int = 200
    message: str = "操作成功"
    data: Optional[T] = None

# 使用示例
@router.get("/apps/{app_name}", response_model=ResponseModel[AppResponse])
async def get_app(app_name: str):
    app = await app_service.get_app(app_name)
    return ResponseModel(
        success=True,
        code=200,
        message="获取成功",
        data=app
    )
```

**简化版本（推荐）**:

```python
# FastAPI 自动处理成功响应,直接返回数据模型
@router.get("/apps/{app_name}", response_model=AppResponse)
async def get_app(app_name: str) -> AppResponse:
    return await app_service.get_app(app_name)

# 列表响应
class AppListResponse(BaseModel):
    items: List[AppResponse]
    total: int
    page: int
    page_size: int

@router.get("/apps", response_model=AppListResponse)
async def list_apps(page: int = 1, page_size: int = 20):
    items, total = await app_service.list_apps(page, page_size)
    return AppListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )
```

#### 4.1.2 错误响应

```python
from fastapi import HTTPException
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    code: int
    message: str
    error: ErrorDetail

# 使用示例
@router.get("/apps/{app_name}")
async def get_app(app_name: str):
    app = await app_service.get_app(app_name)
    if not app:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "APP_NOT_FOUND",
                "message": f"应用 {app_name} 不存在",
                "field": "app_name"
            }
        )
    return app
```

### 4.2 HTTP 状态码

| 状态码 | 含义 | 使用场景 | Websoft9 示例 |
|--------|------|----------|---------------|
| **200** | OK | 成功获取资源或执行操作 | 获取应用详情 |
| **201** | Created | 成功创建资源 | 创建新应用 |
| **204** | No Content | 成功删除资源或无返回数据 | 删除应用 |
| **400** | Bad Request | 请求参数错误 | 应用名称格式错误 |
| **401** | Unauthorized | 未认证或 Token 无效 | API Key 无效 |
| **403** | Forbidden | 已认证但无权限 | 无权限访问应用 |
| **404** | Not Found | 资源不存在 | 应用不存在 |
| **409** | Conflict | 资源冲突 | 应用名称已存在 |
| **422** | Unprocessable Entity | 请求格式正确但语义错误 | 端口号超出范围 |
| **429** | Too Many Requests | 请求频率限制 | API 调用超限 |
| **500** | Internal Server Error | 服务器内部错误 | Docker API 调用失败 |
| **503** | Service Unavailable | 服务暂时不可用 | Docker daemon 不可用 |

### 4.3 响应头

```python
from fastapi import Response

@router.post("/apps", status_code=201)
async def create_app(app: AppCreate, response: Response):
    result = await app_service.create_app(app)
    
    # 添加响应头
    response.headers["Location"] = f"/api/v1/apps/{result.app_name}"
    response.headers["X-Request-ID"] = "550e8400-e29b-41d4-a716-446655440000"
    
    return result
```

---

## 5. 错误处理

### 5.1 错误码设计

```python
# apphub/src/core/errors.py

class ErrorCode:
    """错误码定义"""
    
    # 认证错误 (AUTH_*)
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN_001"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED_002"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED_003"
    
    # 权限错误 (PERM_*)
    PERM_FORBIDDEN = "PERM_FORBIDDEN_001"
    PERM_INSUFFICIENT_ROLE = "PERM_INSUFFICIENT_ROLE_002"
    
    # 资源错误 (RES_*)
    RES_NOT_FOUND = "RES_NOT_FOUND_001"
    RES_ALREADY_EXISTS = "RES_ALREADY_EXISTS_002"
    RES_CONFLICT = "RES_CONFLICT_003"
    
    # 验证错误 (VAL_*)
    VAL_INVALID_PARAM = "VAL_INVALID_PARAM_001"
    VAL_MISSING_FIELD = "VAL_MISSING_FIELD_002"
    VAL_FORMAT_ERROR = "VAL_FORMAT_ERROR_003"
    
    # 业务错误 (BIZ_*)
    BIZ_QUOTA_EXCEEDED = "BIZ_QUOTA_EXCEEDED_001"
    BIZ_OPERATION_FAILED = "BIZ_OPERATION_FAILED_002"
    
    # Docker 错误 (DOCKER_*)
    DOCKER_CONTAINER_NOT_FOUND = "DOCKER_CONTAINER_NOT_FOUND_001"
    DOCKER_IMAGE_NOT_FOUND = "DOCKER_IMAGE_NOT_FOUND_002"
    DOCKER_NETWORK_ERROR = "DOCKER_NETWORK_ERROR_003"
    
    # 系统错误 (SYS_*)
    SYS_INTERNAL_ERROR = "SYS_INTERNAL_ERROR_001"
    SYS_SERVICE_UNAVAILABLE = "SYS_SERVICE_UNAVAILABLE_002"
    SYS_DATABASE_ERROR = "SYS_DATABASE_ERROR_003"
```

### 5.2 自定义异常

```python
# apphub/src/core/exceptions.py

from fastapi import HTTPException, status

class AppException(HTTPException):
    """应用异常基类"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "code": error_code,
                "message": message,
                "details": details or {}
            }
        )

class AppNotFoundException(AppException):
    """应用不存在异常"""
    
    def __init__(self, app_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.RES_NOT_FOUND,
            message=f"应用 {app_name} 不存在",
            details={"app_name": app_name}
        )

class AppAlreadyExistsException(AppException):
    """应用已存在异常"""
    
    def __init__(self, app_name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.RES_ALREADY_EXISTS,
            message=f"应用 {app_name} 已存在",
            details={"app_name": app_name}
        )

class DockerException(AppException):
    """Docker 异常"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.DOCKER_NETWORK_ERROR,
            message=message,
            details=details
        )
```

### 5.3 全局异常处理

```python
# apphub/src/main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理应用异常"""
    logger.warning(f"AppException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": exc.status_code,
            "message": exc.detail.get("message"),
            "error": exc.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理验证错误"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": 422,
            "message": "请求参数验证失败",
            "error": {
                "code": ErrorCode.VAL_INVALID_PARAM,
                "message": "请求参数验证失败",
                "details": exc.errors()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 500,
            "message": "服务器内部错误",
            "error": {
                "code": ErrorCode.SYS_INTERNAL_ERROR,
                "message": "服务器内部错误",
                "request_id": str(request.headers.get("X-Request-ID", ""))
            }
        }
    )
```

---

## 6. 认证与授权

### 6.1 API Key 认证

```python
# apphub/src/api/v1/deps.py

from fastapi import Header, HTTPException, status
from typing import Optional
import os

async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    验证 API Key
    
    Args:
        x_api_key: HTTP Header 中的 API Key
        
    Returns:
        验证通过的 API Key
        
    Raises:
        HTTPException: API Key 无效
    """
    stored_key = os.getenv("API_KEY")
    if not stored_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key not configured"
        )
    
    if x_api_key != stored_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.AUTH_INVALID_TOKEN,
                "message": "Invalid API key"
            }
        )
    
    return x_api_key

# 使用示例
@router.get("/apps")
async def list_apps(api_key: str = Depends(verify_api_key)):
    """需要 API Key 认证的接口"""
    pass
```

### 6.2 Bearer Token 认证 (未来扩展)

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    验证 JWT Token
    
    Args:
        credentials: Bearer Token
        
    Returns:
        Token payload
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
```

### 6.3 CORS 配置

```python
# apphub/src/main.py

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://websoft9.example.com",  # 生产域名
        "http://localhost:9000",         # Cockpit 开发环境
    ] if os.getenv("ENV") == "production" else ["*"],  # 开发环境允许所有
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)
```

### 6.4 Rate Limiting (推荐使用中间件)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.get("/apps")
@limiter.limit("100/minute")  # 每分钟最多 100 次请求
async def list_apps(request: Request):
    pass
```

---

## 7. 分页与过滤

### 7.1 分页实现

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.get("/apps", response_model=PaginatedResponse[AppResponse])
async def list_apps(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    分页查询应用列表
    
    Args:
        page: 页码,从 1 开始
        page_size: 每页大小,范围 1-100
        
    Returns:
        分页数据
    """
    offset = (page - 1) * page_size
    items, total = await app_service.list_apps(offset=offset, limit=page_size)
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )
```

### 7.2 过滤与搜索

```python
from enum import Enum

class AppStatus(str, Enum):
    """应用状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

@router.get("/apps")
async def list_apps(
    # 精确过滤
    status: Optional[AppStatus] = None,
    
    # 模糊搜索
    q: Optional[str] = Query(None, min_length=1, description="搜索关键词"),
    
    # 范围过滤
    created_after: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    created_before: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    
    # 排序
    sort: str = Query("created_at", regex="^(name|created_at|status)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
):
    """
    高级查询接口
    
    示例:
        GET /api/v1/apps?status=running&q=wordpress&sort=created_at&order=desc
    """
    filters = {
        "status": status,
        "q": q,
        "created_after": created_after,
        "created_before": created_before,
        "sort": sort,
        "order": order,
    }
    return await app_service.list_apps(**filters)
```

---

## 8. 异步操作

### 8.1 长时间任务

```python
from fastapi import BackgroundTasks
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int
    result: Optional[dict] = None
    error: Optional[str] = None

# 任务存储 (生产环境应使用 Redis)
tasks_db = {}

async def export_app_data(task_id: str, app_name: str):
    """后台导出应用数据"""
    tasks_db[task_id]["status"] = TaskStatus.RUNNING
    
    try:
        # 模拟耗时操作
        await app_service.export_data(app_name)
        
        tasks_db[task_id]["status"] = TaskStatus.COMPLETED
        tasks_db[task_id]["progress"] = 100
        tasks_db[task_id]["result"] = {
            "download_url": f"/api/v1/downloads/{task_id}.tar.gz"
        }
    except Exception as e:
        tasks_db[task_id]["status"] = TaskStatus.FAILED
        tasks_db[task_id]["error"] = str(e)

@router.post("/apps/{app_name}/export", status_code=202)
async def create_export_task(
    app_name: str,
    background_tasks: BackgroundTasks
) -> TaskResponse:
    """
    创建导出任务
    
    Args:
        app_name: 应用名称
        background_tasks: FastAPI 后台任务
        
    Returns:
        任务信息,状态码 202 Accepted
    """
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "progress": 0
    }
    
    background_tasks.add_task(export_app_data, task_id, app_name)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0
    )

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str) -> TaskResponse:
    """
    查询任务状态
    
    Args:
        task_id: 任务 ID
        
    Returns:
        任务当前状态
    """
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return TaskResponse(**tasks_db[task_id])
```

---

## 9. API 文档

### 9.1 FastAPI 自动文档

```python
from fastapi import FastAPI

app = FastAPI(
    title="Websoft9 AppHub API",
    description="容器化应用管理平台 API",
    version="2.0.0",
    docs_url="/api/docs",      # Swagger UI
    redoc_url="/api/redoc",    # ReDoc
    openapi_url="/api/openapi.json"
)

# 访问文档
# http://localhost:8080/api/docs
# http://localhost:8080/api/redoc
```

### 9.2 路由文档增强

```python
@router.get(
    "/apps/{app_name}",
    response_model=AppResponse,
    summary="获取应用详情",
    description="根据应用名称获取应用的详细配置和运行状态",
    response_description="应用详细信息",
    tags=["应用管理"],
    responses={
        200: {
            "description": "成功获取应用信息",
            "content": {
                "application/json": {
                    "example": {
                        "app_name": "wordpress",
                        "status": "running",
                        "image": "wordpress:latest",
                        "created_at": "2026-01-04T10:00:00Z"
                    }
                }
            }
        },
        404: {
            "description": "应用不存在",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "RES_NOT_FOUND_001",
                            "message": "应用 wordpress 不存在"
                        }
                    }
                }
            }
        }
    }
)
async def get_app(
    app_name: str = Path(..., description="应用名称,如 wordpress")
) -> AppResponse:
    pass
```

---

## 10. 最佳实践

### 10.1 依赖注入

```python
# 数据库连接
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

# Docker 客户端
async def get_docker_client():
    import docker
    client = docker.from_env()
    try:
        yield client
    finally:
        client.close()

# 使用依赖
@router.get("/apps")
async def list_apps(
    db: Session = Depends(get_db),
    docker: DockerClient = Depends(get_docker_client)
):
    pass
```

### 10.2 性能优化

```python
# 使用异步操作
import asyncio

@router.get("/dashboard")
async def get_dashboard():
    """并发获取多个数据"""
    apps, containers, images = await asyncio.gather(
        app_service.count_apps(),
        docker_service.count_containers(),
        docker_service.count_images()
    )
    
    return {
        "apps": apps,
        "containers": containers,
        "images": images
    }

# 使用缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def get_app_config(app_name: str):
    """缓存应用配置"""
    return load_config(app_name)
```

### 10.3 代码审查清单

API 设计审查清单:

- [ ] URL 使用复数名词
- [ ] HTTP 方法正确使用
- [ ] 所有路由函数都是 async
- [ ] 使用 Pydantic 模型验证请求
- [ ] 返回正确的 HTTP 状态码
- [ ] 完整的错误处理
- [ ] 添加日志记录
- [ ] API 文档完整 (docstring + response_model)
- [ ] 认证授权检查
- [ ] 幂等性保证 (PUT/DELETE)

---

## 附录

### A. Websoft9 API 路由列表

详见: [tech-architecture.md](../architecture/tech-architecture.md#41-路由规则)

### B. 工具推荐

- **API 测试**: Postman, Insomnia, httpie
- **文档查看**: FastAPI 自带 Swagger UI/ReDoc
- **性能测试**: k6, Locust
- **异步调试**: pytest-asyncio

---

**文档维护**: Winston (Architect Agent)  
**审核状态**: Active  
**下一步**: [coding-standards.md](./coding-standards.md) - 编码规范文档

**相关文档**: [Architecture](../architecture/tech-architecture.md) | [Coding Standards](./coding-standards.md) | [Testing Standards](./testing-standards.md)
