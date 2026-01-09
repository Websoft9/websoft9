# Quick Start: CI/CD for Developers

This is a quick reference guide for working with the CI/CD pipeline. For detailed information, see [docs/ci-guide.md](docs/ci-guide.md).

## ✅ Pre-commit Checklist

Before pushing code, run these commands:

```bash
cd apphub

# 1. Format and lint
black src/
isort src/
flake8 src/

# 2. Run tests
pytest --cov=src

# 3. Verify build
pip install -e .
```

## 🚀 CI Pipeline Overview

Every push/PR to `main` or `dev` triggers:

| Job | What it does | Pass required |
|-----|-------------|---------------|
| **Lint** | Code style & quality checks | ✅ Yes |
| **Test** | Unit tests + coverage | ✅ Yes |
| **Build** | Package building | ✅ Yes |
| **Security Scan** | Vulnerability scanning | ✅ Yes |
| **Integration Test** | E2E tests (PRs only) | ⚠️ Optional |

## 📦 Setup Development Environment

```bash
# Install dependencies
cd apphub
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

## 🧪 Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test
pytest tests/test_basic.py::test_imports -v

# Open coverage report
open htmlcov/index.html  # macOS/Linux
start htmlcov\index.html  # Windows
```

## 🎨 Code Formatting

```bash
# Auto-format
black src/
isort src/

# Check only (like CI does)
black --check src/
isort --check src/
flake8 src/
```

## 🔍 Common CI Failures

### ❌ Formatting errors
```bash
# Fix: Run formatters
black src/
isort src/
```

### ❌ Test failures
```bash
# Fix: Run tests locally and debug
pytest -v
pytest tests/test_failing.py::test_name --pdb
```

### ❌ Coverage too low
```bash
# Fix: Add more tests
pytest --cov=src --cov-report=term-missing
# Add tests for uncovered lines
```

### ❌ Build errors
```bash
# Fix: Check dependencies
pip install -r requirements.txt
pip install -e .
```

## 🔐 Security Scans

```bash
# Check Python dependencies
pip install safety
safety check -r requirements.txt

# Scan Docker image (requires Docker)
docker build -t websoft9-apphub:test .
trivy image websoft9-apphub:test
```

## 📊 View CI Results

- **Actions Tab**: https://github.com/Websoft9/websoft9/actions
- **Coverage Report**: https://codecov.io/gh/Websoft9/websoft9
- **Security Alerts**: https://github.com/Websoft9/websoft9/security

## 📝 Pull Request Template

When creating a PR, the template will auto-populate. Make sure to:

- [ ] Describe your changes
- [ ] Check the type of change
- [ ] Link related issues
- [ ] Verify all tests pass
- [ ] Complete the checklist

## 🆘 Getting Help

1. Read [docs/ci-guide.md](docs/ci-guide.md)
2. Check [GitHub Actions logs](https://github.com/Websoft9/websoft9/actions)
3. Review [CONTRIBUTING.md](CONTRIBUTING.md)
4. Ask in [Issues](https://github.com/Websoft9/websoft9/issues)

## 🔗 Quick Links

- [CI Workflow File](.github/workflows/ci.yml)
- [AppHub Tests](apphub/tests/)
- [pytest Configuration](apphub/pytest.ini)
- [Code Style Config](apphub/pyproject.toml)
