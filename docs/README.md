# Websoft9 Documentation

Welcome to the Websoft9 documentation. Websoft9 is a web-based PaaS/Linux Panel for running 200+ open source applications on your own server.

## Quick Navigation

| Document | Description |
|----------|-------------|
| [Getting Started](user.md) | Installation, first login, and basic usage |
| [Architecture](architecture.md) | System architecture, components, and design decisions |
| [Developer Guide](developer.md) | Development environment setup, coding standards, and contribution workflow |
| [API Reference](api-reference.md) | AppHub REST API endpoints and usage |
| [Deployment](deployment.md) | Production deployment, cloud marketplace, and operations |
| [FAQ](faq.md) | Frequently asked questions |

## Project Resources

- [Main Repository](https://github.com/Websoft9/websoft9)
- [Application Templates](https://github.com/Websoft9/docker-library)
- [Issue Tracker](https://github.com/Websoft9/websoft9/issues)
- [Contributing Guide](../CONTRIBUTING.md)
- [Security Policy](../SECURITY.md)
- [Changelog](../CHANGELOG.md)

## Product Overview

Websoft9 packages four key open source components into a single-container control plane:

- **Gitea** — Git repository and embedded workspace
- **Portainer** — Container and stack management
- **Nginx Proxy Manager** — Reverse proxy, SSL, and domain management
- **AppHub** — Application catalog, lifecycle, and business API

All four run inside one Docker container, managed by supervisord, and exposed through a unified web console at port `9000`.
