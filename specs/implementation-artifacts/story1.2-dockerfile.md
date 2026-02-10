# Story 1.2: Dockerfile 改造

**Epic**: Epic 1 - Infrastructure & Build System  
**Priority**: P0  
**Status**: 🔄 规划中 (Updated 2026-02-10)

## 目标
改造 Dockerfile，适应新架构：移除旧后端（apphub/apphub-cron），新增 Convex 后端，保持单体容器模式。

## 架构变更

### 改造前后对比

| 组件 | 改造前 | 改造后 |
|------|--------|--------|
| **容器数量** | 1个单体容器 | 1个单体容器（不变） |
| **后端** | Python (apphub + apphub-cron) | Convex |
| **前端** | Cockpit Web UI | Dashboard (React) |
| **API 路径** | `/w9api/` | `/baas/` |
| **端口** | 9090 | 9090（不变） |

### 容器内服务清单

**保留的服务**（不变）：
- ✅ nginx（反向代理）
- ✅ portainer
- ✅ gitea
- ✅ ssh
- ✅ cockpit-ws + cockpit-bridge
- ✅ dbus
- ✅ /w9media 静态服务

**移除的服务**：
- ❌ apphub（Python 后端）
- ❌ apphub-cron

**新增的服务**：
- ✅ Convex 后端（BaaS）
- ✅ Dashboard 前端（替换 Cockpit Web UI）

## 架构图

```
                        ┌──────────────────────────────┐
                        │   websoft9-cockpit 容器      │
                        │         (单体容器)            │
                        ├──────────────────────────────┤
                        │                              │
                        │  ┌─────────────────────┐    │
                        │  │  Dashboard (React)  │    │
                        │  │  (替换 Cockpit UI)  │    │
                        │  └─────────────────────┘    │
                        │                              │
                        │  ┌─────────────────────┐    │
                        │  │   Convex 后端       │    │
                        │  │   (替换 apphub)     │    │
                        │  └─────────────────────┘    │
                        │                              │
                        │  ┌─────────────────────┐    │
                        │  │   Nginx (反向代理)  │    │
                        │  └─────────────────────┘    │
                        │                              │
                        │  ┌─────────────────────┐    │
                        │  │   Cockpit-ws        │    │
                        │  │   Cockpit-bridge    │    │
                        │  └─────────────────────┘    │
                        │                              │
                        │  ┌─────────────────────┐    │
                        │  │   Gitea             │    │
                        │  │   Portainer         │    │
                        │  │   SSH/DBUS          │    │
                        │  │   /w9media          │    │
                        │  └─────────────────────┘    │
                        │                              │
                        └──────────────────────────────┘
                                    │
                                    ▼
                          /var/run/docker.sock
```

**关键点**：
- 所有服务运行在同一个容器中
- Dashboard 替换原 Cockpit Web UI
- Convex 替换 apphub 后端
- 容器内 Nginx 统一路由
- 端口 9090 保持不变

## Dockerfile 改造计划

### 需要修改的文件

```
docker/cockpit/
├── Dockerfile              # 移除 apphub，增加 Convex
├── supervisord.conf        # 删除 apphub/apphub-cron 服务，增加 convex 服务
├── entrypoint.sh          # 移除 apphub 初始化，增加 convex 初始化
└── nginx.conf             # 更新路由：/w9api/ → /baas/
```

### 1. Dockerfile 改造

**移除 apphub 相关**：
- Python 依赖（FastAPI, uvicorn 等）
- apphub 源码复制
- Python 虚拟环境

**增加 Convex**：
- Convex 二进制文件
- Convex 数据目录 `/convex/data`
- Dashboard 静态文件（Epic 7 产出）

### 2. supervisord.conf 改造

**删除服务**：
```ini
[program:apphub]          # 删除
[program:apphub-cron]     # 删除
```

**增加服务**：
```ini
[program:convex]
command=/usr/local/bin/convex-backend
directory=/convex
environment=CONVEX_CLOUD_ORIGIN="http://127.0.0.1:3210"
```

**保留服务**：
- dbus, sshd, cockpit-ws, nginx, portainer, gitea（全部保留）

### 3. nginx.conf 改造

**路由变更**：ï
```nginx
# 旧路由（删除）
location /w9api/ {
    proxy_pass http://127.0.0.1:8001/;
}

# 新路由（增加）
location /baas/ {
    proxy_pass http://127.0.0.1:3210/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# Dashboard（替换 /cockpit 路由）
location / {
    root /usr/share/cockpit/dashboard;
    try_files $uri /index.html;
}

# Cockpit WebSocket（保留）
location /cockpit/ {
    proxy_pass http://127.0.0.1:9090/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### 4. entrypoint.sh 改造

**删除**：
- apphub 数据库初始化
- Python 环境检查

**增加**：
- Convex 数据目录初始化
- Convex 配置文件生成

## 构建和测试

### 构建镜像

```bash
cd docker/cockpit
docker build -t websoft9/cockpit:dev .
```

### 测试运行

```bash
docker run -d \
  --name test-cockpit \
  -p 9090:9090 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  websoft9/cockpit:dev

# 检查服务状态
docker exec test-cockpit supervisorctl status

# 预期输出（没有 apphub，有 convex）
# dbus                       RUNNING
# sshd                       RUNNING
# cockpit-ws                 RUNNING
# nginx                      RUNNING
# portainer                  RUNNING
# gitea                      RUNNING
# convex                     RUNNING
```

### 验证功能

```bash
# 检查 Convex API
curl http://localhost:9090/baas/version

# 检查 Dashboard
curl http://localhost:9090/

# 检查 Cockpit WebSocket
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:9090/cockpit/socket
```

## 关键技术点

### 1. Convex 集成

- 使用 Convex 开源后端（test/convex/docker-compose.yml 已验证）
- Convex 端口：3210（API），3211（site proxy），6791（admin dashboard）
- 数据存储：`/convex/data`

### 2. Dashboard 集成

- Dashboard 构建产物：`dashboard/dist/`
- Nginx 配置：静态文件服务 + SPA 路由
- 替换原 Cockpit Web UI 但保留 cockpit-ws（用于 cockpit.js）

### 3. 路由变更

| 路径 | 目标 | 说明 |
|------|------|------|
| `/` | Dashboard 静态文件 | 新前端 |
| `/baas/` | Convex (127.0.0.1:3210) | 新后端 API |
| `/cockpit/` | cockpit-ws (127.0.0.1:9090) | 保留（cockpit.js 需要） |
| `/w9git/` | Gitea (127.0.0.1:3000) | 保留 |
| `/portainer/` | Portainer | 保留 |
| `/w9media/` | 静态媒体 | 保留 |

## 验收标准

### Dockerfile 改造

- [ ] 移除所有 apphub 相关代码和依赖
- [ ] 增加 Convex 二进制和配置
- [ ] 增加 Dashboard 静态文件

### supervisord 配置

- [ ] 删除 apphub 和 apphub-cron 服务配置
- [ ] 增加 convex 服务配置
- [ ] 所有原有服务（nginx, gitea, portainer 等）保持运行

### Nginx 配置

- [ ] `/baas/` 路由到 Convex
- [ ] `/` 路由到 Dashboard
- [ ] 删除 `/w9api/` 路由（旧 apphub）
- [ ] 其他路由保持不变

### 功能测试

- [ ] Dashboard 正常访问
- [ ] Convex API 可调用
- [ ] Cockpit.js 功能正常（docker spawn 等）
- [ ] Gitea、Portainer 正常访问
- [ ] /w9media 静态服务正常

### 兼容性

- [ ] 容器启动正常，所有服务运行
- [ ] 端口 9090 保持不变
- [ ] 数据卷挂载正确
- [ ] docker.sock 挂载正常

## 相关文档

- [test/convex/docker-compose.yml](../../test/convex/docker-compose.yml) - Convex 部署参考
- [docker/cockpit/Dockerfile](../../docker/cockpit/Dockerfile) - 当前 Dockerfile
- [docker/cockpit/supervisord.conf](../../docker/cockpit/supervisord.conf) - 当前 supervisord 配置
- [Epic 7: Dashboard](./epic7-dashboard.md) - Dashboard 开发规范

---

**更新记录**：
- 2026-02-10: 重新定义为单体容器架构，移除微服务分离方案
