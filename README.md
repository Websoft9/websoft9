<p align="center">
  <img src="https://github.com/user-attachments/assets/bb01fa37-1f53-4fc6-8992-9f784d02dd40" alt="Websoft9" width="200">
</p>

<h1 align="center">Websoft9</h1>

<p align="center">
  <strong>Web-based PaaS for running 200+ open source applications on your own server.</strong>
</p>

<p align="center">
  <a href="http://www.gnu.org/licenses/gpl-3.0"><img src="https://img.shields.io/badge/License-LGPL%20v3-blue.svg" alt="License"></a>
  <a href="https://github.com/Websoft9/websoft9/actions/workflows/ci.yml"><img src="https://github.com/Websoft9/websoft9/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Websoft9/websoft9/releases"><img src="https://img.shields.io/github/v/release/websoft9/websoft9" alt="Release"></a>
  <a href="https://github.com/Websoft9/websoft9/stargazers"><img src="https://img.shields.io/github/stars/websoft9/websoft9?style=social" alt="Stars"></a>
</p>

---

## What is Websoft9?

Websoft9 is a self-hosted PaaS that lets you deploy and manage **200+ open source applications** (WordPress, GitLab, Mattermost, and more) on a single server — no Kubernetes required.

Think of it as your own private app store: browse, one-click install, manage domains and SSL, back up data, all from a clean web console.

## Quick Start

```bash
# Install on any Linux server with Docker
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh && sudo bash install.sh
```

Then open **http://\<server-ip\>:9000** and follow the setup wizard.

> [!TIP]
> Try the demo: [http://demo.goweb.cc:9000](http://demo.goweb.cc:9000) — user: `demo` / password: `Websoft9@`

## Features

| Category | Capabilities |
|----------|-------------|
| **App Store** | Browse and install 200+ apps in one click — CMS, e-commerce, DevOps, databases |
| **My Apps** | Start, stop, restart, redeploy, view logs, manage files and volumes per app |
| **File Manager** | Web-based file browser with upload, download, edit, and permission management |
| **Terminal** | Browser-based SSH terminal for remote server management |
| **Proxy & SSL** | Domain binding and free Let's Encrypt SSL certificates via Nginx Proxy Manager |
| **Backups** | Scheduled local and S3 remote backups for apps and databases |
| **Docker Compose** | GUI for deploying custom docker-compose stacks |
| **User Management** | Multi-user accounts with role-based access |
| **Monitoring** | Real-time host metrics, service status, and log viewer |

## Architecture

Websoft9 runs as a **single Docker container** that bundles four key open source components:

| Component | Role |
|-----------|------|
| **AppHub** (Python/FastAPI) | Business API — app catalog, lifecycle, auth, settings |
| **Console** (React/TypeScript) | Web management UI |
| **Portainer** | Container and stack orchestration |
| **Nginx Proxy Manager** | Reverse proxy, domains, SSL certificates |

All components are managed by supervisord inside one container — simple to deploy, easy to upgrade.

→ [Architecture overview](docs/architecture.md)

## Cloud Marketplace

Websoft9 is certified and available on major cloud platforms:

<p align="center">
  <a href="https://azuremarketplace.microsoft.com/en-us/marketplace/apps/websoft9inc.websoft9"><img src="https://libs.websoft9.com/Websoft9/logo/marketplace/azure-logo.png" width="40" alt="Azure"></a>&nbsp;
  <a href="https://aws.amazon.com/marketplace/pp/prodview-5jziwpvx4puq4"><img src="https://libs.websoft9.com/Websoft9/logo/marketplace/aws-logo.png" width="40" alt="AWS"></a>&nbsp;
  <a href="https://marketplace.alibabacloud.com/products/201072001/sgcmjj00034378.html"><img src="https://libs.websoft9.com/Websoft9/logo/marketplace/alibabacloud-logo.png" width="40" alt="Alibaba Cloud"></a>&nbsp;
  <a href="https://marketplace.huaweicloud.com/intl/contents/bf4480ae-d0af-422c-b246-e2ec67743f4e"><img src="https://libs.websoft9.com/Websoft9/logo/marketplace/huaweicloud-logo.png" width="40" alt="Huawei Cloud"></a>
</p>

→ [Deployment guide](docs/deployment.md)

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/user.md) | Installation, features, and daily usage |
| [Developer Guide](docs/developer.md) | Dev environment setup, coding standards, contribution |
| [API Reference](docs/api-reference.md) | AppHub REST API endpoints |
| [Deployment Guide](docs/deployment.md) | Production and cloud marketplace deployment |
| [Architecture](docs/architecture.md) | System design and component topology |
| [FAQ](docs/faq.md) | Common questions and troubleshooting |

## Community

- 💬 [GitHub Issues](https://github.com/Websoft9/websoft9/issues) — Bug reports and feature requests
- 🔧 [Contributing Guide](CONTRIBUTING.md) — How to contribute code
- 📦 [Application Templates](https://github.com/Websoft9/docker-library) — 200+ ready-to-deploy apps

## License

Websoft9 is licensed under [LGPL-3.0](LICENSE.md).  
**Additional restriction**: Publishing free or paid images based on this repository to any cloud platform marketplace without authorization is prohibited.
