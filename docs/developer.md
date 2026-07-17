# Developer Guide

## Prerequisites

- **Python 3.11+** — for AppHub backend
- **Node.js 22+** — for Console frontend
- **Docker & Docker Compose** — for local runtime
- **Go 1.24+** — for Portainer init helper (optional)

## Project Structure

```
websoft9/
├── apphub/          # Backend API (Python/FastAPI)
│   ├── src/         # Application source
│   └── tests/       # Test suite
├── console/         # Frontend UI (React/TypeScript/Vite)
│   └── src/         # Application source
├── docker/          # Container build & runtime
│   ├── Dockerfile   # Single-container image build
│   └── docker-compose.yml
├── install/         # Installation scripts
├── cli/             # CLI tools
├── scripts/         # Utility scripts
└── docs/            # Documentation
```

## Development Setup

### 1. Backend (AppHub)

```bash
cd apphub

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest --cov=src

# Run development server
uvicorn src.main:app --reload --port 8000
```

### 2. Frontend (Console)

```bash
cd console

# Install dependencies
npm ci

# Start development server
npm run dev
```

### 3. Full Stack (Docker Compose)

```bash
cd docker

# Start with dev compose file
docker compose -f docker-compose.dev.yml up -d --build
```

## Code Standards

### Python (AppHub)
- Formatter: **Black** (line length 100)
- Linter: **Flake8**, **Pylint**
- Import sorting: **isort**
- Type hints required for public APIs
- Test coverage target: ≥70%

### TypeScript (Console)
- Formatter: **ESLint** + **Prettier**
- Strict TypeScript mode enabled
- Component structure: feature-based folders under `src/features/`

## CI/CD

All pull requests must pass:

| Check | Tool |
|-------|------|
| Linting | Black, isort, Flake8, ESLint |
| Tests | Pytest (≥70% coverage) |
| Build | Docker image build |
| Security | Container vulnerability scan |

See [CI/CD Guide](ci-guide.md) for details.

## Contributing

1. Fork the `main` branch
2. Create a feature branch
3. Make changes with tests
4. Ensure all CI checks pass locally
5. Submit a pull request to `main`

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution workflow.
