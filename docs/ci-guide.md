# CI/CD Pipeline Guide

This document explains the continuous integration and deployment setup for Websoft9.

## Overview

The CI pipeline automatically runs quality checks and tests on every push and pull request to ensure code quality and reliability.

## CI Workflow

The CI pipeline is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and includes:

### 1. **Lint** - Code Quality Checks
- **Black**: Code formatting verification
- **isort**: Import sorting verification
- **Flake8**: PEP 8 style guide enforcement
- **Pylint**: Code analysis and linting

### 2. **Test** - Automated Testing
- **pytest**: Unit tests execution
- **Coverage**: Code coverage measurement (threshold: 70%)
- **Codecov**: Coverage report upload

### 3. **Build** - Application Building
- **pip install**: Dependencies installation
- **Package build**: Application packaging
- **CLI verification**: Command-line interface testing

### 4. **Security Scan** - Vulnerability Detection
- **Safety**: Python dependency vulnerability scanning
- **Docker Build**: Multi-architecture image building
- **Trivy**: Container image security scanning
- **SARIF Upload**: Security findings to GitHub Security tab

### 5. **Integration Test** - E2E Testing
- Integration tests (runs only on pull requests)
- Validates the complete application workflow

### 6. **Summary** - Pipeline Results
- Aggregates all job results
- Fails the pipeline if any critical job fails

## Triggers

The CI pipeline runs automatically on:

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
```

## Environment Variables

```yaml
env:
  PYTHON_VERSION: '3.11'
  COVERAGE_THRESHOLD: 70
```

## Local Development

### Setup Development Environment

```bash
# Navigate to apphub directory
cd apphub

# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install package in editable mode
pip install -e .
```

### Run Linting Locally

```bash
# Format code
black src/
isort src/

# Check code style
flake8 src/

# Run linting checks (same as CI)
black --check src/
isort --check src/
flake8 src/
pylint src/ --exit-zero
```

### Run Tests Locally

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_basic.py -v

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Build Docker Image Locally

```bash
# Navigate to project root
cd ..

# Download media.zip (or create placeholder)
cd docker/apphub
echo "Test" > placeholder.txt
zip media.zip placeholder.txt
rm placeholder.txt
cd ../..

# Build image
docker build -f docker/apphub/Dockerfile -t websoft9-apphub:local .

# Scan image with Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image websoft9-apphub:local
```

## CI Configuration Files

### Pytest Configuration

**Location**: `apphub/pytest.ini` or `apphub/pyproject.toml`

```ini
[pytest]
testpaths = tests
addopts = -v --strict-markers --cov=src
```

### Flake8 Configuration

**Location**: `apphub/.flake8`

```ini
[flake8]
max-line-length = 127
max-complexity = 10
```

### Black & isort Configuration

**Location**: `apphub/pyproject.toml`

```toml
[tool.black]
line-length = 127
target-version = ['py310', 'py311']

[tool.isort]
profile = "black"
line_length = 127
```

## Viewing CI Results

### GitHub Actions UI

1. Go to [Actions tab](https://github.com/Websoft9/websoft9/actions)
2. Click on the latest workflow run
3. View detailed logs for each job

### Status Badges

The main README displays CI status:

```markdown
[![CI Pipeline](https://github.com/Websoft9/websoft9/actions/workflows/ci.yml/badge.svg)](https://github.com/Websoft9/websoft9/actions/workflows/ci.yml)
```

### Code Coverage

View coverage reports on [Codecov](https://codecov.io/gh/Websoft9/websoft9)

### Security Findings

View security vulnerabilities in the [Security tab](https://github.com/Websoft9/websoft9/security/code-scanning)

## Fixing CI Failures

### Linting Failures

**Problem**: Black or isort formatting issues

**Solution**:
```bash
black src/
isort src/
git add .
git commit -m "fix: apply code formatting"
```

**Problem**: Flake8 style violations

**Solution**: Review the error messages and fix the issues manually, or use:
```bash
autopep8 --in-place --aggressive --aggressive src/
```

### Test Failures

**Problem**: Tests failing

**Solution**:
1. Run tests locally: `pytest -v`
2. Fix the failing tests
3. Verify coverage: `pytest --cov=src`
4. Commit fixes

**Problem**: Coverage below threshold

**Solution**:
1. Identify uncovered code: `pytest --cov=src --cov-report=term-missing`
2. Add tests for uncovered code
3. Or adjust threshold in `.github/workflows/ci.yml` if appropriate

### Build Failures

**Problem**: Package installation fails

**Solution**:
1. Verify `requirements.txt` is valid
2. Test locally: `pip install -r requirements.txt`
3. Check for missing or conflicting dependencies

### Security Scan Failures

**Problem**: Trivy finds vulnerabilities

**Solution**:
1. Review the vulnerability report in GitHub Security tab
2. Update vulnerable dependencies:
   ```bash
   pip install --upgrade <package>
   pip freeze > requirements.txt
   ```
3. If no fix available, document the risk or add exception

## Best Practices

### Before Committing

```bash
# 1. Format code
black src/
isort src/

# 2. Run linting
flake8 src/

# 3. Run tests
pytest

# 4. Check coverage
pytest --cov=src --cov-report=term

# 5. Commit
git add .
git commit -m "feat: your feature description"
git push
```

### Writing Tests

- Write tests for all new features
- Aim for >70% code coverage
- Use descriptive test names
- Use pytest markers (`@pytest.mark.unit`, `@pytest.mark.asyncio`)
- Mock external dependencies

### Pull Requests

- Ensure all CI checks pass before requesting review
- Integration tests will run automatically on PRs
- Address any failing checks promptly

## Continuous Deployment

The CI pipeline does **not** automatically deploy. Deployment is handled by separate workflows:

- **Docker Build**: `.github/workflows/docker.yml`
- **Release**: `.github/workflows/release.yml`

These workflows are triggered on:
- Tagged releases
- Manual workflow dispatch

## Troubleshooting

### GitHub Actions Quota

**Problem**: CI fails due to quota limits

**Solution**: 
- Free tier has limited minutes
- Consider self-hosted runners for private repos
- Optimize CI to run faster (use caching, parallel jobs)

### Cache Issues

**Problem**: Dependencies not caching properly

**Solution**:
```yaml
# Clear cache in GitHub Actions UI
# Or update cache key in workflow file
```

### Docker Build Timeout

**Problem**: Docker build exceeds time limit

**Solution**:
- Use smaller base images
- Reduce number of layers
- Use multi-stage builds
- Enable BuildKit cache

## Contributing

When adding new features:

1. Update tests accordingly
2. Ensure linting passes
3. Maintain or improve code coverage
4. Update documentation if needed
5. Verify CI passes before merging

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Codecov Documentation](https://docs.codecov.com/)

## Support

For CI/CD related issues:
1. Check [workflow runs](https://github.com/Websoft9/websoft9/actions)
2. Review [existing issues](https://github.com/Websoft9/websoft9/issues)
3. Create a new issue with `ci` label
