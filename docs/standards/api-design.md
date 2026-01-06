# API Design Standards

**Websoft9 Project - FastAPI Best Practices**

**Created**: 2026-01-04  
**Maintainer**: Winston (Architect Agent)  
**Version**: 1.0  
**Status**: Active

---

## Table of Contents

1. [RESTful API Standards](#1-restful-api-standards)
2. [HTTP Methods](#2-http-methods)
3. [Request Standards](#3-request-standards)
4. [Response Standards](#4-response-standards)
5. [Error Handling](#5-error-handling)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [Pagination & Filtering](#7-pagination--filtering)
8. [Async Operations](#8-async-operations)
9. [API Documentation](#9-api-documentation)
10. [Best Practices](#10-best-practices)

---

## 1. RESTful API Standards

### 1.1 Basic Principles

- **Resource-Oriented**: URLs represent resources, HTTP methods represent operations
- **Stateless**: Each request contains complete authentication and context information
- **Uniform Interface**: Use standard HTTP methods and status codes
- **Async First**: All I/O operations use async/await

### 1.2 URL Design

#### 1.2.1 Naming Conventions

```python
# ✅ Recommended
GET  /api/v1/apps              # Use plural nouns for resources
GET  /api/v1/apps/myapp        # Use app_name to identify specific resource
POST /api/v1/apps              # Create resource
GET  /api/v1/apps/myapp/ports  # Nested resources

# ❌ Avoid
GET  /api/v1/getApps           # Don't include verbs in URL
GET  /api/v1/app               # Don't use singular form
GET  /api/v1/apps-list         # Don't use hyphens to indicate operations
```

#### 1.2.2 Versioning

```python
# URL path versioning (currently adopted)
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/apps")
async def list_apps():
    pass

# Future version upgrade
router_v2 = APIRouter(prefix="/api/v2")
```

#### 1.2.3 Resource Hierarchy

```python
# Shallow hierarchy (recommended)
GET /api/v1/apps/{app_name}/ports

# Deep hierarchy (avoid more than 3 levels)
# ❌ GET /api/v1/apps/{app_name}/containers/{container_id}/logs/files
# ✅ GET /api/v1/containers/{container_id}/logs
```

---

## 2. HTTP Methods

### 2.1 Standard Methods

| Method | Purpose | Idempotent | Safe | Websoft9 Example |
|--------|---------|------------|------|------------------|
| **GET** | Query resource | ✅ | ✅ | `GET /api/v1/apps/wordpress` |
| **POST** | Create resource | ❌ | ❌ | `POST /api/v1/apps` |
| **PUT** | Complete update | ✅ | ❌ | `PUT /api/v1/apps/wordpress` |
| **PATCH** | Partial update | ✅ | ❌ | `PATCH /api/v1/apps/wordpress` |
| **DELETE** | Delete resource | ✅ | ❌ | `DELETE /api/v1/apps/wordpress` |

### 2.2 FastAPI Implementation Example

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

# GET - List query
@router.get("/", response_model=List[AppResponse])
async def list_apps(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> List[AppResponse]:
    """
    Get application list
    
    Args:
        status: Filter by status (running, stopped, error)
        page: Page number
        page_size: Items per page
        
    Returns:
        List of applications
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

# GET - Detail query
@router.get("/{app_name}", response_model=AppResponse)
async def get_app(app_name: str) -> AppResponse:
    """
    Get application details
    
    Args:
        app_name: Application name
        
    Returns:
        Application detailed information
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

# POST - Create resource
@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_app(app: AppCreate) -> AppResponse:
    """
    Create new application
    
    Args:
        app: Application configuration
        
    Returns:
        Created application information
    """
    try:
        # Validate application name uniqueness
        existing = await app_service.get_app(app.app_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Application {app.app_name} already exists"
            )
        
        # Create application
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

# PATCH - Partial update
@router.patch("/{app_name}", response_model=AppResponse)
async def update_app(app_name: str, updates: dict) -> AppResponse:
    """
    Partially update application configuration
    
    Args:
        app_name: Application name
        updates: Fields to update
        
    Returns:
        Updated application information
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

# DELETE - Delete resource
@router.delete("/{app_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(app_name: str):
    """
    Delete application
    
    Args:
        app_name: Application name
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

## 3. Request Standards

### 3.1 Request Headers

```http
# Required headers
Content-Type: application/json
Accept: application/json
Authorization: Bearer <token>

# Optional headers
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000  # Request tracking ID
X-Client-Version: 2.0.0                             # Client version
Accept-Language: zh-CN,en                           # Language preference
```

### 3.2 Query Parameters

```python
from fastapi import Query
from typing import Optional

@router.get("/apps")
async def list_apps(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    
    # Filtering
    status: Optional[str] = Query(None, regex="^(running|stopped|error)$"),
    
    # Sorting
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    
    # Searching
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    
    # Field selection
    fields: Optional[str] = Query(None, description="Comma-separated field list")
):
    pass
```

### 3.3 Request Body Validation

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List

class AppCreate(BaseModel):
    app_name: str = Field(..., min_length=3, max_length=50, regex="^[a-z0-9-]+$")
    image: str = Field(..., description="Docker image name")
    domain: Optional[str] = Field(None, regex="^[a-z0-9.-]+$")
    ports: List[int] = Field(default_factory=list)
    env_vars: Optional[dict] = Field(default_factory=dict)
    
    @validator('app_name')
    def validate_app_name(cls, v):
        """Validate application name"""
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('Application name cannot start or end with hyphen')
        return v
    
    @validator('ports')
    def validate_ports(cls, v):
        """Validate port number range"""
        for port in v:
            if not (1024 <= port <= 65535):
                raise ValueError(f'Port number {port} out of range (1024-65535)')
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

## 4. Response Standards

### 4.1 Unified Response Format

#### 4.1.1 Success Response

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ResponseModel(BaseModel, Generic[T]):
    """Unified response model"""
    success: bool = True
    code: int = 200
    message: str = "Operation successful"
    data: Optional[T] = None

# Usage example
@router.get("/apps/{app_name}", response_model=ResponseModel[AppResponse])
async def get_app(app_name: str):
    app = await app_service.get_app(app_name)
    return ResponseModel(
        success=True,
        code=200,
        message="Retrieved successfully",
        data=app
    )
```

**Simplified version (recommended)**:

```python
# FastAPI automatically handles success responses, directly return data model
@router.get("/apps/{app_name}", response_model=AppResponse)
async def get_app(app_name: str) -> AppResponse:
    return await app_service.get_app(app_name)

# List response
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

#### 4.1.2 Error Response

```python
from fastapi import HTTPException
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    """Error detail"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    code: int
    message: str
    error: ErrorDetail

# Usage example
@router.get("/apps/{app_name}")
async def get_app(app_name: str):
    app = await app_service.get_app(app_name)
    if not app:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "APP_NOT_FOUND",
                "message": f"Application {app_name} not found",
                "field": "app_name"
            }
        )
    return app
```

### 4.2 HTTP Status Codes

| Status Code | Meaning | Use Case | Websoft9 Example |
|-------------|---------|----------|------------------|
| **200** | OK | Successfully retrieved resource or executed operation | Get app details |
| **201** | Created | Successfully created resource | Create new app |
| **204** | No Content | Successfully deleted resource or no return data | Delete app |
| **400** | Bad Request | Request parameter error | Invalid app name format |
| **401** | Unauthorized | Not authenticated or token invalid | Invalid API key |
| **403** | Forbidden | Authenticated but no permission | No permission to access app |
| **404** | Not Found | Resource does not exist | App not found |
| **409** | Conflict | Resource conflict | App name already exists |
| **422** | Unprocessable Entity | Request format correct but semantic error | Port number out of range |
| **429** | Too Many Requests | Request rate limit | API call limit exceeded |
| **500** | Internal Server Error | Internal server error | Docker API call failed |
| **503** | Service Unavailable | Service temporarily unavailable | Docker daemon unavailable |

### 4.3 Response Headers

```python
from fastapi import Response

@router.post("/apps", status_code=201)
async def create_app(app: AppCreate, response: Response):
    result = await app_service.create_app(app)
    
    # Add response headers
    response.headers["Location"] = f"/api/v1/apps/{result.app_name}"
    response.headers["X-Request-ID"] = "550e8400-e29b-41d4-a716-446655440000"
    
    return result
```

---

## 5. Error Handling

### 5.1 Error Code Design

```python
# apphub/src/core/errors.py

class ErrorCode:
    """Error code definitions"""
    
    # Authentication errors (AUTH_*)
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN_001"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED_002"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED_003"
    
    # Permission errors (PERM_*)
    PERM_FORBIDDEN = "PERM_FORBIDDEN_001"
    PERM_INSUFFICIENT_ROLE = "PERM_INSUFFICIENT_ROLE_002"
    
    # Resource errors (RES_*)
    RES_NOT_FOUND = "RES_NOT_FOUND_001"
    RES_ALREADY_EXISTS = "RES_ALREADY_EXISTS_002"
    RES_CONFLICT = "RES_CONFLICT_003"
    
    # Validation errors (VAL_*)
    VAL_INVALID_PARAM = "VAL_INVALID_PARAM_001"
    VAL_MISSING_FIELD = "VAL_MISSING_FIELD_002"
    VAL_FORMAT_ERROR = "VAL_FORMAT_ERROR_003"
    
    # Business errors (BIZ_*)
    BIZ_QUOTA_EXCEEDED = "BIZ_QUOTA_EXCEEDED_001"
    BIZ_OPERATION_FAILED = "BIZ_OPERATION_FAILED_002"
    
    # Docker errors (DOCKER_*)
    DOCKER_CONTAINER_NOT_FOUND = "DOCKER_CONTAINER_NOT_FOUND_001"
    DOCKER_IMAGE_NOT_FOUND = "DOCKER_IMAGE_NOT_FOUND_002"
    DOCKER_NETWORK_ERROR = "DOCKER_NETWORK_ERROR_003"
    
    # System errors (SYS_*)
    SYS_INTERNAL_ERROR = "SYS_INTERNAL_ERROR_001"
    SYS_SERVICE_UNAVAILABLE = "SYS_SERVICE_UNAVAILABLE_002"
    SYS_DATABASE_ERROR = "SYS_DATABASE_ERROR_003"
```

### 5.2 Custom Exceptions

```python
# apphub/src/core/exceptions.py

from fastapi import HTTPException, status

class AppException(HTTPException):
    """Base application exception"""
    
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
    """Application not found exception"""
    
    def __init__(self, app_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.RES_NOT_FOUND,
            message=f"Application {app_name} not found",
            details={"app_name": app_name}
        )

class AppAlreadyExistsException(AppException):
    """Application already exists exception"""
    
    def __init__(self, app_name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.RES_ALREADY_EXISTS,
            message=f"Application {app_name} already exists",
            details={"app_name": app_name}
        )

class DockerException(AppException):
    """Docker exception"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.DOCKER_NETWORK_ERROR,
            message=message,
            details=details
        )
```

### 5.3 Global Exception Handling

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
    """Handle application exceptions"""
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
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": 422,
            "message": "Request parameter validation failed",
            "error": {
                "code": ErrorCode.VAL_INVALID_PARAM,
                "message": "Request parameter validation failed",
                "details": exc.errors()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 500,
            "message": "Internal server error",
            "error": {
                "code": ErrorCode.SYS_INTERNAL_ERROR,
                "message": "Internal server error",
                "request_id": str(request.headers.get("X-Request-ID", ""))
            }
        }
    )
```

---

## 6. Authentication & Authorization

### 6.1 API Key Authentication

```python
# apphub/src/api/v1/deps.py

from fastapi import Header, HTTPException, status
from typing import Optional
import os

async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    Verify API Key
    
    Args:
        x_api_key: API Key from HTTP Header
        
    Returns:
        Verified API Key
        
    Raises:
        HTTPException: Invalid API Key
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

# Usage example
@router.get("/apps")
async def list_apps(api_key: str = Depends(verify_api_key)):
    """Endpoint requiring API Key authentication"""
    pass
```

### 6.2 Bearer Token Authentication (Future Extension)

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify JWT Token
    
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

### 6.3 CORS Configuration

```python
# apphub/src/main.py

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://websoft9.example.com",  # Production domain
        "http://localhost:9000",         # Cockpit development environment
    ] if os.getenv("ENV") == "production" else ["*"],  # Allow all in development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)
```

### 6.4 Rate Limiting (Recommended using middleware)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.get("/apps")
@limiter.limit("100/minute")  # Maximum 100 requests per minute
async def list_apps(request: Request):
    pass
```

---

## 7. Pagination & Filtering

### 7.1 Pagination Implementation

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model"""
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
    Query application list with pagination
    
    Args:
        page: Page number, starting from 1
        page_size: Items per page, range 1-100
        
    Returns:
        Paginated data
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

### 7.2 Filtering & Searching

```python
from enum import Enum

class AppStatus(str, Enum):
    """Application status enum"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

@router.get("/apps")
async def list_apps(
    # Exact filtering
    status: Optional[AppStatus] = None,
    
    # Fuzzy search
    q: Optional[str] = Query(None, min_length=1, description="Search keyword"),
    
    # Range filtering
    created_after: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    created_before: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$"),
    
    # Sorting
    sort: str = Query("created_at", regex="^(name|created_at|status)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
):
    """
    Advanced query interface
    
    Example:
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

## 8. Async Operations

### 8.1 Long-Running Tasks

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

# Task storage (production should use Redis)
tasks_db = {}

async def export_app_data(task_id: str, app_name: str):
    """Background export application data"""
    tasks_db[task_id]["status"] = TaskStatus.RUNNING
    
    try:
        # Simulate time-consuming operation
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
    Create export task
    
    Args:
        app_name: Application name
        background_tasks: FastAPI background tasks
        
    Returns:
        Task information, status code 202 Accepted
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
    Query task status
    
    Args:
        task_id: Task ID
        
    Returns:
        Current task status
    """
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return TaskResponse(**tasks_db[task_id])
```

---

## 9. API Documentation

### 9.1 FastAPI Auto Documentation

```python
from fastapi import FastAPI

app = FastAPI(
    title="Websoft9 AppHub API",
    description="Containerized Application Management Platform API",
    version="2.0.0",
    docs_url="/api/docs",      # Swagger UI
    redoc_url="/api/redoc",    # ReDoc
    openapi_url="/api/openapi.json"
)

# Access documentation
# http://localhost:8080/api/docs
# http://localhost:8080/api/redoc
```

### 9.2 Enhanced Route Documentation

```python
@router.get(
    "/apps/{app_name}",
    response_model=AppResponse,
    summary="Get application details",
    description="Get detailed configuration and running status of application by name",
    response_description="Application detailed information",
    tags=["Application Management"],
    responses={
        200: {
            "description": "Successfully retrieved application information",
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
            "description": "Application not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "RES_NOT_FOUND_001",
                            "message": "Application wordpress not found"
                        }
                    }
                }
            }
        }
    }
)
async def get_app(
    app_name: str = Path(..., description="Application name, e.g. wordpress")
) -> AppResponse:
    pass
```

---

## 10. Best Practices

### 10.1 Dependency Injection

```python
# Database connection
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

# Docker client
async def get_docker_client():
    import docker
    client = docker.from_env()
    try:
        yield client
    finally:
        client.close()

# Using dependencies
@router.get("/apps")
async def list_apps(
    db: Session = Depends(get_db),
    docker: DockerClient = Depends(get_docker_client)
):
    pass
```

### 10.2 Performance Optimization

```python
# Use async operations
import asyncio

@router.get("/dashboard")
async def get_dashboard():
    """Concurrently fetch multiple data"""
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

# Use caching
from functools import lru_cache

@lru_cache(maxsize=128)
def get_app_config(app_name: str):
    """Cache application configuration"""
    return load_config(app_name)
```

### 10.3 Code Review Checklist

API Design Review Checklist:

- [ ] URL uses plural nouns
- [ ] HTTP methods used correctly
- [ ] All route functions are async
- [ ] Use Pydantic models for request validation
- [ ] Return correct HTTP status codes
- [ ] Complete error handling
- [ ] Add logging
- [ ] Complete API documentation (docstring + response_model)
- [ ] Authentication/authorization checks
- [ ] Idempotency guarantee (PUT/DELETE)

---

## Appendix

### A. Websoft9 API Route List

See: [tech-architecture.md](../architecture/tech-architecture.md#41-routing-rules)

### B. Tool Recommendations

- **API Testing**: Postman, Insomnia, httpie
- **Documentation Viewing**: FastAPI built-in Swagger UI/ReDoc
- **Performance Testing**: k6, Locust
- **Async Debugging**: pytest-asyncio

---

**Document Maintainer**: Winston (Architect Agent)  
**Review Status**: Active  
**Next Steps**: [coding-standards.md](./coding-standards.md) - Coding Standards Documentation

**Related Documentation**: [Architecture](../architecture/tech-architecture.md) | [Coding Standards](./coding-standards.md) | [Testing Standards](./testing-standards.md)
