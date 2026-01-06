# Standards - Technical Specifications Documentation

**Websoft9 Project**

## 📋 Document Classification

| Type | Definition | Examples |
|------|------------|----------|
| **Standards (Technical Specifications)** | Define code writing rules and static standards | Naming conventions, API formats, testing methods |
| **Processes (Workflow Specifications)** | Define development collaboration workflows and dynamic processes | Branching strategy, PR workflow, release steps |

---

## 📚 Standards Documentation List

| Document | Category | Use Cases | Core Content |
|----------|----------|-----------|--------------|
| **[api-design.md](./api-design.md)** | Technical Standard | Design RESTful APIs, define response formats, error codes | FastAPI routing design, HTTP methods, unified response format, error code specifications, authentication & authorization |
| **[coding-standards.md](./coding-standards.md)** | Technical Standard | Write Python code, name variables, organize project structure | PEP 8 standards, naming conventions, code structure, error handling, comment standards, async programming |
| **[testing-standards.md](./testing-standards.md)** | Technical Standard | Write unit tests, integration tests, E2E tests | pytest test strategy, test coverage, Mock, async testing, Docker testing |
| **[devops-process.md](./devops-process.md)** | Workflow Standard | Development workflow, Git workflow, code review, Docker deployment | Branching strategy, commit conventions, PR templates, CI/CD configuration, version release |

---

## 🎯 Quick Reference

| Question | Reference Document |
|----------|-------------------|
| How to design API routes? | [api-design.md](./api-design.md) Section 1 |
| How to define response formats? | [api-design.md](./api-design.md) Section 4 |
| How to handle errors? | [api-design.md](./api-design.md) Section 5 |
| **How to implement API authentication?** | **[api-design.md](./api-design.md) Section 6** |
| **How to configure CORS?** | **[api-design.md](./api-design.md) Section 6.4** |
| How to name variables/functions? | [coding-standards.md](./coding-standards.md) Section 1 |
| How to organize project structure? | [coding-standards.md](./coding-standards.md) Section 2 |
| How to use async/await? | [coding-standards.md](./coding-standards.md) Section 5 |
| **How to ensure security?** | **[coding-standards.md](./coding-standards.md) Section 8** |
| **How to manage secrets?** | **[coding-standards.md](./coding-standards.md) Section 8.3** |
| How to write pytest tests? | [testing-standards.md](./testing-standards.md) Section 2 |
| How to use Mock? | [testing-standards.md](./testing-standards.md) Section 2.4 |
| How to test async code? | [testing-standards.md](./testing-standards.md) Section 2.5 |
| How to test Docker environment? | [testing-standards.md](./testing-standards.md) Section 4 |
| How to create branches? | [devops-process.md](./devops-process.md) Section 2.1 |
| How to write Commit Messages? | [devops-process.md](./devops-process.md) Section 2.2 |
| How to create PRs? | [devops-process.md](./devops-process.md) Section 3 |
| How to deploy Docker? | [devops-process.md](./devops-process.md) Section 4 |
| How to release versions? | [devops-process.md](./devops-process.md) Section 5 |

---

## 🏗️ Websoft9 Tech Stack

### Core Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI (Async Web Framework)
- **Containerization**: Docker, Docker Compose
- **Database**: SQLite (Optional PostgreSQL)
- **Cache**: Redis 7+
- **System Management**: RedHat Cockpit 276+

### Architecture Components
- **AppHub**: Core application management service (Python + FastAPI)
- **Nginx Proxy Manager**: Reverse proxy and SSL management
- **Portainer**: Docker container management UI
- **Gitea**: Git repository service

### Development Tools
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Code Quality**: black, flake8, mypy
- **API Documentation**: FastAPI auto-generated (Swagger/ReDoc)
- **CI/CD**: GitHub Actions

---

## 🚀 Quick Start

### Onboarding for New Developers

1. **Reading Order**:
   - [coding-standards.md](./coding-standards.md) - Learn coding standards
   - [api-design.md](./api-design.md) - Learn API design principles
   - [testing-standards.md](./testing-standards.md) - Master testing methods
   - [devops-process.md](./devops-process.md) - Familiarize with development workflow

2. **Environment Setup**:
   ```bash
   # Clone repository
   git clone https://github.com/Websoft9/websoft9.git
   cd websoft9
   
   # Create virtual environment
   cd apphub
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   
   # Start development server
   cd src
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **First Task**:
   - Find the relevant router in `apphub/src/api/v1/routers/`
   - Write code following [api-design.md](./api-design.md)
   - Write tests using [testing-standards.md](./testing-standards.md)
   - Submit PR according to [devops-process.md](./devops-process.md)

---

## 📖 Relationship with Other Documents

```
docs/
├── product/
│   └── product-brief.md          # Product Strategy (Analyst Agent)
├── prd.md                         # Requirements Document (Analyst Agent)
├── architecture/
│   └── tech-architecture.md       # Technical Architecture (Architect Agent)
├── standards/                     # 📍 Current Location
│   ├── README.md                  # This file
│   ├── api-design.md              # API Design Standards
│   ├── coding-standards.md        # Coding Standards
│   ├── testing-standards.md       # Testing Standards
│   └── devops-process.md          # DevOps Process
└── sprint-artifacts/              # Sprint Deliverables
    └── story-*/                   # Specific Story Implementations
```

### Document Usage

- **Product Managers**: Refer to Product Brief, PRD to understand product requirements
- **Architects**: Refer to Architecture to understand system design
- **Development Engineers**: **Refer to Standards (this directory) to learn coding standards and best practices** ⭐
- **Test Engineers**: Refer to Testing Standards to write test cases
- **DevOps Engineers**: Refer to DevOps Process to configure CI/CD

---

## 🔄 Document Maintenance

### Maintenance Responsibilities
- **Maintainer**: Architect Agent (Winston)
- **Reviewer**: Development Team Lead
- **Update Frequency**: Monthly review, immediate updates for major changes

### Revision Workflow
1. Submit modification suggestions (GitHub Issue)
2. Technical review (Team discussion)
3. Document update (PR submission)
4. Team training (Change notification)

### Version History
| Version | Date | Changes | Maintainer |
|---------|------|---------|------------|
| 1.0 | 2026-01-04 | Initial version, created complete Standards documentation suite | Winston (Architect Agent) |

---

**Related Documents**: [PRD](../prd.md) | [Architecture](../architecture/tech-architecture.md) | [Product Brief](../product/product-brief.md)

**Maintainer**: Winston (Architect Agent)  
**Last Updated**: 2026-01-04

---

## ⚠️ Important Reminders

1. **All new feature development must follow these standards**
2. **Code Reviews must check compliance with Standards**
3. **Test coverage must reach 80% or above**
4. **API changes must update documentation**
5. **Security-related code must undergo special review**
