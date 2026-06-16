# Websoft9 Documentation

This directory contains all project documentation following the BMad Method workflow structure, inspired by modern software development best practices.

---

## 📋 Documentation Hierarchy

```
Product Strategy (What & Why)
  ↓
Requirements (What to Build)
  ↓
Architecture (How to Build)
  ↓
Implementation (Development)
  ↓
Deployment & Operations
```

---

## 📁 Directory Structure

| Directory | Purpose | Owner | Contents |
|-----------|---------|-------|----------|
| **product/** | Product discovery & strategy | Product Manager | Product briefs, market analysis |
| **architecture/** | System design & tech decisions | Architect | Architecture diagrams, ADRs |
| **api.swagger.json** | API specification | Development Team | OpenAPI/Swagger definitions |
| **prd.md** | Product requirements | Product Manager | Functional & non-functional requirements |
| **developer.md** | Development guidelines | Dev Lead | Contributor guide, coding standards |
| **user.md** | User documentation | Support Team | FAQs, how-to guides |
| **MAINTAINERS.md** | Project governance | Core Team | Roles, responsibilities, processes |

---

## 🔄 Document Relationships

### Product Brief → PRD → Architecture

**1. Product Brief defines "WHY and WHAT"**
- Market positioning and competitive analysis
- Target users and use cases
- Business value and success metrics
- High-level feature priorities

**2. PRD defines "WHAT to build"** (functional requirements)
- Detailed feature specifications
- Acceptance criteria
- User stories
- Non-functional requirements

**3. Architecture defines "HOW to build"** (technical approach)
- Technology stack decisions
- System design and component integration
- Data architecture and API design
- Security and performance strategies

---

## 📖 Key Documents

### Strategic Documents

#### [Product Brief](product/product-brief.md)
**Purpose**: Define product vision, market fit, and strategic direction

**Key Sections:**
- Executive Summary
- Problem Statement & Market Analysis
- Proposed Solution & Differentiators
- Target Users & Use Cases
- Competitive Positioning
- Go-to-Market Strategy
- Roadmap

**Audience**: Executives, investors, product team

---

#### [Edition Strategy](product/edition-strategy_cn.md)
**Purpose**: Define the minimal product-edition, cloud marketplace, and upgrade strategy for Community, Standard, and Enterprise offers

**Key Sections:**
- Single-image multi-edition strategy
- Marketplace initialization model
- Edition entitlement file design
- Community to Standard upgrade flow

**Audience**: Product, architecture, development, release, marketplace operations

---

#### [PRD - Product Requirements Document](prd.md)
**Purpose**: Detailed functional and non-functional requirements

**Key Sections:**
- Core Functional Requirements (FR-XXX-XXX)
- Non-Functional Requirements (NFR-XXX)
- User Stories & Acceptance Tests
- MVP Scope & Priorities
- Integration Requirements

**Audience**: Development team, QA team, product managers

---

### Technical Documents

#### [Technical Architecture](architecture/tech-architecture.md)
**Purpose**: System design and implementation approach

**Key Sections:**
- Architecture Overview & Technology Stack
- Component Architecture (Cockpit, AppHub, Docker, etc.)
- Data Architecture & API Design
- Security Architecture
- Performance & Scalability
- Deployment Architecture
- Architecture Decision Records (ADRs)

**Audience**: Architects, senior developers, DevOps

---

### Operational Documents

#### [Developer Guide](developer.md)
**Purpose**: How to contribute and develop Websoft9

**Contents:**
- Development setup
- Coding standards
- Release process
- Testing guidelines

**Audience**: Contributors, development team

---

#### [User Guide](user.md)
**Purpose**: How to use and troubleshoot Websoft9

**Contents:**
- FAQ
- Common issues and solutions
- Best practices

**Audience**: End users, support team

---

#### [Maintainers Guide](MAINTAINERS.md)
**Purpose**: Project governance and maintenance processes

**Contents:**
- Team roles and responsibilities
- Pull request workflow
- Issue triage
- Release management

**Audience**: Core maintainers

---

## 🚀 How to Use This Documentation

### For Product Managers
1. Start with **[Product Brief](product/product-brief.md)** to understand strategic direction
2. Reference **[PRD](prd.md)** for detailed requirements
3. Track progress using GitHub Issues/Projects

### For Developers
1. Read **[Architecture](architecture/tech-architecture.md)** to understand system design
2. Follow **[Developer Guide](developer.md)** for coding standards
3. Refer to **[PRD](prd.md)** for acceptance criteria
4. Check **[API Documentation](apidocs/index.html)** for API specs

### For New Contributors
1. Read **[README.md](../README.md)** for project overview
2. Review **[Developer Guide](developer.md)** for setup instructions
3. Check **[MAINTAINERS.md](MAINTAINERS.md)** for contribution process
4. Start with issues labeled `good first issue`

### For Users
1. Start with **[User Guide](user.md)** for FAQs
2. Check **[Product Brief](product/product-brief.md)** for feature roadmap
3. Join community channels for support

---

## 📊 Documentation Standards

### Writing Principles

1. **Clarity Over Cleverness**: Write for understanding, not to impress
2. **Actionable Content**: Every document should enable a decision or action
3. **Consistent Structure**: Follow established templates and formats
4. **Living Documents**: Update as product evolves

### Markdown Conventions

```markdown
# H1 - Document Title (one per document)
## H2 - Major Sections
### H3 - Subsections
#### H4 - Details

**Bold** for emphasis
*Italics* for terminology
`code` for commands and code references
```

### Document Metadata

All major documents should include frontmatter:

```markdown
---
title: Document Title
author: Team Name
date: YYYY-MM-DD
status: Active | Draft | Deprecated
version: X.Y
---
```

---

## 🔗 Related Resources

### Code Repositories
- [Websoft9 Core](https://github.com/Websoft9/websoft9)
- [Docker Library](https://github.com/Websoft9/docker-library) - Application templates
- [Cockpit Plugins](https://github.com/Websoft9?q=plugin) - UI extensions

### External Documentation
- [Cockpit Project](https://cockpit-project.org/guide/latest/)
- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Framework](https://fastapi.tiangolo.com/)
- [Nginx Proxy Manager](https://nginxproxymanager.com/guide/)

### Community
- [Demo Server](http://demo.goweb.cc:9000/) - Try Websoft9 live
- [Slack Workspace](https://websoft9-hq.slack.com/) - Community chat
- [GitHub Discussions](https://github.com/Websoft9/websoft9/discussions) - Q&A forum

---

## 📝 Contributing to Documentation

### Documentation Issues
- Found a typo or outdated information? [Open an issue](https://github.com/Websoft9/websoft9/issues/new)
- Want to improve a section? [Submit a pull request](https://github.com/Websoft9/websoft9/pulls)

### Documentation Guidelines

**Before submitting:**
1. Check spelling and grammar
2. Verify links are working
3. Test code examples
4. Follow existing structure and style
5. Update table of contents if needed

**Review process:**
- Documentation PRs reviewed by core team
- Merged within 7 days (for minor updates)
- Technical content requires architect approval

---

## 📅 Document Maintenance

### Review Schedule

| Document | Review Frequency | Owner |
|----------|------------------|-------|
| Product Brief | Quarterly | Product Manager |
| PRD | Per release cycle | Product + Dev Team |
| Architecture | Bi-annually | Architect |
| Developer Guide | Per major release | Dev Lead |
| User Guide | Monthly | Support Team |

### Version Control

- **Major updates**: Increment version number (1.0 → 2.0)
- **Minor updates**: Update date only
- **Deprecated docs**: Move to `docs/archived/` with deprecation notice

---

## 🎯 Document Status Legend

| Status | Meaning |
|--------|---------|
| ✅ **Active** | Current and accurate |
| 🔨 **Draft** | In progress, not finalized |
| ⚠️ **Review Needed** | Requires technical review |
| 📦 **Archived** | Outdated, kept for reference |
| ❌ **Deprecated** | No longer valid, do not use |

---

## 🏆 Documentation Quality Metrics

We track documentation effectiveness through:

- **Completeness**: All sections filled, no TODO placeholders
- **Accuracy**: Content reflects current implementation
- **Findability**: Searchable, well-indexed, clear structure
- **Usability**: Easy to read, actionable, well-formatted
- **Feedback**: User ratings, issue reports, support tickets reduced

---

**Last Updated**: 2026-01-04  
**Maintained By**: Websoft9 Documentation Team  
**Next Review**: 2026-04-01

---

*For questions or suggestions about this documentation, please [open an issue](https://github.com/Websoft9/websoft9/issues/new) or contact the documentation team.*
