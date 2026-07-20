# Deployment Guide

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 20.04+, Debian 11+, CentOS 7+ | Ubuntu 22.04+ |
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 8+ GB |
| Disk | 20 GB | 50+ GB SSD |
| Docker | 20.10+ | 24.0+ |

## Production Deployment

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo bash
```

### 2. Install Websoft9

```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh && sudo bash install.sh
```

### 3. Verify Installation

```bash
# Check container status
docker ps --filter "name=websoft9"

# Check logs
docker logs websoft9

# Access console
curl http://localhost:9000
```

## Cloud Marketplace Deployment

Websoft9 is available on major cloud marketplaces:

| Platform | Link |
|----------|------|
| Azure | [Websoft9 on Azure Marketplace](https://azuremarketplace.microsoft.com/en-us/marketplace/apps/websoft9inc.websoft9) |
| AWS | [Websoft9 on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-5jziwpvx4puq4) |
| Alibaba Cloud | [Websoft9 on Alibaba Cloud](https://marketplace.alibabacloud.com/products/201072001/sgcmjj00034378.html) |
| Huawei Cloud | [Websoft9 on Huawei Cloud](https://marketplace.huaweicloud.com/intl/contents/bf4480ae-d0af-422c-b246-e2ec67743f4e) |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBSOFT9_DATA_ROOT` | `/opt/websoft9/data` | Persistent data directory |
| `CONSOLE_PORT` | `9000` | Web console port |
| `IMAGE_REPO` | `websoft9dev/websoft9` | Docker image repository |
| `IMAGE_TAG` | `latest` | Docker image tag |

### Persistence

All persistent data is stored under `WEBSOFT9_DATA_ROOT`:

```
/opt/websoft9/data/
├── config/           # Platform configuration
├── portainer/        # Portainer data (stacks, compose files)
├── gitea/            # Git repositories
├── npm/              # NPM proxy and certificate data
├── apps/             # Application runtime data
└── backups/          # Backup archives
```

## Health Check

```bash
# Platform health endpoint
curl http://localhost:9000/api/health
```

## Monitoring

- Container health: `docker ps --filter "name=websoft9"`
- Resource usage: `docker stats websoft9`
- Service status: Console → Services page
- Application logs: Console → Logs page
