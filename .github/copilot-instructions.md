# GitHub Copilot Instructions for Websoft9

## Project Overview

Websoft9 is a containerized application management platform consisting of:
- **Cockpit**: Web-based system management interface
- **Four Core Containers**:
  - **AppHub**: Custom-built application hub (Python + FastAPI) - our main service
  - **Gitea**: Git repository service
  - **Portainer**: Docker container management UI
  - **Nginx Proxy Manager**: Reverse proxy and SSL management

## Tech Stack

### AppHub Service (Primary Development Focus)
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Async**: asyncio-based for non-blocking operations
- **Validation**: Pydantic models
- **Database**: SQLite (with option for PostgreSQL)
- **Docker**: Containerized deployment

### Infrastructure
- **Orchestration**: Docker Compose
- **Proxy**: Nginx-based reverse proxy
- **System Management**: Cockpit
- **Version Control**: Gitea (self-hosted)
- **Container Management**: Portainer

## Code Standards

### Python/FastAPI Best Practices

1. **Follow PEP 8** - Use consistent Python style
2. **Type Hints**: Always use type annotations
3. **Async First**: Prefer `async/await` for I/O operations
4. **Pydantic Models**: Use for request/response validation
5. **Dependency Injection**: Leverage FastAPI's `Depends()`

### Example Code Pattern

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Pydantic Schema
class AppCreate(BaseModel):
    name: str
    description: Optional[str] = None
    image: str

class AppResponse(BaseModel):
    id: str
    name: str
    status: str

# Router
router = APIRouter(prefix="/api/v1/apps", tags=["applications"])

@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    app: AppCreate,
    current_user: dict = Depends(get_current_user)
) -> AppResponse:
    """
    Create a new application instance
    
    Args:
        app: Application configuration
        current_user: Authenticated user from dependency
        
    Returns:
        AppResponse with created application details
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        result = await app_service.create(app, current_user)
        logger.info(f"Application created: {result.id}")
        return result
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
```

## Project Structure

```
websoft9/
├── apphub/                      # Main FastAPI application
│   ├── src/
│   │   ├── api/
│   │   │   └── v1/             # API version 1 routes
│   │   │       ├── routers/    # Endpoint definitions
│   │   │       └── deps.py     # Dependencies (auth, db, etc.)
│   │   ├── core/               # Business logic & services
│   │   ├── schemas/            # Pydantic models
│   │   ├── models/             # Database models
│   │   ├── db/                 # Database utilities
│   │   └── main.py             # FastAPI app entry point
│   ├── tests/                  # pytest test suite
│   ├── requirements.txt
│   └── Dockerfile
├── docker/
│   ├── docker-compose.yml      # Service orchestration
│   ├── .env                    # Environment variables
│   └── proxy/
│       └── config/             # Nginx configurations
├── cockpit/                    # Cockpit configurations
├── scripts/                    # Automation scripts
└── docs/                       # Documentation
```

## Development Guidelines

### Adding New API Endpoints

1. **Define Schema** in `apphub/src/schemas/`
   ```python
   # apphub/src/schemas/deployment.py
   from pydantic import BaseModel, Field
   
   class DeploymentCreate(BaseModel):
       app_id: str = Field(..., description="Application ID")
       config: dict = Field(default_factory=dict)
   ```

2. **Implement Service Logic** in `apphub/src/core/`
   ```python
   # apphub/src/core/deployment_service.py
   async def deploy_application(app_id: str, config: dict) -> dict:
       # Business logic here
       pass
   ```

3. **Create Router** in `apphub/src/api/v1/routers/`
   ```python
   # apphub/src/api/v1/routers/deployments.py
   from fastapi import APIRouter
   
   router = APIRouter(prefix="/deployments", tags=["deployments"])
   
   @router.post("/")
   async def create_deployment(...):
       pass
   ```

4. **Add Tests** in `tests/`
   ```python
   # tests/test_deployments.py
   import pytest
   from httpx import AsyncClient
   
   @pytest.mark.asyncio
   async def test_create_deployment(client: AsyncClient):
       response = await client.post("/api/v1/deployments", json={...})
       assert response.status_code == 201
   ```

### Docker Container Management

When working with Docker operations in AppHub:

```python
import docker
from docker.errors import NotFound, APIError

async def restart_container(container_name: str) -> dict:
    """Restart a Docker container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        container.restart()
        return {"status": "success", "container": container_name}
    except NotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Container {container_name} not found"
        )
    except APIError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Docker API error: {str(e)}"
        )
```

### Error Handling Pattern

Always use structured error handling:

```python
try:
    result = await service.perform_operation()
    return result
except ValueError as e:
    # Client error - bad input
    logger.warning(f"Invalid input: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except PermissionError as e:
    # Authorization error
    logger.warning(f"Permission denied: {e}")
    raise HTTPException(status_code=403, detail="Permission denied")
except NotFoundError as e:
    # Resource not found
    raise HTTPException(status_code=404, detail=str(e))
except Exception as e:
    # Unexpected server error
    logger.exception(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

# Info: normal operations
logger.info(f"Application {app_id} started successfully")

# Warning: recoverable issues
logger.warning(f"Deprecated API endpoint called: {endpoint}")

# Error: operation failures
logger.error(f"Failed to connect to database: {error}")

# Exception: with full stack trace
logger.exception(f"Unexpected error in {function_name}")
```

## Testing Guidelines

### Test Structure

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

@pytest.fixture
async def client():
    """Async HTTP client fixture"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_application(client: AsyncClient):
    """Test retrieving an application"""
    response = await client.get("/api/v1/apps/test-app")
    assert response.status_code == 200
    assert response.json()["name"] == "test-app"

@pytest.mark.asyncio
async def test_create_application_invalid(client: AsyncClient):
    """Test creating application with invalid data"""
    response = await client.post("/api/v1/apps", json={"invalid": "data"})
    assert response.status_code == 422
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apphub --cov-report=html

# Run specific test file
pytest tests/test_apps.py

# Run with verbose output
pytest -v
```

## Docker & Container Guidelines

### Dockerfile Best Practices

```dockerfile
# Use specific Python version
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies separately for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Use non-root user
RUN useradd -m appuser
USER appuser

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Service Definition

```yaml
services:
  apphub:
    build: ./apphub
    container_name: websoft9-apphub
    restart: unless-stopped
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - API_KEY=${API_KEY}
    volumes:
      - apphub-data:/app/data
    networks:
      - websoft9
    depends_on:
      - proxy
```

### Container Communication

All Websoft9 services communicate via the `websoft9` Docker network:

```python
# Accessing other services from AppHub
GITEA_URL = "http://websoft9-gitea:3000"
PORTAINER_URL = "http://websoft9-portainer:9000"
PROXY_URL = "http://websoft9-proxy:80"
```

## Security Best Practices

### 1. Never Hardcode Secrets

```python
# ❌ BAD
API_KEY = "hardcoded-secret-key"

# ✅ GOOD
import os
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
```

### 2. Input Validation

```python
from pydantic import BaseModel, validator, Field

class AppConfig(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    port: int = Field(..., ge=1024, le=65535)
    
    @validator('name')
    def validate_name(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Name must be alphanumeric')
        return v
```

### 3. Authentication & Authorization

```python
from fastapi import Depends, Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Verify API key from request header"""
    stored_key = os.getenv("API_KEY")
    if x_api_key != stored_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return x_api_key

@router.get("/protected")
async def protected_route(api_key: str = Depends(verify_api_key)):
    return {"message": "Access granted"}
```

### 4. CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

## Working with External Services

### Gitea Integration

```python
import httpx

class GiteaClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"token {token}"}
    
    async def create_repository(self, name: str, private: bool = False):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/user/repos",
                headers=self.headers,
                json={"name": name, "private": private}
            )
            response.raise_for_status()
            return response.json()
```

### Portainer Integration

```python
class PortainerClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    async def list_containers(self, endpoint_id: int = 1):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json",
                headers=self.headers
            )
            return response.json()
```

## Common Development Tasks

### Starting Development Environment

```bash
# Clone repository
git clone https://github.com/websoft9/websoft9.git
cd websoft9

# Start all services
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f apphub

# Stop services
docker-compose -f docker/docker-compose.yml down
```

### Local AppHub Development

```bash
# Navigate to apphub
cd apphub

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Run locally
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

### Debugging

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()

# Use logging for production debugging
logger.debug(f"Variable value: {variable}")
```

## AI-Assisted Development Tips

### Effective Prompts for GitHub Copilot

1. **Be Specific with Context**
   ```python
   # Create a FastAPI endpoint for Websoft9 AppHub that retrieves application status
   # Should check Docker container status and return JSON response
   # Include error handling for container not found
   ```

2. **Provide Type Hints**
   ```python
   async def get_app_status(app_id: str) -> dict:
       # Copilot will generate better code with type hints
   ```

3. **Use Descriptive Function Names**
   ```python
   # Good: Copilot understands intent
   async def deploy_application_to_docker_container(config: DeploymentConfig):
       
   # Less effective
   async def deploy(c):
   ```

### Code Generation Examples

When asking Copilot to generate code:

```python
# Prompt: "Create an async function to backup Websoft9 application data"
# Expected pattern:

async def backup_application_data(
    app_id: str,
    backup_path: str,
    include_logs: bool = True
) -> dict:
    """
    Backup application data to specified path
    
    Args:
        app_id: Application identifier
        backup_path: Destination path for backup
        include_logs: Whether to include log files
        
    Returns:
        dict: Backup metadata including path, size, timestamp
    """
    # Implementation...
```

## Performance Optimization

### Async Operations

```python
import asyncio

# ✅ GOOD: Concurrent operations
async def fetch_all_data():
    results = await asyncio.gather(
        fetch_apps(),
        fetch_containers(),
        fetch_repositories()
    )
    return results

# ❌ BAD: Sequential operations
async def fetch_all_data():
    apps = await fetch_apps()
    containers = await fetch_containers()
    repos = await fetch_repositories()
    return [apps, containers, repos]
```

### Database Queries

```python
# Use connection pooling
from databases import Database

database = Database(DATABASE_URL, min_size=5, max_size=20)

# Batch operations when possible
async def get_multiple_apps(app_ids: list[str]):
    query = "SELECT * FROM apps WHERE id = ANY(:ids)"
    return await database.fetch_all(query=query, values={"ids": app_ids})
```

### Caching

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Simple in-memory cache
_cache = {}

async def get_system_info(force_refresh: bool = False):
    cache_key = "system_info"
    
    if not force_refresh and cache_key in _cache:
        cached_data, timestamp = _cache[cache_key]
        if datetime.now() - timestamp < timedelta(minutes=5):
            return cached_data
    
    # Fetch fresh data
    data = await fetch_system_info()
    _cache[cache_key] = (data, datetime.now())
    return data
```

## Commit & PR Guidelines

### Commit Message Format

Follow Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(apphub): add application backup endpoint

Implement POST /api/v1/apps/{id}/backup endpoint that creates
a backup of application data and configuration.

Closes #123

fix(proxy): resolve CORS issue for Portainer access

Update Nginx configuration to properly set Origin headers
for Portainer container access.

Fixes #456
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
```

## Troubleshooting

### Common Issues

**Issue**: Container communication fails
```bash
# Check network
docker network inspect websoft9

# Verify container is on network
docker inspect websoft9-apphub | grep NetworkMode
```

**Issue**: Port already in use
```bash
# Find process using port
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Stop conflicting service or change port in docker-compose.yml
```

**Issue**: Database connection fails
```python
# Add connection retry logic
import asyncio

async def connect_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            await database.connect()
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Pydantic Documentation: https://docs.pydantic.dev/
- Docker Documentation: https://docs.docker.com/
- Python asyncio: https://docs.python.org/3/library/asyncio.html
- Websoft9 Project: https://github.com/websoft9/websoft9

---

**Last Updated**: 2025-01-17

This guide is maintained by the Websoft9 development team. For questions or suggestions, please open an issue on GitHub.
