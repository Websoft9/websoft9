# Standards - 技术规范文档

**Websoft9 项目**

## 📋 文档分类

| 类型 | 定义 | 示例 |
|-----|------|------|
| **Standards（技术规范）** | 定义代码编写规则和静态标准 | 命名规范、API 格式、测试方法 |
| **Processes（流程规范）** | 定义开发协作流程和动态过程 | 分支策略、PR 流程、发布步骤 |

---

## 📚 规范文档列表

| 文档 | 分类 | 适用场景 | 核心内容 |
|-----|------|---------|---------|
| **[api-design.md](./api-design.md)** | 技术规范 | 设计 RESTful API、定义响应格式、错误码 | FastAPI 路由设计、HTTP 方法、统一响应格式、错误码规范、认证授权 |
| **[coding-standards.md](./coding-standards.md)** | 技术规范 | 编写 Python 代码、命名变量、组织项目结构 | PEP 8 规范、命名规范、代码结构、错误处理、注释规范、异步编程 |
| **[testing-standards.md](./testing-standards.md)** | 技术规范 | 编写单元测试、集成测试、E2E 测试 | pytest 测试策略、测试覆盖率、Mock、异步测试、Docker 测试 |
| **[devops-process.md](./devops-process.md)** | 流程规范 | 开发流程、Git 工作流、代码审查、Docker 部署 | 分支策略、Commit 规范、PR 模板、CI/CD 配置、版本发布 |

---

## 🎯 快速查找

| 问题 | 查阅文档 |
|-----|---------|
| 如何设计 API 路由？ | [api-design.md](./api-design.md) Section 1 |
| 如何定义响应格式？ | [api-design.md](./api-design.md) Section 4 |
| 如何处理错误？ | [api-design.md](./api-design.md) Section 5 |
| **如何实现 API 认证？** | **[api-design.md](./api-design.md) Section 6** |
| **如何配置 CORS？** | **[api-design.md](./api-design.md) Section 6.4** |
| 如何命名变量/函数？ | [coding-standards.md](./coding-standards.md) Section 1 |
| 如何组织项目结构？ | [coding-standards.md](./coding-standards.md) Section 2 |
| 如何使用 async/await？ | [coding-standards.md](./coding-standards.md) Section 5 |
| **如何保证安全？** | **[coding-standards.md](./coding-standards.md) Section 8** |
| **如何管理密钥？** | **[coding-standards.md](./coding-standards.md) Section 8.3** |
| 如何编写 pytest 测试？ | [testing-standards.md](./testing-standards.md) Section 2 |
| 如何使用 Mock？ | [testing-standards.md](./testing-standards.md) Section 2.4 |
| 如何测试异步代码？ | [testing-standards.md](./testing-standards.md) Section 2.5 |
| 如何测试 Docker 环境？ | [testing-standards.md](./testing-standards.md) Section 4 |
| 如何创建分支？ | [devops-process.md](./devops-process.md) Section 2.1 |
| 如何写 Commit Message？ | [devops-process.md](./devops-process.md) Section 2.2 |
| 如何创建 PR？ | [devops-process.md](./devops-process.md) Section 3 |
| 如何部署 Docker？ | [devops-process.md](./devops-process.md) Section 4 |
| 如何发布版本？ | [devops-process.md](./devops-process.md) Section 5 |

---

## 🏗️ Websoft9 技术栈

### 核心技术
- **语言**: Python 3.11+
- **框架**: FastAPI (异步 Web 框架)
- **容器化**: Docker, Docker Compose
- **数据库**: SQLite (可选 PostgreSQL)
- **缓存**: Redis 7+
- **系统管理**: RedHat Cockpit 276+

### 架构组件
- **AppHub**: 核心应用管理服务 (Python + FastAPI)
- **Nginx Proxy Manager**: 反向代理和 SSL 管理
- **Portainer**: Docker 容器管理 UI
- **Gitea**: Git 仓库服务

### 开发工具
- **测试**: pytest, pytest-asyncio, pytest-cov
- **代码质量**: black, flake8, mypy
- **API 文档**: FastAPI 自动生成 (Swagger/ReDoc)
- **CI/CD**: GitHub Actions

---

## 🚀 快速开始

### 新开发者入职

1. **阅读顺序**:
   - [coding-standards.md](./coding-standards.md) - 了解代码规范
   - [api-design.md](./api-design.md) - 学习 API 设计原则
   - [testing-standards.md](./testing-standards.md) - 掌握测试方法
   - [devops-process.md](./devops-process.md) - 熟悉开发流程

2. **环境搭建**:
   ```bash
   # 克隆项目
   git clone https://github.com/Websoft9/websoft9.git
   cd websoft9
   
   # 创建虚拟环境
   cd apphub
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   
   # 安装依赖
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   
   # 启动开发服务器
   cd src
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **第一个任务**:
   - 在 `apphub/src/api/v1/routers/` 中找到相关路由
   - 参照 [api-design.md](./api-design.md) 编写代码
   - 使用 [testing-standards.md](./testing-standards.md) 编写测试
   - 按照 [devops-process.md](./devops-process.md) 提交 PR

---

## 📖 与其他文档的关系

```
docs/
├── product/
│   └── product-brief.md          # 产品战略 (Analyst Agent)
├── prd.md                         # 需求文档 (Analyst Agent)
├── architecture/
│   └── tech-architecture.md       # 技术架构 (Architect Agent)
├── standards/                     # 📍 当前位置
│   ├── README.md                  # 本文件
│   ├── api-design.md              # API 设计规范
│   ├── coding-standards.md        # 编码规范
│   ├── testing-standards.md       # 测试规范
│   └── devops-process.md          # DevOps 流程
└── sprint-artifacts/              # Sprint 交付物
    └── story-*/                   # 具体 Story 实现
```

### 文档用途

- **产品经理**: 查阅 Product Brief、PRD 了解产品需求
- **架构师**: 查阅 Architecture 了解系统设计
- **开发工程师**: **查阅 Standards（本目录）学习编码规范和最佳实践** ⭐
- **测试工程师**: 查阅 Testing Standards 编写测试用例
- **DevOps 工程师**: 查阅 DevOps Process 配置 CI/CD

---

## 🔄 文档维护

### 维护职责
- **维护者**: Architect Agent (Winston)
- **审核者**: 开发团队 Lead
- **更新频率**: 每月审查一次,重大变更即时更新

### 修订流程
1. 提出修改建议 (GitHub Issue)
2. 技术评审 (团队讨论)
3. 文档更新 (PR 提交)
4. 团队培训 (变更通知)

### 版本历史
| 版本 | 日期 | 变更内容 | 维护者 |
|------|------|---------|---------|
| 1.0 | 2026-01-04 | 初始版本,创建完整 Standards 文档套件 | Winston (Architect Agent) |

---

**相关文档**: [PRD](../prd.md) | [Architecture](../architecture/tech-architecture.md) | [Product Brief](../product/product-brief.md)

**维护者**: Winston (Architect Agent)  
**最后更新**: 2026-01-04

---

## ⚠️ 重要提醒

1. **所有新功能开发必须遵循这些规范**
2. **Code Review 时必须检查是否符合 Standards**
3. **测试覆盖率必须达到 80% 以上**
4. **API 变更必须更新文档**
5. **安全相关代码必须经过专项审查**
