# 测试规范

**Websoft9 项目 - pytest 测试最佳实践**

**创建日期**: 2026-01-04  
**维护者**: Winston (Architect Agent)  
**版本**: 1.0  
**状态**: Active

---

## 目录

1. [测试策略](#1-测试策略)
2. [单元测试](#2-单元测试)
3. [集成测试](#3-集成测试)
4. [端到端测试](#4-端到端测试)
5. [异步测试](#5-异步测试)
6. [Mock 与 Fixture](#6-mock-与-fixture)
7. [测试覆盖率](#7-测试覆盖率)
8. [CI/CD 集成](#8-cicd-集成)

---

## 1. 测试策略

### 1.1 测试金字塔

```
        /\
       /E2E\        10% - 端到端测试 (慢,脆弱,高价值)
      /------\
     /Integration\  20% - 集成测试 (中速,稳定,中价值)
    /--------------\
   /  Unit  Tests  \ 70% - 单元测试 (快速,可靠,低价值)
  /------------------\
```

**Websoft9 测试分布**:
- **70% 单元测试**: 核心业务逻辑、工具函数、数据模型
- **20% 集成测试**: API 端点、数据库交互、Docker 集成
- **10% E2E 测试**: 关键业务流程 (应用创建→配置→删除)

### 1.2 测试覆盖率目标

| 模块 | 目标覆盖率 | 优先级 |
|------|-----------|--------|
| **core/** (业务逻辑) | 90%+ | 🔴 高 |
| **api/routers/** (API 端点) | 85%+ | 🔴 高 |
| **schemas/** (数据模型) | 80%+ | 🟡 中 |
| **utils/** (工具函数) | 90%+ | 🔴 高 |
| **db/** (数据库层) | 75%+ | 🟡 中 |
| **整体项目** | **≥ 80%** | 🔴 高 |

---

## 2. 单元测试

### 2.1 AAA 模式 (Arrange-Act-Assert)

```python
# tests/unit/test_app_service.py

import pytest
from core.app_service import AppService
from schemas.app import AppCreate

class TestAppService:
    """应用服务单元测试"""
    
    @pytest.mark.asyncio
    async def test_create_app_success(self):
        """测试成功创建应用"""
        # Arrange (准备)
        service = AppService()
        app_data = AppCreate(
            app_name="wordpress",
            image="wordpress:latest",
            ports=[8080]
        )
        
        # Act (执行)
        result = await service.create_app(app_data)
        
        # Assert (断言)
        assert result.app_name == "wordpress"
        assert result.status == "running"
        assert result.image == "wordpress:latest"
    
    @pytest.mark.asyncio
    async def test_create_app_duplicate_name(self):
        """测试创建重名应用失败"""
        # Arrange
        service = AppService()
        app_data = AppCreate(app_name="wordpress", image="wordpress:latest")
        
        # 先创建一个应用
        await service.create_app(app_data)
        
        # Act & Assert
        with pytest.raises(AppAlreadyExistsException) as exc_info:
            await service.create_app(app_data)
        
        assert "wordpress" in str(exc_info.value)
```

### 2.2 参数化测试

```python
import pytest

class TestAppNameValidation:
    """应用名称验证测试"""
    
    @pytest.mark.parametrize("app_name,expected", [
        ("wordpress", True),
        ("my-app", True),
        ("app123", True),
        ("valid-app-name", True),
        ("MyApp", False),        # 大写字母
        ("app_name", False),     # 下划线
        ("app@123", False),      # 特殊字符
        ("-invalid", False),     # 以连字符开头
        ("invalid-", False),     # 以连字符结尾
        ("ab", False),           # 太短 (< 3)
        ("a" * 51, False),       # 太长 (> 50)
    ])
    def test_validate_app_name(self, app_name, expected):
        """测试应用名称验证规则"""
        from core.validators import validate_app_name
        
        if expected:
            assert validate_app_name(app_name) is True
        else:
            with pytest.raises(ValueError):
                validate_app_name(app_name)
```

### 2.3 异常测试

```python
import pytest
from exceptions.app_exceptions import (
    AppNotFoundException,
    DockerAPIException
)

class TestAppService:
    
    @pytest.mark.asyncio
    async def test_get_app_not_found(self):
        """测试获取不存在的应用"""
        service = AppService()
        
        with pytest.raises(AppNotFoundException) as exc_info:
            await service.get_app("non-existent-app")
        
        assert exc_info.value.error_code == "APP_NOT_FOUND"
        assert "non-existent-app" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_docker_api_failure(self, mocker):
        """测试 Docker API 调用失败"""
        service = AppService()
        
        # Mock Docker API 抛出异常
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

## 3. 集成测试

### 3.1 API 端点测试

```python
# tests/integration/test_apps_api.py

import pytest
from httpx import AsyncClient
from fastapi import status

class TestAppsAPI:
    """应用管理 API 集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_app_api(self, client: AsyncClient, api_key):
        """测试创建应用 API"""
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
        """测试列出应用 API"""
        # 先创建几个应用
        for i in range(3):
            await client.post(
                "/api/v1/apps",
                json={"app_name": f"app-{i}", "image": "nginx"},
                headers={"X-API-Key": api_key}
            )
        
        # 查询应用列表
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
        """测试删除应用 API"""
        # 先创建应用
        create_response = await client.post(
            "/api/v1/apps",
            json={"app_name": "temp-app", "image": "nginx"},
            headers={"X-API-Key": api_key}
        )
        assert create_response.status_code == 201
        
        # 删除应用
        delete_response = await client.delete(
            "/api/v1/apps/temp-app",
            headers={"X-API-Key": api_key}
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # 验证应用已删除
        get_response = await client.get(
            "/api/v1/apps/temp-app",
            headers={"X-API-Key": api_key}
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
```

### 3.2 数据库集成测试

```python
# tests/integration/test_database.py

import pytest
from db.session import get_db
from models.app import App

class TestDatabase:
    """数据库集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_and_query_app(self, db_session):
        """测试创建和查询应用"""
        # 创建应用
        app = App(
            app_name="test-app",
            image="nginx:latest",
            status="running"
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        assert app.id is not None
        
        # 查询应用
        result = await db_session.execute(
            select(App).where(App.app_name == "test-app")
        )
        queried_app = result.scalar_one()
        
        assert queried_app.app_name == "test-app"
        assert queried_app.image == "nginx:latest"
```

---

## 4. 端到端测试

### 4.1 完整业务流程测试

```python
# tests/e2e/test_app_lifecycle.py

import pytest
from httpx import AsyncClient
import asyncio

class TestAppLifecycle:
    """应用生命周期 E2E 测试"""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_full_app_lifecycle(self, client: AsyncClient, api_key):
        """测试应用完整生命周期: 创建 → 配置 → 启停 → 删除"""
        
        # 1. 创建应用
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
        
        # 2. 等待应用启动
        await asyncio.sleep(5)
        
        # 3. 验证应用运行状态
        status_response = await client.get(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "running"
        
        # 4. 停止应用
        stop_response = await client.post(
            "/api/v1/apps/e2e-wordpress/stop",
            headers={"X-API-Key": api_key}
        )
        assert stop_response.status_code == 200
        
        await asyncio.sleep(2)
        
        # 5. 验证应用已停止
        status_response = await client.get(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert status_response.json()["status"] == "stopped"
        
        # 6. 重启应用
        start_response = await client.post(
            "/api/v1/apps/e2e-wordpress/start",
            headers={"X-API-Key": api_key}
        )
        assert start_response.status_code == 200
        
        # 7. 删除应用
        delete_response = await client.delete(
            "/api/v1/apps/e2e-wordpress",
            headers={"X-API-Key": api_key}
        )
        assert delete_response.status_code == 204
```

---

## 5. 异步测试

### 5.1 pytest-asyncio

```python
import pytest
import asyncio

# 异步测试函数
@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await some_async_function()
    assert result == "expected"

# 异步 fixture
@pytest.fixture
async def async_client():
    """异步 HTTP 客户端 fixture"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

# 使用异步 fixture
@pytest.mark.asyncio
async def test_with_async_fixture(async_client):
    response = await async_client.get("/api/v1/apps")
    assert response.status_code == 200
```

### 5.2 测试并发操作

```python
import pytest
import asyncio

class TestConcurrency:
    """并发操作测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_app_creation(self, client: AsyncClient, api_key):
        """测试并发创建应用"""
        
        async def create_app(index: int):
            """创建单个应用"""
            response = await client.post(
                "/api/v1/apps",
                json={
                    "app_name": f"concurrent-app-{index}",
                    "image": "nginx"
                },
                headers={"X-API-Key": api_key}
            )
            return response.status_code
        
        # 并发创建 10 个应用
        results = await asyncio.gather(
            *[create_app(i) for i in range(10)]
        )
        
        # 验证所有请求成功
        assert all(code == 201 for code in results)
```

---

## 6. Mock 与 Fixture

### 6.1 pytest Fixture

```python
# tests/conftest.py

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from main import app
import os

# 会话级别 fixture (所有测试共享)
@pytest.fixture(scope="session")
def api_key():
    """API Key fixture"""
    return os.getenv("TEST_API_KEY", "test-api-key-12345")

# 函数级别 fixture (每个测试独立)
@pytest.fixture
async def client():
    """异步 HTTP 客户端"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# 数据库 fixture
@pytest.fixture
async def db_session():
    """数据库会话 (测试后回滚)"""
    from db.session import SessionLocal
    
    session = SessionLocal()
    yield session
    
    await session.rollback()  # 回滚测试数据
    await session.close()

# Docker 客户端 fixture
@pytest.fixture
def docker_client():
    """Docker 客户端"""
    import docker
    client = docker.from_env()
    yield client
    client.close()

# 清理 fixture
@pytest.fixture(autouse=True)
async def cleanup_test_apps(docker_client):
    """自动清理测试应用"""
    yield
    
    # 测试结束后清理
    containers = docker_client.containers.list(
        filters={"name": "test-*"}
    )
    for container in containers:
        container.remove(force=True)
```

### 6.2 pytest-mock (Mock 对象)

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

class TestWithMock:
    """使用 Mock 的测试"""
    
    @pytest.mark.asyncio
    async def test_docker_api_mock(self, mocker):
        """Mock Docker API 调用"""
        # Mock Docker 客户端
        mock_docker = mocker.patch('docker.from_env')
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        
        mock_docker.return_value.containers.run.return_value = mock_container
        
        # 测试
        from core.docker_service import DockerService
        service = DockerService()
        result = await service.create_container("nginx")
        
        assert result.id == "abc123"
        mock_docker.return_value.containers.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_mock(self, mocker):
        """Mock 数据库查询"""
        # Mock 数据库查询
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {
            "app_name": "wordpress",
            "status": "running"
        }
        
        mocker.patch(
            'db.session.get_db',
            return_value=mock_db
        )
        
        # 测试
        from core.app_service import AppService
        service = AppService()
        app = await service.get_app("wordpress")
        
        assert app["app_name"] == "wordpress"
```

---

## 7. 测试覆盖率

### 7.1 pytest-cov 配置

```bash
# 安装依赖
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=apphub --cov-report=html --cov-report=term

# 查看 HTML 报告
# htmlcov/index.html
```

**配置文件 (pyproject.toml)**:
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

### 7.2 覆盖率目标

```python
# 排除不需要测试的代码
def debug_function():
    """调试函数"""
    # pragma: no cover
    print("Debug info")

# 抽象方法不需要覆盖
from abc import ABC, abstractmethod

class BaseService(ABC):
    @abstractmethod
    def process(self):
        # pragma: no cover
        raise NotImplementedError
```

---

## 8. CI/CD 集成

### 8.1 GitHub Actions 配置

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

### 8.2 本地测试脚本

```bash
#!/bin/bash
# scripts/run_tests.sh

set -e

echo "🧪 运行 Websoft9 AppHub 测试套件..."

cd apphub

# 1. 代码格式检查
echo "📝 检查代码格式..."
black --check src/
flake8 src/

# 2. 类型检查
echo "🔍 类型检查..."
mypy src/

# 3. 单元测试
echo "🎯 运行单元测试..."
pytest tests/unit/ -v --cov=src --cov-report=term

# 4. 集成测试
echo "🔗 运行集成测试..."
pytest tests/integration/ -v

# 5. E2E 测试 (可选)
if [ "$RUN_E2E" = "true" ]; then
    echo "🌐 运行 E2E 测试..."
    pytest tests/e2e/ -v -m e2e
fi

# 6. 生成覆盖率报告
echo "📊 生成覆盖率报告..."
pytest --cov=src --cov-report=html --cov-report=term

echo "✅ 所有测试通过!"
```

---

## 9. 测试最佳实践总结

### 9.1 测试命名

```python
# ✅ 推荐: 描述性测试名称
def test_create_app_with_valid_name_succeeds():
    pass

def test_create_app_with_duplicate_name_raises_exception():
    pass

def test_list_apps_returns_paginated_results():
    pass

# ❌ 避免: 模糊的测试名称
def test_app():
    pass

def test_create():
    pass
```

### 9.2 测试独立性

```python
# ✅ 推荐: 每个测试独立,不依赖其他测试
class TestAppService:
    
    @pytest.mark.asyncio
    async def test_create_app(self):
        """独立测试创建应用"""
        service = AppService()
        app = await service.create_app(...)
        assert app.app_name == "test-app"
    
    @pytest.mark.asyncio
    async def test_delete_app(self):
        """独立测试删除应用"""
        service = AppService()
        # 先创建应用 (不依赖上一个测试)
        app = await service.create_app(...)
        # 再删除
        await service.delete_app(app.app_name)

# ❌ 避免: 测试之间有依赖
class TestAppServiceBad:
    app_name = None  # ❌ 共享状态
    
    def test_create(self):
        """第一个测试"""
        self.app_name = create_app()
    
    def test_delete(self):
        """依赖第一个测试 ❌"""
        delete_app(self.app_name)
```

### 9.3 测试数据管理

```python
# tests/factories.py

from factory import Factory, Faker
from models.app import App

class AppFactory(Factory):
    """应用测试数据工厂"""
    
    class Meta:
        model = App
    
    app_name = Faker('slug')
    image = "nginx:latest"
    status = "running"
    ports = [8080]


# 使用
def test_with_factory():
    """使用工厂创建测试数据"""
    app = AppFactory.create(app_name="wordpress")
    assert app.app_name == "wordpress"
    assert app.image == "nginx:latest"
```

---

## 附录

### A. pytest 常用命令

```bash
# 运行所有测试
pytest

# 运行指定目录
pytest tests/unit/

# 运行指定文件
pytest tests/unit/test_app_service.py

# 运行指定测试
pytest tests/unit/test_app_service.py::TestAppService::test_create_app

# 只运行失败的测试
pytest --lf

# 并行运行 (需要 pytest-xdist)
pytest -n auto

# 生成 JUnit XML 报告
pytest --junitxml=report.xml

# 显示详细输出
pytest -v -s

# 运行带标记的测试
pytest -m "not slow"  # 跳过慢速测试
pytest -m e2e         # 只运行 E2E 测试
```

### B. 推荐工具

- **测试框架**: pytest, pytest-asyncio
- **Mock**: pytest-mock, unittest.mock
- **覆盖率**: pytest-cov
- **工厂**: factory_boy
- **HTTP**: httpx, requests-mock
- **并行**: pytest-xdist

---

**文档维护**: Winston (Architect Agent)  
**审核状态**: Active  
**下一步**: [devops-process.md](./devops-process.md) - DevOps 流程规范

**相关文档**: [API Design](./api-design.md) | [Coding Standards](./coding-standards.md) | [DevOps Process](./devops-process.md)
