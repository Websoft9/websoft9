# Standards - Technical Specifications Documentation

**Websoft9 Project**

## 📋 Document Classification

| Type | Definition | Examples |
|------|------------|----------|
| **Standards (Technical Specifications)** | Define code writing rules and static standards | Naming conventions, API formats, testing methods |
| **Processes (Workflow Specifications)** | Define development collaboration workflows and dynamic processes | Branching strategy, PR workflow, release steps |

---

## 📚 Standards Documentation List

### General Engineering Standards

| Document | Category | Use Cases | Core Content |
|----------|----------|-----------|--------------|
| **[api-design.md](./api-design.md)** | Technical Standard | Design RESTful APIs, define response formats, error codes | FastAPI routing design, HTTP methods, unified response format, error code specifications, authentication & authorization |
| **[coding-standards.md](./coding-standards.md)** | Technical Standard | Write Python code, name variables, organize project structure | PEP 8 standards, naming conventions, code structure, error handling, comment standards, async programming |
| **[testing-standards.md](./testing-standards.md)** | Technical Standard | Write unit tests, integration tests, E2E tests | pytest test strategy, test coverage, Mock, async testing, Docker testing |
| **[devops/README.md](./devops/README.md)** | DevOps Package | Enter the release governance package | branching, release governance, app-store release governance, incidents, repository controls |

### Platform Domain Package

Platform capability documents are separated from DevOps release governance.

| Document | Category | Use Cases | Core Content |
|----------|----------|-----------|--------------|
| [../platform/README.md](../platform/README.md) | Platform Package | Enter the platform-domain package | platform capability scope, module boundaries, runtime facts |
| [../platform/app-store-foundation_cn.md](../platform/app-store-foundation_cn.md) | Chinese Platform Spec | Understand the app store as a platform capability | app store ownership, main-branch runtime facts, module boundaries |

### DevOps Execution Package

All current release-governance documents are now centralized under [devops/README.md](./devops/README.md), with Chinese docs as the single execution source of truth.

Recommended entry order for the current Websoft9 DevOps program:

1. [devops/README.md](./devops/README.md)
2. [devops/roadmap_cn.md](./devops/roadmap_cn.md)
3. [devops/entry-baseline_cn.md](./devops/entry-baseline_cn.md)
4. One execution package matching the current phase

| Document | Category | Use Cases | Core Content |
|----------|----------|-----------|--------------|
| [devops/README.md](./devops/README.md) | DevOps Package Index | Enter the release governance package | package scope, reading order, baseline, governance boundaries |
| [devops/roadmap_cn.md](./devops/roadmap_cn.md) | Chinese Master Plan | Understand the release-governance roadmap, main-branch baseline, and current phase order | roadmap, phase status, completion boundary, sequencing |
| [devops/entry-baseline_cn.md](./devops/entry-baseline_cn.md) | Chinese Execution Entry | Enter the DevOps package with a fixed reading order and institutional baseline | package map, execution order, minimal governance baseline |
| [devops/branching-and-artifacts_cn.md](./devops/branching-and-artifacts_cn.md) | Chinese Guide | Explain branching, channels, artifacts, and compatibility | branch model, channel model, artifact model, compatibility thinking |
| [devops/app-store-release-governance_cn.md](./devops/app-store-release-governance_cn.md) | Chinese Execution Spec | Define app store data artifact governance, retention, compatibility, manifest, and rollback rules | catalog/library/manifest/full/incremental/checksum compatibility rules |
| [devops/incident-hotfix-runbook_cn.md](./devops/incident-hotfix-runbook_cn.md) | Chinese Runbook | Execute emergency code and data fixes safely | hotfix steps, data hotfix steps, rollback and record requirements |
| [devops/repo-protection-and-checks_cn.md](./devops/repo-protection-and-checks_cn.md) | Chinese Governance Checklist | Configure branch protection and required checks | protected branches, PR Check Summary, admin checklist |
| [devops/github-manual-configuration_cn.md](./devops/github-manual-configuration_cn.md) | Chinese Manual Ops Checklist | Complete GitHub-side settings that cannot be enforced from the repo | branch protection, required checks, secrets, Pages, actions permissions |

### Platform Lifecycle Package

Platform install, upgrade, uninstall, migration compatibility, and post-upgrade data migration are no longer mixed into the DevOps package.

| Document | Category | Use Cases | Core Content |
|----------|----------|-----------|--------------|
| [../platform-lifecycle/README.md](../platform-lifecycle/README.md) | Platform Lifecycle Package | Enter the platform lifecycle package | package scope, install/upgrade/uninstall boundary, migration boundary |
| [../platform-lifecycle/platform-lifecycle-governance_cn.md](../platform-lifecycle/platform-lifecycle-governance_cn.md) | Chinese Lifecycle Spec | Define install, upgrade, uninstall, compatibility, and migration guarantees | install/upgrade/uninstall contract, migration scope, data migration guarantees |

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
| How should I enter the DevOps document package? | [devops/README.md](./devops/README.md) |
| How to create branches, PRs, and release flows in the current program? | [devops/entry-baseline_cn.md](./devops/entry-baseline_cn.md) |
| How do branches, RCs, formal releases, artifacts, and compatibility work together? | [devops/branching-and-artifacts_cn.md](./devops/branching-and-artifacts_cn.md) |
| What is the full release-governance roadmap and current completion status? | [devops/roadmap_cn.md](./devops/roadmap_cn.md) |
| How should app store data artifacts be stored and retained? | [devops/app-store-release-governance_cn.md](./devops/app-store-release-governance_cn.md) |
| Where is the app store defined as a platform capability? | [../platform/app-store-foundation_cn.md](../platform/app-store-foundation_cn.md) |
| How should urgent code/data fixes be handled? | [devops/incident-hotfix-runbook_cn.md](./devops/incident-hotfix-runbook_cn.md) |
| How should main/dev branch protection be configured? | [devops/repo-protection-and-checks_cn.md](./devops/repo-protection-and-checks_cn.md) |
| Which GitHub settings still require manual configuration? | [devops/github-manual-configuration_cn.md](./devops/github-manual-configuration_cn.md) |
| Where are install/upgrade/uninstall/migration compatibility rules? | [../platform-lifecycle/README.md](../platform-lifecycle/README.md) |

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
   - [devops/README.md](./devops/README.md) - Enter the DevOps package and confirm the release-governance baseline and requirements
   - [../platform/README.md](../platform/README.md) - Enter the platform package when working on platform capabilities and ownership boundaries
   - [../platform-lifecycle/README.md](../platform-lifecycle/README.md) - Enter the platform lifecycle package when working on install, upgrade, uninstall, or migration

2. **Current DevOps Program Reading Order**:
   - [devops/README.md](./devops/README.md) - Enter the consolidated DevOps package
   - [devops/roadmap_cn.md](./devops/roadmap_cn.md) - Check the whole roadmap, main-branch baseline, and current phase
   - [devops/entry-baseline_cn.md](./devops/entry-baseline_cn.md) - Confirm the fixed reading order and institutional baseline
   - One phase-specific execution doc from the DevOps package

3. **Environment Setup**:
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

4. **First Task**:
   - Find the relevant router in `apphub/src/api/v1/routers/`
   - Write code following [api-design.md](./api-design.md)
   - Write tests using [testing-standards.md](./testing-standards.md)
   - Submit PR according to [devops/entry-baseline_cn.md](./devops/entry-baseline_cn.md)

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
│   ├── devops/                     # Release governance package
│       ├── README.md
│       ├── roadmap_cn.md
│       ├── entry-baseline_cn.md
│       ├── branching-and-artifacts_cn.md
│       └── ...
│   └── ../platform/                # Platform domain package
│       ├── README.md
│       └── app-store-foundation_cn.md
├── platform-lifecycle/
│   ├── README.md
│   └── platform-lifecycle-governance_cn.md
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
| 1.1 | 2026-06-05 | Added DevOps branching and artifact guide for release channels, RC, app-store data publication, and hotfix handling | Platform/DevOps |
| 1.2 | 2026-06-05 | Added Chinese execution docs for R2 app-store artifacts, hotfix runbook, and branch protection checklist | Platform/DevOps |
| 1.3 | 2026-06-05 | Added GitHub manual configuration checklist for secrets, Pages, actions, and branch protection rollout | Platform/DevOps |
| 1.4 | 2026-06-05 | Added Chinese master execution plan for the DevOps refactor, including phase status, progress matrix, and next-step sequencing | Platform/DevOps |

---

**Related Documents**: [PRD](../prd.md) | [Architecture](../architecture/tech-architecture.md) | [Product Brief](../product/product-brief.md)

**Maintainer**: Winston (Architect Agent)  
**Last Updated**: 2026-06-05

---

## ⚠️ Important Reminders

1. **All new feature development must follow these standards**
2. **Code Reviews must check compliance with Standards**
3. **Test coverage must reach 80% or above**
4. **API changes must update documentation**
5. **Security-related code must undergo special review**
