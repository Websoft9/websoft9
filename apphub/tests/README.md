# Websoft9 AppHub Tests

This directory contains automated tests for the AppHub service.

## Test Structure

```
tests/
├── test_basic.py           # Basic import and structure tests
├── integration/            # Integration tests (future)
│   └── run.sh             # Integration test runner
└── README.md              # This file
```

## Running Tests

### Prerequisites

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# From apphub directory
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=src --cov-report=html
```

### Run Specific Tests

```bash
# Run a specific file
pytest tests/test_basic.py

# Run a specific test function
pytest tests/test_basic.py::test_imports

# Run tests with a marker
pytest -m unit
pytest -m asyncio
```

### Coverage Reports

After running tests with coverage:

```bash
# View terminal summary
pytest --cov=src --cov-report=term

# Generate HTML report
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML report (for CI)
pytest --cov=src --cov-report=xml
```

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py` or `*_test.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test

```python
import pytest

def test_example():
    """Test description"""
    result = some_function()
    assert result == expected_value

@pytest.mark.asyncio
async def test_async_example():
    """Async test description"""
    result = await some_async_function()
    assert result == expected_value
```

### Test Markers

Use markers to categorize tests:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.asyncio` - Async tests

## Current Test Coverage

The current test suite includes:

- ✅ Basic imports and dependencies
- ✅ Project structure verification
- ✅ Python version compatibility
- ✅ Requirements validation
- ✅ Async/await functionality
- ✅ Docker SDK availability
- ✅ YAML support
- ✅ Environment variable support
- ✅ JWT support

## TODO: Future Tests

- [ ] API endpoint tests (FastAPI routes)
- [ ] Database operations tests
- [ ] Docker operations tests
- [ ] Authentication and authorization tests
- [ ] Error handling tests
- [ ] Integration tests with external services
- [ ] Performance tests

## CI Integration

Tests are automatically run on:
- Push to `main` or `dev` branches
- Pull requests to `main` or `dev` branches

See [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) for CI configuration.

## Troubleshooting

### Import Errors

If you get import errors, make sure to install the package in development mode:

```bash
pip install -e .
```

### Async Test Failures

If async tests fail, ensure pytest-asyncio is installed:

```bash
pip install pytest-asyncio
```

### Docker Tests Failing

Docker SDK tests require Docker to be installed and running:

```bash
docker --version
docker ps
```
