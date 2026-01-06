# Python Coding Standards

**Websoft9 Project - Python/FastAPI Best Practices**

**Created**: 2026-01-04  
**Maintainer**: Winston (Architect Agent)  
**Version**: 1.0  
**Status**: Active

---

## Table of Contents

1. [Naming Conventions](#1-naming-conventions)
2. [Project Structure](#2-project-structure)
3. [Code Style](#3-code-style)
4. [Error Handling](#4-error-handling)
5. [Async Programming](#5-async-programming)
6. [Comments & Documentation](#6-comments--documentation)
7. [Type Annotations](#7-type-annotations)
8. [Security Coding](#8-security-coding)
9. [Performance Optimization](#9-performance-optimization)
10. [Code Review Checklist](#10-code-review-checklist)

---

## 1. Naming Conventions

### 1.1 Basic Principles

Follow [PEP 8](https://peps.python.org/pep-0008/) standards:

```python
# ✅ Recommended

# Module/Package names: lowercase_with_underscores
# apphub/src/core/app_service.py
# apphub/src/api/v1/routers/app_management.py

# Class names: CapWords (PascalCase)
class AppService:
    pass

class DockerContainerManager:
    pass

# Function/Method names: lowercase_with_underscores
def create_application(app_name: str) -> dict:
    pass

async def get_container_status(container_id: str) -> str:
    pass

# Variable names: lowercase_with_underscores
app_name = "wordpress"
container_id = "abc123"
is_running = True

# Constants: UPPERCASE_WITH_UNDERSCORES
API_VERSION = "v1"
MAX_RETRY_COUNT = 3
DEFAULT_PORT = 8080

# Private attributes/methods: _leading_underscore
class MyClass:
    def __init__(self):
        self._private_var = None
    
    def _private_method(self):
        pass

# ❌ Avoid

# Don't use camelCase for variables/functions
appName = "wordpress"  # ❌
def createApplication():  # ❌
    pass

# Don't use single-character variable names (except loop counters)
a = get_app()  # ❌
result = get_app()  # ✅

# Don't use Python keywords
class = "MyClass"  # ❌ SyntaxError
type = "string"    # ❌ Shadows built-in function
```

### 1.2 Domain-Specific Naming

```python
# Docker-related
container_name = "websoft9-wordpress"
image_name = "wordpress:latest"
network_name = "websoft9_network"

# Application-related
app_name = "wordpress"  # Application identifier
app_id = "app_123"      # Database primary key
app_title = "WordPress" # Display name

# API-related
api_key = "sk_live_xxxxxxxxxxxx"
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
request_id = "550e8400-e29b-41d4-a716-446655440000"

# File paths
app_data_dir = "/websoft9/apphub/data"
config_file_path = "/etc/websoft9/config.json"
```

---

## 2. Project Structure

### 2.1 Websoft9 AppHub Structure

```
apphub/
├── src/
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── api/
│   │   └── v1/
│   │       ├── routers/           # API routes
│   │       │   ├── apps.py
│   │       │   ├── proxy.py
│   │       │   └── settings.py
│   │       └── deps.py            # Dependency injection
│   ├── core/                      # Core business logic
│   │   ├── app_service.py
│   │   ├── docker_service.py
│   │   └── config_service.py
│   ├── schemas/                   # Pydantic models
│   │   ├── app.py
│   │   ├── proxy.py
│   │   └── response.py
│   ├── models/                    # Database models
│   │   └── app.py
│   ├── db/                        # Database utilities
│   │   ├── base.py
│   │   └── session.py
│   ├── utils/                     # Utility functions
│   │   ├── logger.py
│   │   ├── docker_utils.py
│   │   └── file_utils.py
│   └── exceptions/                # Custom exceptions
│       └── app_exceptions.py
├── tests/                         # Test code
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### 2.2 Module Organization Principles

```python
# ✅ Recommended: Layer by functionality

# apphub/src/api/v1/routers/apps.py (API layer)
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


# apphub/src/core/app_service.py (Business logic layer)
from typing import List
from schemas.app import AppCreate, AppResponse
from db.session import get_db

class AppService:
    """Application management service"""
    
    async def create_app(self, app: AppCreate) -> AppResponse:
        """Create application"""
        # Business logic implementation
        pass


# apphub/src/schemas/app.py (Data model layer)
from pydantic import BaseModel
from typing import Optional

class AppCreate(BaseModel):
    """Create application request model"""
    app_name: str
    image: str
    domain: Optional[str] = None


# ❌ Avoid: All code in one file
# main.py (2000+ lines of code) ❌
```

---

## 3. Code Style

### 3.1 PEP 8 Core Rules

```python
# 1. Indentation: 4 spaces (no tabs)
def my_function():
    if condition:
        do_something()

# 2. Line length: Maximum 88 characters (Black default)
# ✅ Recommended
result = some_function_with_long_name(
    argument1,
    argument2,
    argument3
)

# 3. Blank lines
# - 2 blank lines before/after class definitions
# - 1 blank line between method definitions
class MyClass:
    
    def method1(self):
        pass
    
    def method2(self):
        pass


class AnotherClass:
    pass


# 4. Import order
# Standard library
import os
import sys
from typing import List, Optional

# Third-party libraries
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import docker

# Local modules
from core.app_service import AppService
from schemas.app import AppCreate
```

### 3.2 Using Black Formatter

```bash
# Install Black
pip install black

# Format single file
black apphub/src/main.py

# Format entire project
black apphub/src/

# Check format without modifying
black --check apphub/src/

# Configuration file: pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # Exclude directories
  \.git
  | \.venv
  | build
  | dist
)/
'''
```

### 3.3 String Formatting

```python
# ✅ Recommended: f-string (Python 3.6+)
app_name = "wordpress"
message = f"Application {app_name} created successfully"

# Multi-line f-string
query = (
    f"SELECT * FROM apps "
    f"WHERE name = '{app_name}' "
    f"AND status = 'running'"
)

# ❌ Avoid: % formatting (old-style)
message = "Application %s created successfully" % app_name

# ❌ Avoid: .format() (unless lazy formatting needed)
message = "Application {} created successfully".format(app_name)

# ⚠️ Use % formatting for logging (performance optimization)
import logging
logger = logging.getLogger(__name__)
logger.info("Application %s created successfully", app_name)  # Format only when needed
```

### 3.4 List/Dict Comprehensions

```python
# ✅ Recommended: Concise comprehensions
# List comprehension
running_apps = [app for app in apps if app.status == "running"]

# Dict comprehension
app_dict = {app.name: app.status for app in apps}

# Set comprehension
unique_images = {app.image for app in apps}

# ❌ Avoid: Complex comprehensions (use traditional loops for clarity)
# Too complex ❌
result = [
    process_data(item.value) 
    for item in data 
    if item.is_valid() and item.value > 0
    for subitem in item.children
    if subitem.active
]

# Use traditional loop instead ✅
result = []
for item in data:
    if item.is_valid() and item.value > 0:
        for subitem in item.children:
            if subitem.active:
                result.append(process_data(item.value))
```

---

## 4. Error Handling

### 4.1 Exception Handling Patterns

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ✅ Recommended: Specific exceptions first, log errors
async def get_application(app_name: str) -> Optional[dict]:
    """Get application information"""
    try:
        app = await app_repository.find_by_name(app_name)
        if not app:
            logger.warning(f"Application {app_name} not found")
            return None
        return app
        
    except ConnectionError as e:
        logger.error(f"Database connection failed: {e}")
        raise
        
    except ValueError as e:
        logger.warning(f"Invalid application name {app_name}: {e}")
        raise
        
    except Exception as e:
        logger.exception(f"Unknown error while getting application {app_name}: {e}")
        raise


# ❌ Avoid: Catch all exceptions and ignore
async def get_application(app_name: str):
    try:
        return await app_repository.find_by_name(app_name)
    except:  # ❌ Bare except
        pass  # ❌ Swallowing exception


# ❌ Avoid: Unnecessary try-except
def simple_calculation(a: int, b: int) -> int:
    try:  # ❌ Simple operation doesn't need it
        return a + b
    except:
        return 0
```

### 4.2 Custom Exceptions

```python
# apphub/src/exceptions/app_exceptions.py

class AppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AppNotFoundException(AppException):
    """Application not found exception"""
    def __init__(self, app_name: str):
        super().__init__(
            message=f"Application {app_name} not found",
            error_code="APP_NOT_FOUND"
        )
        self.app_name = app_name


class DockerAPIException(AppException):
    """Docker API call failed"""
    def __init__(self, message: str, container_id: str = None):
        super().__init__(
            message=message,
            error_code="DOCKER_API_ERROR"
        )
        self.container_id = container_id


# Usage example
from exceptions.app_exceptions import AppNotFoundException

async def delete_app(app_name: str):
    app = await get_app(app_name)
    if not app:
        raise AppNotFoundException(app_name)
    
    await docker_service.remove_container(app.container_id)
```

### 4.3 Context Managers

```python
from contextlib import asynccontextmanager

# ✅ Recommended: Use with to manage resources
import docker

def manage_containers():
    client = docker.from_env()
    try:
        containers = client.containers.list()
        return containers
    finally:
        client.close()  # Ensure cleanup


# Async context manager
@asynccontextmanager
async def get_database_session():
    """Database session management"""
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Usage
async def create_app(app_data: dict):
    async with get_database_session() as session:
        app = App(**app_data)
        session.add(app)
        # Auto commit/rollback
```

---

## 5. Async Programming

### 5.1 Async/Await Basics

```python
import asyncio
from typing import List

# ✅ Recommended: Use async for all I/O operations
async def fetch_app_data(app_name: str) -> dict:
    """Asynchronously fetch application data"""
    # Async database query
    app = await db.fetch_one("SELECT * FROM apps WHERE name = ?", app_name)
    
    # Async HTTP request
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://api/status/{app_name}")
    
    return {"app": app, "status": response.json()}


# ✅ Concurrent execution of multiple tasks
async def get_dashboard_data() -> dict:
    """Concurrently fetch dashboard data"""
    # Execute multiple async operations simultaneously
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


# ❌ Avoid: Using sync I/O in async functions
async def bad_example(app_name: str):
    # ❌ Blocks event loop
    import time
    time.sleep(5)  # Use await asyncio.sleep(5)
    
    # ❌ Sync HTTP request
    import requests
    response = requests.get(url)  # Use httpx.AsyncClient
    
    # ❌ Sync file operations
    with open("data.txt") as f:
        data = f.read()  # Use aiofiles
```

### 5.2 Async Iteration

```python
from typing import AsyncIterator

# Async generator
async def stream_logs(container_id: str) -> AsyncIterator[str]:
    """Stream container logs"""
    async for line in docker_client.logs(container_id, stream=True):
        yield line.decode('utf-8')


# Using async iteration
@router.get("/containers/{container_id}/logs")
async def get_container_logs(container_id: str):
    """Return logs as stream"""
    async def log_generator():
        async for log_line in stream_logs(container_id):
            yield f"data: {log_line}\n\n"
    
    return StreamingResponse(log_generator(), media_type="text/event-stream")
```

### 5.3 Async Locks

```python
import asyncio

class AppService:
    def __init__(self):
        self._locks = {}  # app_name -> Lock
    
    async def _get_lock(self, app_name: str) -> asyncio.Lock:
        """Get application-level lock"""
        if app_name not in self._locks:
            self._locks[app_name] = asyncio.Lock()
        return self._locks[app_name]
    
    async def update_app(self, app_name: str, updates: dict):
        """Concurrency-safe application update"""
        lock = await self._get_lock(app_name)
        
        async with lock:
            # Serialize update operations for the same app
            app = await self.get_app(app_name)
            app.update(updates)
            await self.save(app)
```

---

## 6. Comments & Documentation

### 6.1 Docstring Standards

Use Google-style docstrings:

```python
def create_application(
    app_name: str,
    image: str,
    ports: list[int] = None,
    env_vars: dict = None
) -> dict:
    """
    Create a new containerized application
    
    This function performs the following operations:
    1. Validate application name uniqueness
    2. Pull Docker image
    3. Create and start container
    4. Configure network and port mapping
    
    Args:
        app_name: Application name, must be unique, format: lowercase letters, numbers, hyphens
        image: Docker image name, format: repository:tag
        ports: Port mapping list, range 1024-65535, defaults to empty list
        env_vars: Environment variables dictionary, defaults to empty dict
    
    Returns:
        Dictionary containing the following fields:
        - app_id: Application unique identifier
        - container_id: Docker container ID
        - status: Application status (running, stopped, error)
        - created_at: Creation timestamp
    
    Raises:
        AppAlreadyExistsException: Application name already exists
        DockerImageNotFoundException: Docker image not found
        DockerAPIException: Docker API call failed
    
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
        - Application name cannot be modified after creation
        - Automatically assigns available port if port conflict occurs
        - Environment variables support template substitution ${VAR_NAME}
    
    See Also:
        - update_application(): Update application configuration
        - delete_application(): Delete application
    """
    pass
```

### 6.2 Comment Best Practices

```python
# ✅ Recommended: Explain WHY, not WHAT

# Good comment: Explains reason
# Use asyncio.gather instead of serial calls to reduce response time by 50%
apps, containers = await asyncio.gather(
    get_apps(),
    get_containers()
)

# Handle Docker API race condition: container may be deleted immediately after query
try:
    container = docker_client.containers.get(container_id)
except docker.errors.NotFound:
    logger.warning(f"Container {container_id} has been deleted")
    return None


# ❌ Avoid: Comments that repeat code

# Bad comment: Repeats code
# Create application
app = create_app()  # ❌ Redundant

# Get application name
name = app.name  # ❌ Redundant


# ✅ TODO/FIXME/NOTE comments

# TODO(winston): Implement automatic application backup feature (Issue #123)
# FIXME: Docker API may timeout under high concurrency, need to add retry logic
# NOTE: This method is only compatible with Docker Engine 20.10+
# HACK: Temporary workaround, waiting for Docker SDK to fix bug
# XXX: Dangerous operation, must backup data before modification
```

### 6.3 Type Annotations as Documentation

```python
from typing import Optional, List, Dict, Union, TypedDict

# ✅ Use TypedDict to define complex structures
class AppConfig(TypedDict):
    """Application configuration structure"""
    app_name: str
    image: str
    ports: List[int]
    env_vars: Dict[str, str]
    volumes: Optional[Dict[str, str]]


def configure_app(config: AppConfig) -> bool:
    """
    Configure application
    
    Args:
        config: Application configuration, must contain app_name and image
    
    Returns:
        Whether configuration was successful
    """
    pass


# IDE will provide complete field hints
configure_app({
    "app_name": "wordpress",
    "image": "wordpress:latest",
    "ports": [8080],
    "env_vars": {},
})
```

---

## 7. Type Annotations

### 7.1 Function Type Annotations

```python
from typing import List, Dict, Optional, Union, Any, Callable
from pydantic import BaseModel

# ✅ Recommended: Complete type annotations
async def list_applications(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> List[Dict[str, Any]]:
    """List applications"""
    pass


# Using Pydantic models
class AppResponse(BaseModel):
    app_name: str
    status: str
    image: str


async def get_application(app_name: str) -> Optional[AppResponse]:
    """Get application"""
    pass


# Callback function type
ProcessCallback = Callable[[str, int], bool]

def process_apps(
    apps: List[str],
    callback: ProcessCallback
) -> None:
    """Process application list"""
    for index, app in enumerate(apps):
        callback(app, index)
```

### 7.2 Using mypy for Type Checking

```bash
# Install mypy
pip install mypy

# Check types
mypy apphub/src/

# Configuration file: mypy.ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

# Ignore third-party libraries
[mypy-docker.*]
ignore_missing_imports = True

[mypy-pydantic.*]
ignore_missing_imports = True
```

---

## 8. Security Coding

### 8.1 Input Validation

```python
from pydantic import BaseModel, Field, validator
import re

class AppCreate(BaseModel):
    """Application creation request"""
    app_name: str = Field(..., min_length=3, max_length=50)
    image: str = Field(..., regex=r'^[a-z0-9._/-]+:[a-z0-9._-]+$')
    
    @validator('app_name')
    def validate_app_name(cls, v):
        """Validate application name security"""
        # Only allow lowercase letters, numbers, hyphens
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Application name can only contain lowercase letters, numbers and hyphens')
        
        # Cannot start/end with hyphen
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('Application name cannot start or end with hyphen')
        
        # Reserved names not allowed
        reserved_names = ['system', 'admin', 'root', 'test']
        if v in reserved_names:
            raise ValueError(f'Application name cannot use reserved names: {reserved_names}')
        
        return v
```

### 8.2 SQL Injection Protection

```python
# ✅ Recommended: Use parameterized queries
async def get_app_by_name(app_name: str):
    query = "SELECT * FROM apps WHERE name = ?"
    return await db.fetch_one(query, app_name)


# ❌ Dangerous: String concatenation
async def get_app_by_name_unsafe(app_name: str):
    query = f"SELECT * FROM apps WHERE name = '{app_name}'"  # ❌ SQL injection risk
    return await db.fetch_one(query)
```

### 8.3 Secret Management

```python
import os
from cryptography.fernet import Fernet

# ✅ Recommended: Use environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")

SECRET_KEY = os.getenv("SECRET_KEY")


# ❌ Dangerous: Hardcoded secrets
API_KEY = "sk_live_1234567890abcdef"  # ❌ Never do this


# Encrypt sensitive data
class SecretsManager:
    """Secrets manager"""
    
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt data"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt data"""
        return self.cipher.decrypt(ciphertext.encode()).decode()


# Usage
secrets = SecretsManager()
encrypted_password = secrets.encrypt("my_password")
# Store encrypted_password in database
```

### 8.4 Command Injection Protection

```python
import subprocess
import shlex

# ✅ Recommended: Use list arguments
def run_docker_command(container_id: str):
    """Safely execute Docker command"""
    # Argument list, won't be parsed by shell
    result = subprocess.run(
        ["docker", "inspect", container_id],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout


# ❌ Dangerous: Using shell=True
def run_docker_command_unsafe(container_id: str):
    command = f"docker inspect {container_id}"  # ❌ Command injection risk
    result = subprocess.run(
        command,
        shell=True,  # ❌ Dangerous
        capture_output=True
    )
    return result.stdout


# If shell is required, at least escape arguments
def run_with_shell(container_id: str):
    safe_id = shlex.quote(container_id)  # Escape special characters
    command = f"docker inspect {safe_id}"
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.stdout
```

---

## 9. Performance Optimization

### 9.1 Caching Strategy

```python
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional

# In-memory cache (simple scenarios)
@lru_cache(maxsize=128)
def get_docker_config(config_key: str) -> str:
    """Cache Docker configuration"""
    return load_config(config_key)


# Cache with TTL
class CacheWithTTL:
    """Cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[any]:
        """Get from cache"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any):
        """Set cache"""
        self._cache[key] = (value, datetime.now())


# Usage
app_cache = CacheWithTTL(ttl_seconds=300)  # 5 minutes expiration

async def get_app_status(app_name: str):
    """Get application status (with cache)"""
    cached = app_cache.get(app_name)
    if cached:
        return cached
    
    status = await docker_service.get_status(app_name)
    app_cache.set(app_name, status)
    return status
```

### 9.2 Batch Operations

```python
# ✅ Recommended: Batch queries
async def get_apps_status(app_names: List[str]) -> Dict[str, str]:
    """Batch get application status"""
    # Query all apps at once
    query = "SELECT name, status FROM apps WHERE name IN (?)"
    results = await db.fetch_all(query, app_names)
    return {row['name']: row['status'] for row in results}


# ❌ Avoid: N+1 queries
async def get_apps_status_slow(app_names: List[str]):
    """Slow way: Query one by one"""
    statuses = {}
    for name in app_names:  # ❌ N database queries
        status = await get_app_status(name)
        statuses[name] = status
    return statuses
```

### 9.3 Generator for Memory Optimization

```python
from typing import Iterator

# ✅ Recommended: Use generator for large datasets
def process_large_log_file(file_path: str) -> Iterator[str]:
    """Process log file line by line"""
    with open(file_path) as f:
        for line in f:  # Read line by line, doesn't consume much memory
            if "ERROR" in line:
                yield line.strip()


# ❌ Avoid: Load all data at once
def process_large_log_file_bad(file_path: str) -> list[str]:
    """Load all logs at once (high memory usage)"""
    with open(file_path) as f:
        all_lines = f.readlines()  # ❌ Memory explosion if file is large
    return [line for line in all_lines if "ERROR" in line]


# Async generator
async def stream_container_logs(container_id: str):
    """Stream container logs"""
    async for log in docker_client.logs(container_id, stream=True):
        yield log
```

---

## 10. Code Review Checklist

### 10.1 Pre-Commit Checks

```bash
# 1. Code formatting
black apphub/src/
flake8 apphub/src/

# 2. Type checking
mypy apphub/src/

# 3. Run tests
pytest tests/ --cov=apphub

# 4. Check security issues
bandit -r apphub/src/

# 5. Check dependency vulnerabilities
safety check
```

### 10.2 Code Review Checklist

**Naming & Structure**:
- [ ] Variable/function names follow PEP 8
- [ ] Class names use PascalCase, function names use snake_case
- [ ] Module organization is reasonable, single responsibility

**Code Quality**:
- [ ] All functions have type annotations
- [ ] Public functions have docstrings
- [ ] No `# type: ignore` to bypass type checking
- [ ] No hardcoded magic numbers/strings

**Async Programming**:
- [ ] I/O operations use async/await
- [ ] No sync blocking calls in async functions
- [ ] Proper use of asyncio.gather for concurrent execution

**Error Handling**:
- [ ] Catch specific exceptions, no bare `except`
- [ ] Exceptions properly logged
- [ ] Resources properly released (using with/finally)

**Security**:
- [ ] No hardcoded secrets/passwords
- [ ] Input validated
- [ ] SQL uses parameterized queries
- [ ] Command execution avoids shell injection

**Performance**:
- [ ] Avoid N+1 queries
- [ ] Proper use of caching
- [ ] Use generators for large datasets

**Testing**:
- [ ] New features have corresponding unit tests
- [ ] Test coverage ≥ 80%
- [ ] Critical logic has integration tests

---

## Appendix

### A. Tool Configuration

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

### B. Recommended Tools

- **Formatting**: Black, isort
- **Linting**: flake8, pylint
- **Type Checking**: mypy
- **Security Scanning**: bandit, safety
- **Testing**: pytest, pytest-asyncio, pytest-cov

---

**Document Maintainer**: Winston (Architect Agent)  
**Review Status**: Active  
**Next Steps**: [testing-standards.md](./testing-standards.md) - Testing Standards Documentation

**Related Documentation**: [API Design](./api-design.md) | [Testing Standards](./testing-standards.md) | [DevOps Process](./devops-process.md)
