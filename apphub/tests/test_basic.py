"""
Unit tests for Websoft9 AppHub

This file contains basic tests to verify the application structure and imports.
Add more comprehensive tests as the application evolves.
"""

import pytest
import sys
from pathlib import Path


def test_imports():
    """Test that core modules can be imported"""
    try:
        # Test basic imports don't raise errors
        import fastapi
        import uvicorn
        import pydantic
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required dependency: {e}")


def test_project_structure():
    """Verify project structure exists"""
    project_root = Path(__file__).parent.parent
    
    # Check critical directories exist
    assert (project_root / "src").exists(), "src directory should exist"
    assert (project_root / "requirements.txt").exists(), "requirements.txt should exist"
    assert (project_root / "setup.py").exists(), "setup.py should exist"


def test_python_version():
    """Verify Python version compatibility"""
    assert sys.version_info >= (3, 10), "Python 3.10+ is required"


def test_requirements_file():
    """Verify requirements.txt is readable and valid"""
    requirements_file = Path(__file__).parent.parent / "requirements.txt"
    
    assert requirements_file.exists(), "requirements.txt not found"
    
    with open(requirements_file, 'r') as f:
        requirements = f.read()
        
    # Check for essential dependencies
    essential_deps = ['fastapi', 'uvicorn', 'pydantic']
    for dep in essential_deps:
        assert dep.lower() in requirements.lower(), f"Essential dependency '{dep}' not found in requirements.txt"


@pytest.mark.asyncio
async def test_async_capability():
    """Test async/await functionality works"""
    async def async_function():
        return "async works"
    
    result = await async_function()
    assert result == "async works"


def test_docker_support():
    """Test docker module can be imported"""
    try:
        import docker
        assert True
    except ImportError:
        pytest.fail("Docker SDK not available")


def test_yaml_support():
    """Test YAML support"""
    try:
        import yaml
        
        # Test basic YAML operations
        test_data = {"test": "value", "number": 123}
        yaml_str = yaml.dump(test_data)
        loaded = yaml.safe_load(yaml_str)
        
        assert loaded["test"] == "value"
        assert loaded["number"] == 123
    except ImportError:
        pytest.fail("PyYAML not available")


class TestConfiguration:
    """Test configuration handling"""
    
    def test_env_file_support(self):
        """Test dotenv support"""
        try:
            from dotenv import load_dotenv
            assert True
        except ImportError:
            pytest.fail("python-dotenv not available")
    
    def test_jwt_support(self):
        """Test JWT support"""
        try:
            import jwt
            assert True
        except ImportError:
            pytest.fail("PyJWT not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
