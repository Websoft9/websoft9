# Story 1.1: Docker Compose 开发环境标准化

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P0  
**状态**: Ready for Dev

## User Story
作为开发者，我想要标准化的本地开发环境配置，这样我可以快速启动所有服务并进行本地测试。

## 验收标准
- [ ] `docker-compose-dev.yml` 支持本地源码挂载 (`/data/source`)
- [ ] 所有4个服务可通过 `docker compose up --build` 本地构建
- [ ] `.env` 包含所有必需环境变量
- [ ] 开发模式支持热重载（Python/JS）
- [ ] websoft9 network 配置正确
- [ ] Volume 挂载正确（配置、日志、数据）
- [ ] README 包含开发环境文档

## 技术细节
**涉及文件**:
- `docker/docker-compose-dev.yml`
- `docker/.env`
- `docker/README.md`

**环境要求**:
- Docker Compose v2+
- 与生产 `docker-compose.yml` 网络拓扑一致

## 测试
```bash
cd docker
docker compose -f docker-compose-dev.yml up --build
# 验证所有服务启动
docker ps | grep websoft9
# 修改源码，验证热重载
```
