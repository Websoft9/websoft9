# Python 编码规范

**Websoft9 项目 - Python/FastAPI 最佳实践**

**创建日期**: 2026-01-04  
**维护者**: Winston (Architect Agent)  
**版本**: 1.0  
**状态**: Active

---

## 目录

1. [命名规范](#1-命名规范)
2. [项目结构](#2-项目结构)
3. [代码风格](#3-代码风格)
4. [错误处理](#4-错误处理)
5. [异步编程](#5-异步编程)
6. [注释与文档](#6-注释与文档)
7. [类型注解](#7-类型注解)
8. [安全编码](#8-安全编码)
9. [性能优化](#9-性能优化)
10. [代码审查清单](#10-代码审查清单)

---

## 1. 命名规范

### 1.1 基本原则

遵循 [PEP 8](https://peps.python.org/pep-0008/) 规范:

```python
# ✅ 推荐

# 模块/包名: lowercase_with_underscores
# apphub/src/core/app_service.py
# apphub/src/api/v1/routers/app_management.py

# 类名: CapWords (PascalCase)
class AppService:
    pass

class DockerContainerManager:
    pass

# 函数/方法名: lowercase_with_underscores
def create_application(app_name: str) -> dict:
    pass

async def get_container_status(container_id: str) -> str:
    pass

# 变量名: lowercase_with_underscores
app_name = "wordpress"
container_id = "abc123"
is_running = True

# 常量: UPPERCASE_WITH_UNDERSCORES
API_VERSION = "v1"
MAX_RETRY_COUNT = 3
DEFAULT_PORT = 8080

# 私有属性/方法: _leading_underscore
class MyClass:
    def __init__(self):
        self._private_var = None
    
    def _private_method(self):
        pass

# ❌ 避免

# 不要使用驼峰命名变量/函数
appName = "wordpress"  # ❌
def createApplication():  # ❌
    pass

# 不要使用单字符变量名 (除循环计数器外)
a = get_app()  # ❌
result = get_app()  # ✅

# 不要使用 Python 关键字
class = "MyClass"  # ❌ SyntaxError
type = "string"    # ❌ 覆盖内置函数
```

### 1.2 领域特定命名

```python
# Docker 相关
container_name = "websoft9-wordpress"
image_name = "wordpress:latest"
network_name = "websoft9_network"

# 应用相关
app_name = "wordpress"  # 应用标识
app_id = "app_123"      # 数据库主键
app_title = "WordPress" # 显示名称

# API 相关
api_key = "sk_live_xxxxxxxxxxxx"
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
request_id = "550e8400-e29b-41d4-a716-446655440000"

# 文件路径
app_data_dir = "/websoft9/apphub/data"
config_file_path = "/etc/websoft9/config.json"
```

---

## 2. 项目结构

### 2.1 Websoft9 AppHub 结构

```
apphub/
├── src/
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理
│   ├── api/
│   │   └── v1/
│   │       ├── routers/           # API 路由
│   │       │   ├── apps.py
│   │       │   ├── proxy.py
│   │       │   └── settings.py
│   │       └── deps.py            # 依赖注入
│   ├── core/                      # 核心业务逻辑
│   │   ├── app_service.py
│   │   ├── docker_service.py
│   │   └── config_service.py
│   ├── schemas/                   # Pydantic 模型
│   │   ├── app.py
│   │   ├── proxy.py
│   │   └── response.py
│   ├── models/                    # 数据库模型
│   │   └── app.py
│   ├── db/                        # 数据库工具
│   │   ├── base.py
│   │   └── session.py
│   ├── utils/                     # 工具函数
│   │   ├── logger.py
│   │   ├── docker_utils.py
│   │   └── file_utils.py
│   └── exceptions/                # 自定义异常
│       └── app_exceptions.py
├── tests/                         # 测试代码
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### 2.2 模块组织原则

```python
# ✅ 推荐: 按功能分层

# apphub/src/api/v1/routers/apps.py (API 层)
from fastapi import APIRouter, Depends
from core.app_service import AppService
from schemas.app import AppCreate, AppResponse

router = APIRouter(prefix="/api/v1/apps", tags=["applications"])

@router.post("/", response_model=AppResponse)
async def create_app(
    app: AppCreate,
    service: AppService = Depends()
):
    return await service.create_app(app)


# apphub/src/core/app_service.py (业务逻辑层)
from typing import List
from schemas.app import AppCreate, AppResponse
from db.session import get_db

class AppService:
    """应用管理服务"""
    
    async def create_app(self, app: AppCreate) -> AppResponse:
        """创建应用"""
        # 业务逻辑实现
        pass


# apphub/src/schemas/app.py (数据模型层)
from pydantic import BaseModel
from typing import Optional

class AppCreate(BaseModel):
    """创建应用请求模型"""
    app_name: str
    image: str
    domain: Optional[str] = None


# ❌ 避免: 所有代码放在一个文件
# main.py (2000+ 行代码) ❌
```

---

## 3. 代码风格

### 3.1 PEP 8 核心规则

```python
# 1. 缩进: 4 个空格 (不要使用 Tab)
def my_function():
    if condition:
        do_something()

# 2. 行长度: 最大 88 字符 (Black 默认)
# ✅ 推荐
result = some_function_with_long_name(
    argument1,
    argument2,
    argument3
)

# 3. 空行
# - 类定义前后 2 个空行
# - 方法定义之间 1 个空行
class MyClass:
    
    def method1(self):
        pass
    
    def method2(self):
        pass


class AnotherClass:
    pass


# 4. 导入顺序
# 标准库
import os
import sys
from typing import List, Optional

# 第三方库
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import docker

# 本地模块
from core.app_service import AppService
from schemas.app import AppCreate
```

### 3.2 使用 Black 格式化

```bash
# 安装 Black
pip install black

# 格式化单个文件
black apphub/src/main.py

# 格式化整个项目
black apphub/src/

# 检查格式但不修改
black --check apphub/src/

# 配置文件: pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # 排除目录
  \.git
  | \.venv
  | build
  | dist
)/
'''
```

### 3.3 字符串格式化

```python
# ✅ 推荐: f-string (Python 3.6+)
app_name = "wordpress"
message = f"应用 {app_name} 创建成功"

# 多行 f-string
query = (
    f"SELECT * FROM apps "
    f"WHERE name = '{app_name}' "
    f"AND status = 'running'"
)

# ❌ 避免: % 格式化 (旧式)
message = "应用 %s 创建成功" % app_name

# ❌ 避免: .format() (除非需要延迟格式化)
message = "应用 {} 创建成功".format(app_name)

# ⚠️ 日志使用 % 格式化 (性能优化)
import logging
logger = logging.getLogger(__name__)
logger.info("应用 %s 创建成功", app_name)  # 只在需要时格式化
```

### 3.4 列表/字典推导式

```python
# ✅ 推荐: 简洁的推导式
# 列表推导
running_apps = [app for app in apps if app.status == "running"]

# 字典推导
app_dict = {app.name: app.status for app in apps}

# 集合推导
unique_images = {app.image for app in apps}

# ❌ 避免: 复杂的推导式 (使用传统循环更清晰)
# 太复杂 ❌
result = [
    process_data(item.value) 
    for item in data 
    if item.is_valid() and item.value > 0
    for subitem in item.children
    if subitem.active
]

# 改用传统循环 ✅
result = []
for item in data:
    if item.is_valid() and item.value > 0:
        for subitem in item.children:
            if subitem.active:
                result.append(process_data(item.value))
```

---

## 4. 错误处理

### 4.1 异常处理模式

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ✅ 推荐: 具体异常优先,记录日志
async def get_application(app_name: str) -> Optional[dict]:
    """获取应用信息"""
    try:
        app = await app_repository.find_by_name(app_name)
        if not app:
            logger.warning(f"应用 {app_name} 不存在")
            return None
        return app
        
    except ConnectionError as e:
        logger.error(f"数据库连接失败: {e}")
        raise
        
    except ValueError as e:
        logger.warning(f"无效的应用名称 {app_name}: {e}")
        raise
        
    except Exception as e:
        logger.exception(f"获取应用 {app_name} 时发生未知错误: {e}")
        raise


# ❌ 避免: 捕获所有异常并忽略
async def get_application(app_name: str):
    try:
        return await app_repository.find_by_name(app_name)
    except:  # ❌ 裸 except
        pass  # ❌ 吞掉异常


# ❌ 避免: 不必要的 try-except
def simple_calculation(a: int, b: int) -> int:
    try:  # ❌ 简单运算不需要
        return a + b
    except:
        return 0
```

### 4.2 自定义异常

```python
# apphub/src/exceptions/app_exceptions.py

class AppException(Exception):
    """应用异常基类"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AppNotFoundException(AppException):
    """应用不存在异常"""
    def __init__(self, app_name: str):
        super().__init__(
            message=f"应用 {app_name} 不存在",
            error_code="APP_NOT_FOUND"
        )
        self.app_name = app_name


class DockerAPIException(AppException):
    """Docker API 调用失败"""
    def __init__(self, message: str, container_id: str = None):
        super().__init__(
            message=message,
            error_code="DOCKER_API_ERROR"
        )
        self.container_id = container_id


# 使用示例
from exceptions.app_exceptions import AppNotFoundException

async def delete_app(app_name: str):
    app = await get_app(app_name)
    if not app:
        raise AppNotFoundException(app_name)
    
    await docker_service.remove_container(app.container_id)
```

### 4.3 上下文管理器

```python
from contextlib import asynccontextmanager

# ✅ 推荐: 使用 with 管理资源
import docker

def manage_containers():
    client = docker.from_env()
    try:
        containers = client.containers.list()
        return containers
    finally:
        client.close()  # 确保清理


# 异步上下文管理器
@asynccontextmanager
async def get_database_session():
    """数据库会话管理"""
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# 使用
async def create_app(app_data: dict):
    async with get_database_session() as session:
        app = App(**app_data)
        session.add(app)
        # 自动 commit/rollback
```

---

## 5. 异步编程

### 5.1 Async/Await 基础

```python
import asyncio
from typing import List

# ✅ 推荐: 所有 I/O 操作使用 async
async def fetch_app_data(app_name: str) -> dict:
    """异步获取应用数据"""
    # 异步数据库查询
    app = await db.fetch_one("SELECT * FROM apps WHERE name = ?", app_name)
    
    # 异步 HTTP 请求
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://api/status/{app_name}")
    
    return {"app": app, "status": response.json()}


# ✅ 并发执行多个任务
async def get_dashboard_data() -> dict:
    """并发获取仪表盘数据"""
    # 同时执行多个异步操作
    apps, containers, images = await asyncio.gather(
        count_apps(),
        count_containers(),
        count_images()
    )
    
    return {
        "apps": apps,
        "containers": containers,
        "images": images
    }


# ❌ 避免: 在异步函数中使用同步 I/O
async def bad_example(app_name: str):
    # ❌ 阻塞事件循环
    import time
    time.sleep(5)  # 使用 await asyncio.sleep(5)
    
    # ❌ 同步 HTTP 请求
    import requests
    response = requests.get(url)  # 使用 httpx.AsyncClient
    
    # ❌ 同步文件操作
    with open("data.txt") as f:
        data = f.read()  # 使用 aiofiles
```

### 5.2 异步迭代

```python
from typing import AsyncIterator

# 异步生成器
async def stream_logs(container_id: str) -> AsyncIterator[str]:
    """流式读取容器日志"""
    async for line in docker_client.logs(container_id, stream=True):
        yield line.decode('utf-8')


# 使用异步迭代
@router.get("/containers/{container_id}/logs")
async def get_container_logs(container_id: str):
    """流式返回日志"""
    async def log_generator():
        async for log_line in stream_logs(container_id):
            yield f"data: {log_line}\n\n"
    
    return StreamingResponse(log_generator(), media_type="text/event-stream")
```

### 5.3 异步锁

```python
import asyncio

class AppService:
    def __init__(self):
        self._locks = {}  # app_name -> Lock
    
    async def _get_lock(self, app_name: str) -> asyncio.Lock:
        """获取应用级别的锁"""
        if app_name not in self._locks:
            self._locks[app_name] = asyncio.Lock()
        return self._locks[app_name]
    
    async def update_app(self, app_name: str, updates: dict):
        """并发安全的应用更新"""
        lock = await self._get_lock(app_name)
        
        async with lock:
            # 同一应用的更新操作串行化
            app = await self.get_app(app_name)
            app.update(updates)
            await self.save(app)
```

---

## 6. 注释与文档

### 6.1 Docstring 规范

使用 Google 风格 Docstring:

```python
def create_application(
    app_name: str,
    image: str,
    ports: list[int] = None,
    env_vars: dict = None
) -> dict:
    """
    创建新的容器化应用
    
    该函数会执行以下操作:
    1. 验证应用名称唯一性
    2. 拉取 Docker 镜像
    3. 创建并启动容器
    4. 配置网络和端口映射
    
    Args:
        app_name: 应用名称,必须唯一,格式: 小写字母、数字、连字符
        image: Docker 镜像名称,格式: repository:tag
        ports: 端口映射列表,范围 1024-65535,默认为空列表
        env_vars: 环境变量字典,默认为空字典
    
    Returns:
        包含以下字段的字典:
        - app_id: 应用唯一标识符
        - container_id: Docker 容器 ID
        - status: 应用状态 (running, stopped, error)
        - created_at: 创建时间戳
    
    Raises:
        AppAlreadyExistsException: 应用名称已存在
        DockerImageNotFoundException: Docker 镜像不存在
        DockerAPIException: Docker API 调用失败
    
    Examples:
        >>> create_application(
        ...     app_name="wordpress",
        ...     image="wordpress:latest",
        ...     ports=[8080],
        ...     env_vars={"WORDPRESS_DB_HOST": "mysql"}
        ... )
        {
            'app_id': 'app_123',
            'container_id': 'abc123def456',
            'status': 'running',
            'created_at': '2026-01-04T10:00:00Z'
        }
    
    Note:
        - 应用名称创建后不可修改
        - 端口冲突时自动分配可用端口
        - 环境变量支持模板替换 ${VAR_NAME}
    
    See Also:
        - update_application(): 更新应用配置
        - delete_application(): 删除应用
    """
    pass
```

### 6.2 注释最佳实践

```python
# ✅ 推荐: 解释 WHY,而不是 WHAT

# 好注释: 解释原因
# 使用 asyncio.gather 而不是串行调用,减少 50% 的响应时间
apps, containers = await asyncio.gather(
    get_apps(),
    get_containers()
)

# 处理 Docker API 的竞态条件:容器可能在查询后立即被删除
try:
    container = docker_client.containers.get(container_id)
except docker.errors.NotFound:
    logger.warning(f"容器 {container_id} 已被删除")
    return None


# ❌ 避免: 重复代码的注释

# 坏注释: 重复代码
# 创建应用
app = create_app()  # ❌ 多余

# 获取应用名称
name = app.name  # ❌ 多余


# ✅ TODO/FIXME/NOTE 注释

# TODO(winston): 实现应用自动备份功能 (Issue #123)
# FIXME: Docker API 在高并发下可能超时,需要添加重试逻辑
# NOTE: 该方法仅兼容 Docker Engine 20.10+
# HACK: 临时解决方案,等待 Docker SDK 修复 Bug
# XXX: 危险操作,修改前务必备份数据
```

### 6.3 类型注解作为文档

```python
from typing import Optional, List, Dict, Union, TypedDict

# ✅ 使用 TypedDict 定义复杂结构
class AppConfig(TypedDict):
    """应用配置结构"""
    app_name: str
    image: str
    ports: List[int]
    env_vars: Dict[str, str]
    volumes: Optional[Dict[str, str]]


def configure_app(config: AppConfig) -> bool:
    """
    配置应用
    
    Args:
        config: 应用配置,必须包含 app_name 和 image
    
    Returns:
        配置是否成功
    """
    pass


# IDE 会提供完整的字段提示
configure_app({
    "app_name": "wordpress",
    "image": "wordpress:latest",
    "ports": [8080],
    "env_vars": {},
})
```

---

## 7. 类型注解

### 7.1 函数类型注解

```python
from typing import List, Dict, Optional, Union, Any, Callable
from pydantic import BaseModel

# ✅ 推荐: 完整的类型注解
async def list_applications(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> List[Dict[str, Any]]:
    """列出应用"""
    pass


# 使用 Pydantic 模型
class AppResponse(BaseModel):
    app_name: str
    status: str
    image: str


async def get_application(app_name: str) -> Optional[AppResponse]:
    """获取应用"""
    pass


# 回调函数类型
ProcessCallback = Callable[[str, int], bool]

def process_apps(
    apps: List[str],
    callback: ProcessCallback
) -> None:
    """处理应用列表"""
    for index, app in enumerate(apps):
        callback(app, index)
```

### 7.2 使用 mypy 检查

```bash
# 安装 mypy
pip install mypy

# 检查类型
mypy apphub/src/

# 配置文件: mypy.ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

# 忽略第三方库
[mypy-docker.*]
ignore_missing_imports = True

[mypy-pydantic.*]
ignore_missing_imports = True
```

---

## 8. 安全编码

### 8.1 输入验证

```python
from pydantic import BaseModel, Field, validator
import re

class AppCreate(BaseModel):
    """应用创建请求"""
    app_name: str = Field(..., min_length=3, max_length=50)
    image: str = Field(..., regex=r'^[a-z0-9._/-]+:[a-z0-9._-]+$')
    
    @validator('app_name')
    def validate_app_name(cls, v):
        """验证应用名称安全性"""
        # 仅允许小写字母、数字、连字符
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('应用名称只能包含小写字母、数字和连字符')
        
        # 不允许以连字符开头/结尾
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('应用名称不能以连字符开头或结尾')
        
        # 不允许保留名称
        reserved_names = ['system', 'admin', 'root', 'test']
        if v in reserved_names:
            raise ValueError(f'应用名称不能使用保留名称: {reserved_names}')
        
        return v
```

### 8.2 SQL 注入防护

```python
# ✅ 推荐: 使用参数化查询
async def get_app_by_name(app_name: str):
    query = "SELECT * FROM apps WHERE name = ?"
    return await db.fetch_one(query, app_name)


# ❌ 危险: 字符串拼接
async def get_app_by_name_unsafe(app_name: str):
    query = f"SELECT * FROM apps WHERE name = '{app_name}'"  # ❌ SQL 注入风险
    return await db.fetch_one(query)
```

### 8.3 密钥管理

```python
import os
from cryptography.fernet import Fernet

# ✅ 推荐: 使用环境变量
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")

SECRET_KEY = os.getenv("SECRET_KEY")


# ❌ 危险: 硬编码密钥
API_KEY = "sk_live_1234567890abcdef"  # ❌ 永远不要这样做


# 加密敏感数据
class SecretsManager:
    """密钥管理器"""
    
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """加密数据"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密数据"""
        return self.cipher.decrypt(ciphertext.encode()).decode()


# 使用
secrets = SecretsManager()
encrypted_password = secrets.encrypt("my_password")
# 存储 encrypted_password 到数据库
```

### 8.4 命令注入防护

```python
import subprocess
import shlex

# ✅ 推荐: 使用列表参数
def run_docker_command(container_id: str):
    """安全执行 Docker 命令"""
    # 参数列表,不会被 shell 解析
    result = subprocess.run(
        ["docker", "inspect", container_id],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout


# ❌ 危险: 使用 shell=True
def run_docker_command_unsafe(container_id: str):
    command = f"docker inspect {container_id}"  # ❌ 命令注入风险
    result = subprocess.run(
        command,
        shell=True,  # ❌ 危险
        capture_output=True
    )
    return result.stdout


# 如果必须使用 shell,至少转义参数
def run_with_shell(container_id: str):
    safe_id = shlex.quote(container_id)  # 转义特殊字符
    command = f"docker inspect {safe_id}"
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.stdout
```

---

## 9. 性能优化

### 9.1 缓存策略

```python
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional

# 内存缓存 (简单场景)
@lru_cache(maxsize=128)
def get_docker_config(config_key: str) -> str:
    """缓存 Docker 配置"""
    return load_config(config_key)


# 带过期时间的缓存
class CacheWithTTL:
    """带 TTL 的缓存"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[any]:
        """获取缓存"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any):
        """设置缓存"""
        self._cache[key] = (value, datetime.now())


# 使用
app_cache = CacheWithTTL(ttl_seconds=300)  # 5 分钟过期

async def get_app_status(app_name: str):
    """获取应用状态 (带缓存)"""
    cached = app_cache.get(app_name)
    if cached:
        return cached
    
    status = await docker_service.get_status(app_name)
    app_cache.set(app_name, status)
    return status
```

### 9.2 批量操作

```python
# ✅ 推荐: 批量查询
async def get_apps_status(app_names: List[str]) -> Dict[str, str]:
    """批量获取应用状态"""
    # 一次查询所有应用
    query = "SELECT name, status FROM apps WHERE name IN (?)"
    results = await db.fetch_all(query, app_names)
    return {row['name']: row['status'] for row in results}


# ❌ 避免: N+1 查询
async def get_apps_status_slow(app_names: List[str]):
    """慢速方式: 逐个查询"""
    statuses = {}
    for name in app_names:  # ❌ N 次数据库查询
        status = await get_app_status(name)
        statuses[name] = status
    return statuses
```

### 9.3 生成器优化内存

```python
from typing import Iterator

# ✅ 推荐: 使用生成器处理大数据集
def process_large_log_file(file_path: str) -> Iterator[str]:
    """逐行处理日志文件"""
    with open(file_path) as f:
        for line in f:  # 逐行读取,不占用大量内存
            if "ERROR" in line:
                yield line.strip()


# ❌ 避免: 一次性加载所有数据
def process_large_log_file_bad(file_path: str) -> list[str]:
    """一次性加载所有日志 (内存占用大)"""
    with open(file_path) as f:
        all_lines = f.readlines()  # ❌ 如果文件很大,内存爆炸
    return [line for line in all_lines if "ERROR" in line]


# 异步生成器
async def stream_container_logs(container_id: str):
    """流式读取容器日志"""
    async for log in docker_client.logs(container_id, stream=True):
        yield log
```

---

## 10. 代码审查清单

### 10.1 提交前检查

```bash
# 1. 代码格式化
black apphub/src/
flake8 apphub/src/

# 2. 类型检查
mypy apphub/src/

# 3. 运行测试
pytest tests/ --cov=apphub

# 4. 检查安全问题
bandit -r apphub/src/

# 5. 检查依赖漏洞
safety check
```

### 10.2 Code Review 检查清单

**命名与结构**:
- [ ] 变量/函数名符合 PEP 8 规范
- [ ] 类名使用 PascalCase,函数名使用 snake_case
- [ ] 模块组织合理,职责单一

**代码质量**:
- [ ] 所有函数都有类型注解
- [ ] 公共函数都有 Docstring
- [ ] 没有使用 `# type: ignore` 绕过类型检查
- [ ] 没有硬编码魔法数字/字符串

**异步编程**:
- [ ] I/O 操作使用 async/await
- [ ] 没有在异步函数中使用同步阻塞调用
- [ ] 正确使用 asyncio.gather 并发执行

**错误处理**:
- [ ] 捕获具体异常,不使用裸 `except`
- [ ] 异常被正确记录日志
- [ ] 资源正确释放 (使用 with/finally)

**安全**:
- [ ] 没有硬编码密钥/密码
- [ ] 输入经过验证
- [ ] SQL 使用参数化查询
- [ ] 命令执行避免 shell 注入

**性能**:
- [ ] 避免 N+1 查询
- [ ] 合理使用缓存
- [ ] 大数据集使用生成器

**测试**:
- [ ] 新功能有对应的单元测试
- [ ] 测试覆盖率 ≥ 80%
- [ ] 关键逻辑有集成测试

---

## 附录

### A. 工具配置

**pyproject.toml**:
```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "--cov=apphub --cov-report=html"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### B. 推荐工具

- **格式化**: Black, isort
- **Lint**: flake8, pylint
- **类型检查**: mypy
- **安全扫描**: bandit, safety
- **测试**: pytest, pytest-asyncio, pytest-cov

---

**文档维护**: Winston (Architect Agent)  
**审核状态**: Active  
**下一步**: [testing-standards.md](./testing-standards.md) - 测试规范文档

**相关文档**: [API Design](./api-design.md) | [Testing Standards](./testing-standards.md) | [DevOps Process](./devops-process.md)
