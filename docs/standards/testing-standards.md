# Testing Standards

**Websoft9 Project - pytest Best Practices**

**Created**: 2026-01-04  
**Maintainer**: Winston (Architect Agent)  
**Version**: 1.0  
**Status**: Active

---

## Table of Contents

1. [Testing Strategy](#1-testing-strategy)
2. [Unit Testing](#2-unit-testing)
3. [Integration Testing](#3-integration-testing)
4. [End-to-End Testing](#4-end-to-end-testing)
5. [Async Testing](#5-async-testing)
6. [Mocking & Fixtures](#6-mocking--fixtures)
7. [Test Coverage](#7-test-coverage)
8. [CI/CD Integration](#8-cicd-integration)

---

## 1. Testing Strategy

### 1.1 Test Pyramid

```
        /\
       /E2E\        10% - End-to-End (slow, fragile, high value)
      /------\
     /Integration\  20% - Integration (medium speed, stable, medium value)
    /--------------\
   /  Unit  Tests  \ 70% - Unit Tests (fast, reliable, low value)
  /------------------\
```

**Websoft9 Test Distribution**:
- **70% Unit Tests**: Core business logic, utility functions, data models
- **20% Integration Tests**: API endpoints, database interactions, Docker integration
- **10% E2E Tests**: Critical business flows (app creation → configuration → deletion)

### 1.2 Test Coverage Goals

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| **core/** (business logic) | 90%+ | 🔴 High |
| **api/routers/** (API endpoints) | 85%+ | 🔴 High |
| **schemas/** (data models) | 80%+ | 🟡 Medium |
| **utils/** (utility functions) | 90%+ | 🔴 High |
| **db/** (database layer) | 75%+ | 🟡 Medium |
| **Overall Project** | **≥ 80%** | 🔴 High |

---

## 2. Unit Testing

### 2.1 AAA Pattern (Arrange-Act-Assert)

```python
# tests/unit/test_app_service.py

import pytest
from core.app_service import AppService
from schemas.app import AppCreate

class TestAppService:
    """Application service unit tests"""
    
    @pytest.mark.asyncio
    async def test_create_app_success(self):
        """Test successful application creation"""
        # Arrange (setup)
        service = AppService()
        app_data = AppCreate(
            app_name="wordpress",
            image="wordpress:latest",
            ports=[8080]
        )
        
        # Act (execute)
        result = await service.create_app(app_data)
        
        # Assert (verify)
        assert result.app_name == "wordpress"
        assert result.status == "running"
        assert result.image == "wordpress:latest"
    
    @pytest.mark.asyncio
    async def test_create_app_duplicate_name(self):
        """Test creating app with duplicate name fails"""
        # Arrange
        service = AppService()
        app_data = AppCreate(app_name="wordpress", image="wordpress:latest")
        
        # Create first app
        await service.create_app(app_data)
        
        # Act & Assert
        with pytest.raises(AppAlreadyExistsException) as exc_info:
            await service.create_app(app_data)
        
        assert "wordpress" in str(exc_info.value)
```

### 2.2 Parameterized Tests

```python
import pytest

class TestAppNameValidation:
    """Application name validation tests"""
    
    @pytest.mark.parametrize("app_name,expected", [
        ("wordpress", True),
        ("my-app", True),
        ("app123", True),
        ("valid-app-name", True),
        ("MyApp", False),        # Uppercase letters
        ("app_name", False),     # Underscore
        ("app@123", False),      # Special characters
        ("-invalid", False),     # Starts with hyphen
        ("invalid-", False),     # Ends with hyphen
        ("ab", False),           # Too short (< 3)
        ("a" * 51, False),       # Too long (> 50)
    ])
    def test_validate_app_name(self, app_name, expected):
        """Test application name validation rules"""
        from core.validators import validate_app_name
        
        if expected:
            assert validate_app_name(app_name) is True
        else:
            with pytest.raises(ValueError):
                validate_app_name(app_name)
```

### 2.3 Exception Testing

```python
import pytest
from exceptions.app_exceptions import (
    AppNotFoundException,
    DockerAPIException
)

class TestAppService:
    
    @pytest.mark.asyncio
    async def test_get_app_not_found(self):
        """Test getting non-existent application"""
        service = AppService()
        
        with pytest.raises(AppNotFoundException) as exc_info:
            await service.get_app("non-existent-app")
        
        assert exc_info.value.error_code == "APP_NOT_FOUND"
        assert "non-existent-app" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_docker_api_failure(self, mocker):
        """Test Docker API call failure"""
        service = AppService()
        
        # Mock Docker API to raise exception
        mocker.patch(
            'docker.DockerClient.containers.run',
            side_effect=docker.errors.APIError("Connection failed")
        )
        
        with pytest.raises(DockerAPIException) as exc_info:
            await service.create_app(AppCreate(
                app_name="test",
                image="nginx"
            ))
        
        assert "Connection failed" in str(exc_info.value)
```

---

## 3. Integration Testing

### 3.1 API Endpoint Testing

```python
# tests/integration/test_apps_api.py

import pytest
from httpx import AsyncClient
from fastapi import status

class TestAppsAPI:
    """Application management API integration tests"""
    
    @pytest.mark.asyncio
    async def test_create_app_api(self, client: AsyncClient, api_key):
        """Test create application API"""
        response = await client.post(
            "/api/v1/apps",
            json={
                "app_name": "wordpress",
                "image": "wordpress:latest",
                "ports": [8080]
            },
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["app_name"] == "wordpress"
        assert data["status"] in ["running", "starting"]
    
    @pytest.mark.asyncio
    async def test_list_apps_api(self, client: AsyncClient, api_key):
        """Test list applications API"""
        # Create several apps first
        for i in range(3):
            await client.post(
                "/api/v1/apps",
                json={"app_name": f"app-{i}", "image": "nginx"},
                headers={"X-API-Key": api_key}
            )
        
        # Query application list
        response = await client.get(
            "/api/v1/apps?page=1&page_size=10",
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) >= 3
        assert data["total"] >= 3
    
    @pytest.mark.asyncio
    async def test_delete_app_api(self, client: AsyncClient, api_key):
        """Test delete application API"""
        # Create app first
        create_response = await client.post(
            "/api/v1/apps",
            json={"app_name": "temp-app", "image": "nginx"},
            headers={"X-API-Key": api_key}
        )
        assert create_response.status_code == 201
        
        # Delete app
        delete_response = await client.delete(
            "/api/v1/apps/temp-app",
            headers={"X-API-Key": api_key}
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify app deleted
        get_response = await client.get(
            "/api/v1/apps/temp-app",
            headers={"X-API-Key": api_key}
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
```

### 3.2 Database Integration Testing

```python
# tests/integration/test_database.py

import pytest
from db.session import get_db
from models.app import App

class TestDatabase:
    """Database integration tests"""
    
    @pytest.mark.asyncio
    async def test_create_and_query_app(self, db_session):
        """Test creating and querying application"""
        # Create application
        app = App(
            app_name="test-app",
            image="nginx:latest",
            status="running"
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        assert app.id is not None
        
        # Query application
        result = await db_session.execute(
            select(App).where(App.app_name == "test-app")
        )
        queried_app = result.scalar_one()
        
        assert queried_app.app_name == "test-app"
        assert queried_app.image == "nginx:latest"
```

---

## 4. End-to-End Testing

### 4.1 Complete Business Flow Testing

```python
# tests/e2e/test_app_lifecycle.py

import pytest
from httpx import AsyncClient
import asyncio

class TestAppLifecycle:
    """Application lifecycle E2E tests"""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_full_app_lifecycle(self, client: AsyncClient, api_key):
        """Test complete app lifecycle: create → configure → start/stop → delete"""
        
        # 1. Create application
        create_response = await client.post(
            "/api/v1/apps",
            json={
                "app_name": "e2e-wordpress",
                "image": "wordpress:latest",
                "ports": [8080],
                "env_vars": {
                    "WORDPRESS_DB_HOST": "mysql",
                    "WORDPRESS_DB_NAME": "wordpress"
                }
            },
            headers={"X-API-Key": api_key}
        )
        assert create_response.status_code == 201
        
        # 2. Wait for app to start
        await asyncio.sleep(5)
        
        # 3. Verify app running status
        status_response = await client.get(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "running"
        
        # 4. Stop application
        stop_response = await client.post(
            "/api/v1/apps/e2e-wordpress/stop",
            headers={"X-API-Key": api_key}
        )
        assert stop_response.status_code == 200
        
        await asyncio.sleep(2)
        
        # 5. Verify app stopped
        status_response = await client.get(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert status_response.json()["status"] == "stopped"
        
        # 6. Restart application
        start_response = await client.post(
            "/api/v1/apps/e2e-wordpress/start",
            headers={"X-API-Key": api_key}
        )
        assert start_response.status_code == 200
        
        # 7. Delete application
        delete_response = await client.delete(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert delete_response.status_code == 204
```

---

## 5. Async Testing

### 5.1 pytest-asyncio

```python
import pytest
import asyncio

# Async test function
@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await some_async_function()
    assert result == "expected"

# Async fixture
@pytest.fixture
async def async_client():
    """Async HTTP client fixture"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

# Using async fixture
@pytest.mark.asyncio
async def test_with_async_fixture(async_client):
    response = await async_client.get("/api/v1/apps")
    assert response.status_code == 200
```

### 5.2 Testing Concurrent Operations

```python
import pytest
import asyncio

class TestConcurrency:
    """Concurrent operations testing"""
    
    @pytest.mark.asyncio
    async def test_concurrent_app_creation(self, client: AsyncClient, api_key):
        """Test concurrent application creation"""
        
        async def create_app(index: int):
            """Create single application"""
            response = await client.post(
                "/api/v1/apps",
                json={
                    "app_name": f"concurrent-app-{index}",
                    "image": "nginx"
                },
                headers={"X-API-Key": api_key}
            )
            return response.status_code
        
        # Concurrently create 10 apps
        results = await asyncio.gather(
            *[create_app(i) for i in range(10)]
        )
        
        # Verify all requests successful
        assert all(code == 201 for code in results)
```

---

## 6. Mocking & Fixtures

### 6.1 pytest Fixtures

```python
# tests/conftest.py

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from main import app
import os

# Session-level fixture (shared across all tests)
@pytest.fixture(scope="session")
def api_key():
    """API Key fixture"""
    return os.getenv("TEST_API_KEY", "test-api-key-12345")

# Function-level fixture (independent per test)
@pytest.fixture
async def client():
    """Async HTTP client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# Database fixture
@pytest.fixture
async def db_session():
    """Database session (rollback after test)"""
    from db.session import SessionLocal
    
    session = SessionLocal()
    yield session
    
    await session.rollback()  # Rollback test data
    await session.close()

# Docker client fixture
@pytest.fixture
def docker_client():
    """Docker client"""
    import docker
    client = docker.from_env()
    yield client
    client.close()

# Cleanup fixture
@pytest.fixture(autouse=True)
async def cleanup_test_apps(docker_client):
    """Auto cleanup test applications"""
    yield
    
    # Cleanup after test
    containers = docker_client.containers.list(
        filters={"name": "test-*"}
    )
    for container in containers:
        container.remove(force=True)
```

### 6.2 pytest-mock (Mock Objects)

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

class TestWithMock:
    """Tests using Mock"""
    
    @pytest.mark.asyncio
    async def test_docker_api_mock(self, mocker):
        """Mock Docker API call"""
        # Mock Docker client
        mock_docker = mocker.patch('docker.from_env')
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        
        mock_docker.return_value.containers.run.return_value = mock_container
        
        # Test
        from core.docker_service import DockerService
        service = DockerService()
        result = await service.create_container("nginx")
        
        assert result.id == "abc123"
        mock_docker.return_value.containers.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_mock(self, mocker):
        """Mock database query"""
        # Mock database query
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {
            "app_name": "wordpress",
            "status": "running"
        }
        
        mocker.patch(
            'db.session.get_db',
            return_value=mock_db
        )
        
        # Test
        from core.app_service import AppService
        service = AppService()
        app = await service.get_app("wordpress")
        
        assert app["app_name"] == "wordpress"
```

---

## 7. Test Coverage

### 7.1 pytest-cov Configuration

```bash
# Install dependencies
pip install pytest-cov

# Run tests and generate coverage report
pytest --cov=apphub --cov-report=html --cov-report=term

# View HTML report
# htmlcov/index.html
```

**Configuration file (pyproject.toml)**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = """
    --cov=apphub/src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
    -v
"""

[tool.coverage.run]
source = ["apphub/src"]
omit = [
    "*/tests/*",
    "*/venv/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### 7.2 Coverage Goals

```python
# Exclude code that doesn't need testing
def debug_function():
    """Debug function"""
    # pragma: no cover
    print("Debug info")

# Abstract methods don't need coverage
from abc import ABC, abstractmethod

class BaseService(ABC):
    @abstractmethod
    def process(self):
        # pragma: no cover
        raise NotImplementedError
```

---

## 8. CI/CD Integration

### 8.1 GitHub Actions Configuration

```yaml
# .github/workflows/test.yml

name: Tests

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main, dev ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      # Docker-in-Docker
      docker:
        image: docker:dind
        options: --privileged
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r apphub/requirements.txt
        pip install -r apphub/requirements-dev.txt
    
    - name: Run unit tests
      run: |
        cd apphub
        pytest tests/unit/ -v --cov=src --cov-report=xml
    
    - name: Run integration tests
      run: |
        cd apphub
        pytest tests/integration/ -v
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./apphub/coverage.xml
        fail_ci_if_error: true
    
    - name: Check coverage threshold
      run: |
        cd apphub
        pytest --cov=src --cov-fail-under=80
```

### 8.2 Local Test Script

```bash
#!/bin/bash
# scripts/run_tests.sh

set -e

echo "🧪 Running Websoft9 AppHub test suite..."

cd apphub

# 1. Code formatting check
echo "📝 Checking code format..."
black --check src/
flake8 src/

# 2. Type checking
echo "🔍 Type checking..."
mypy src/

# 3. Unit tests
echo "🎯 Running unit tests..."
pytest tests/unit/ -v --cov=src --cov-report=term

# 4. Integration tests
echo "🔗 Running integration tests..."
pytest tests/integration/ -v

# 5. E2E tests (optional)
if [ "$RUN_E2E" = "true" ]; then
    echo "🌐 Running E2E tests..."
    pytest tests/e2e/ -v -m e2e
fi

# 6. Generate coverage report
echo "📊 Generating coverage report..."
pytest --cov=src --cov-report=html --cov-report=term

echo "✅ All tests passed!"
```

---

## 9. Testing Best Practices Summary

### 9.1 Test Naming

```python
# ✅ Recommended: Descriptive test names
def test_create_app_with_valid_name_succeeds():
    pass

def test_create_app_with_duplicate_name_raises_exception():
    pass

def test_list_apps_returns_paginated_results():
    pass

# ❌ Avoid: Vague test names
def test_app():
    pass

def test_create():
    pass
```

### 9.2 Test Independence

```python
# ✅ Recommended: Each test independent, no dependency on others
class TestAppService:
    
    @pytest.mark.asyncio
    async def test_create_app(self):
        """Independently test app creation"""
        service = AppService()
        app = await service.create_app(...)
        assert app.app_name == "test-app"
    
    @pytest.mark.asyncio
    async def test_delete_app(self):
        """Independently test app deletion"""
        service = AppService()
        # Create app first (don't depend on previous test)
        app = await service.create_app(...)
        # Then delete
        await service.delete_app(app.app_name)

# ❌ Avoid: Tests with dependencies
class TestAppServiceBad:
    app_name = None  # ❌ Shared state
    
    def test_create(self):
        """First test"""
        self.app_name = create_app()
    
    def test_delete(self):
        """Depends on first test ❌"""
        delete_app(self.app_name)
```

### 9.3 Test Data Management

```python
# tests/factories.py

from factory import Factory, Faker
from models.app import App

class AppFactory(Factory):
    """Application test data factory"""
    
    class Meta:
        model = App
    
    app_name = Faker('slug')
    image = "nginx:latest"
    status = "running"
    ports = [8080]


# Usage
def test_with_factory():
    """Use factory to create test data"""
    app = AppFactory.create(app_name="wordpress")
    assert app.app_name == "wordpress"
    assert app.image == "nginx:latest"
```

---

## Appendix

### A. Common pytest Commands

```bash
# Run all tests
pytest

# Run specific directory
pytest tests/unit/

# Run specific file
pytest tests/unit/test_app_service.py

# Run specific test
pytest tests/unit/test_app_service.py::TestAppService::test_create_app

# Run only failed tests
pytest --lf

# Run in parallel (requires pytest-xdist)
pytest -n auto

# Generate JUnit XML report
pytest --junitxml=report.xml

# Show verbose output
pytest -v -s

# Run tests with markers
pytest -m "not slow"  # Skip slow tests
pytest -m e2e         # Only run E2E tests
```

### B. Recommended Tools

- **Test Framework**: pytest, pytest-asyncio
- **Mocking**: pytest-mock, unittest.mock
- **Coverage**: pytest-cov
- **Factories**: factory_boy
- **HTTP**: httpx, requests-mock
- **Parallel**: pytest-xdist

---

**Document Maintainer**: Winston (Architect Agent)  
**Review Status**: Active  
**Next Steps**: [devops-process.md](./devops-process.md) - DevOps Process Standards

**Related Documentation**: [API Design](./api-design.md) | [Coding Standards](./coding-standards.md) | [DevOps Process](./devops-process.md)
