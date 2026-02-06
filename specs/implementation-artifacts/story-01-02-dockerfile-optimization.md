# Story 1.2: Dockerfile 优化与 Cockpit 集成

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P0 (架构变更)  
**状态**: Not Started

## User Story
作为 DevOps 工程师，我想要将 Cockpit 与 apphub 构建在同一个镜像中，这样可以简化部署、减少依赖宿主机安装，实现完全容器化。

## 架构变更说明
**当前架构**: Cockpit 通过 `install_cockpit.sh` 直接安装在宿主机  
**目标架构**: 分层镜像架构 - Cockpit 基础镜像 + apphub 应用镜像

### 镜像分层策略
```
websoft9dev/cockpit-base:297      (基础镜像，独立维护)
    ↓ FROM
websoft9dev/apphub:0.2.6          (应用镜像，基于 cockpit-base)
```

**优势**:
- ✅ 完全容器化，无需宿主机安装 Cockpit
- ✅ **Cockpit 独立维护**：更新 Cockpit 无需重新构建 apphub
- ✅ **构建缓存优化**：Cockpit 层缓存，apphub 构建更快
- ✅ **版本解耦**：Cockpit 和 apphub 可独立发版
- ✅ **多项目复用**：其他项目可复用 cockpit-base 镜像
- ✅ 便于开发测试（本地 Docker 即可运行完整环境）

**挑战**:
- ⚠️ 容器内需创建默认用户（websoft9/websoft9）
- ⚠️ Cockpit 需要访问宿主机 systemd（需挂载 socket）
- ⚠️ 需要维护两个 Dockerfile（cockpit-base + apphub）
- ⚠️ 需要特权模式或额外权限

## 验收标准

### 核心功能
- [ ] **cockpit-base 镜像**: 独立的 Cockpit 基础镜像（websoft9dev/cockpit-base）
- [ ] **apphub 镜像**: 基于 cockpit-base 构建，包含 FastAPI backend
- [ ] **Cockpit 正常运行**: WebSocket、Web Terminal、容器内用户认证可用
- [ ] **默认用户**: 容器内创建 websoft9/websoft9 默认管理员账户
- [ ] **FastAPI 正常运行**: API 端点响应正常
- [ ] **端口暴露**: Cockpit (9000) 和 apphub API (8080) 正确暴露
- [ ] **systemd 交互**: Cockpit 可管理宿主机服务（通过 socket 挂载）
- [ ] **文件系统访问**: Cockpit 可访问必要的宿主机路径

### 镜像优化目标
- [ ] **cockpit-base 镜像**:
  - 基于 `debian:bullseye-slim`
  - 包含 Cockpit 完整安装（ws, system, bridge, pcp）
  - 包含自定义配置（cockpit.conf, menu_override）
  - 镜像大小 < 300MB
  - 版本标签与 Cockpit 版本一致（如 `297`）
- [ ] **apphub 镜像**:
  - 基于 `websoft9dev/cockpit-base:$COCKPIT_VERSION`
  - Multi-stage build（Python 编译层 + 运行层）
  - 镜像大小 < 600MB（含 Cockpit 层）
  - 构建时间 < 8 分钟（利用 Cockpit 层缓存）
- [ ] **健康检查**: Cockpit 和 apphub 双重健康检查
- [ ] **启动顺序**: Supervisor 管理 Cockpit-ws 和 apphub 进程

### 其他组件优化
- [ ] **deployment**: 文档说明定制原因
- [ ] **git**: 配置注入优化，启动脚本健壮性
- [ ] **proxy**: SSL/Nginx 配置注入优化

## 技术细节

### 镜像 1: Cockpit 基础镜像
**文件**: `docker/cockpit/Dockerfile`

```dockerfile
FROM debian:bullseye-slim

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="297"
LABEL description="Cockpit base image for Websoft9 projects"

# 安装 Cockpit 及其组件
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    cockpit \
    cockpit-ws \
    cockpit-system \
    cockpit-bridge \
    cockpit-pcp \
    openssh-client \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 复制自定义配置
COPY cockpit.conf /etc/cockpit/cockpit.conf
COPY menu_override/shell.override.json /usr/share/cockpit/shell/override.json

# 创建必要的目录
RUN mkdir -p /etc/cockpit/ws-certs.d

# 暴露 Cockpit 端口
EXPOSE 9090

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9090/ || exit 1

# Cockpit-ws 启动命令（由上层镜像的 supervisor 管理）
CMD ["/usr/libexec/cockpit-ws", "--no-tls"]
```

**构建命令**:
```bash
cd docker/cockpit
docker build -t websoft9dev/cockpit-base:297 .
docker push websoft9dev/cockpit-base:297
```

---

### 镜像 2: apphub 应用镜像
**文件**: `docker/apphub/Dockerfile`

```dockerfile
# Stage 1: Python 构建层
FROM python:3.10-slim-bullseye AS builder

ARG MEDIA_VERSION="0.1.1"
ARG LIBRARY_VERSION="0.7.3"
ARG WEBSOFT9_REPO="https://github.com/Websoft9/websoft9"

WORKDIR /build

# 下载并构建 apphub
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget unzip && \
    git clone --depth=1 $WEBSOFT9_REPO ./w9source && \
    # ... 构建逻辑（参考现有 Dockerfile）... \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Stage 2: 最终运行镜像（基于 cockpit-base）
FROM websoft9dev/cockpit-base:297

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.2.6"

# 安装 Python 运行时和 supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    supervisor \
    curl \
    iproute2 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 复制构建产物
COPY --from=builder /build/websoft9 /websoft9

WORKDIR /websoft9

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -r apphub/requirements.txt && \
    pip3 install -e ./apphub

# 复制 supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/websoft9.conf

# 暴露端口
EXPOSE 9090 8080

# 健康检查（检查双进程）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9090/ && curl -f http://localhost:8080/api/health || exit 1

# 启动 supervisor（管理 Cockpit + apphub）
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
```

**构建命令**:
```bash
cd docker/apphub
docker build -t websoft9dev/apphub:0.2.6 .
docker push websoft9dev/apphub:0.2.6
---

### Docker Compose 配置变更

```yaml
apphub:
  image: websoft9dev/apphub:$APPHUB_VERSION
  container_name: websoft9-apphub
  restart: always
  privileged: true  # Cockpit 需要特权访问 systemd
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - /run/systemd:/run/systemd:ro  # systemd socket（只读）
    - /etc/systemd:/etc/systemd:ro  # systemd 配置（只读）
    - apphub_config:/websoft9/apphub/src/config
    - apphub_logs:/websoft9/apphub/logs
  ports:
    - "9090:9090"  # Cockpit
    - "8080:8080"  # apphub API
  environment:
    - COCKPIT_VERSION=297
  depends_on:
    - deployment
    - git
    - proxy
  labels:
    - "owner=websoft9"
    - "com.docker.compose.w9_http.port=8080"
```

**.env 文件新增变量**:
```bash
APPHUB_VERSION=0.2.6
COCKPIT_VERSION=297
```

### Supervisor 配置

```ini
[supervisord]
nodaemon=true

[program:cockpit-ws]
---

### 涉及文件

**新建文件**:
- `docker/cockpit/Dockerfile` - Cockpit 基础镜像
- `docker/cockpit/cockpit.conf` - Cockpit 配置（从 `cockpit/` 复制）
- `docker/cockpit/menu_override/` - 菜单覆盖（从 `cockpit/menu_override/` 复制）
- `docker/apphub/supervisord.conf` - Supervisor 配置

**修改文件**:
- `docker/apphub/Dockerfile` - 改为基于 `cockpit-base` 构建
- `docker/docker-compose.yml` - 修改 apphub 服务配置
- `docker/docker-compose-dev.yml` - 同步修改开发环境配置
- `docker/.env` - 新增 `COCKPIT_VERSION` 变量

**废弃/保留文件**:
- `install/install_cockpit.sh` - 标记为废弃或仅用于非容器化安装
- `cockpit/` 目录 - 保留作为配置源，由 Dockerfile 复制

---

### GitHub Actions 构建流程

**两阶段构建**:

1. **Cockpit 基础镜像构建** (手动或定期触发)
```yaml
# .github/workflows/build-cockpit-base.yml
name第一阶段：Cockpit 基础镜像测试
```bash
# 1. 构建 cockpit-base 镜像
cd docker/cockpit
docker build -t websoft9dev/cockpit-base:297 .

# 2. 检查镜像大小
docker images | grep cockpit-base
# 目标: < 300MB

# 3. 测试 Cockpit 基础功能
docker run -d --name test-cockpit \
  --privileged \
  -v /run/systemd:/run/systemd:ro \
  -p 9090:9090 \
  websoft9dev/cockpit-base:297

# 4. 验证 Cockpit 启动
curl http://localhost:9090
# 预期: Cockpit 登录页面

# 5. 验证健康检查
docker inspect --format='{{json .State.Health}}' test-cockpit

# 6. 清理
docker stop test-cockpit && docker rm test-cockpit
```

### 第二阶段：apphub 应用镜像测试
```bash
# 1. 构建 apphub 镜像（依赖 cockpit-base）
cd docker/apphub
docker build -t websoft9dev/apphub:0.2.6 .

# 2. 检查镜像大小
docker images | grep apphub
# 目标: < 600MB (含 Cockpit 层)

# 3. 检查层结构（验证 cockpit-base 层缓存）
docker history websoft9dev/apphub:0.2.6 | head -20

# 4. 启动完整容器
docker run -d --name test-apphub \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /run/systemd:/run/systemd:ro \
  -p 9090:9090 -p 8080:8080 \
  websoft9dev/apphub:0.2.6

# 5. 验证双进程运行
docker exec test-apphub supervisorctl status
# 预期:
# cockpit-ws    RUNNING   pid 12, uptime 0:01:23
# apphub        RUNNING   pid 34, uptime 0:01:20

# 6. 测试 Cockpit
curl http://localhost:9090
# 预期: Cockpit 登录页面

# 7. 测试 apphub API
curl http://localhost:8080/api/health
# 预期: {"status": "ok"}

# 8. 测试健康检查
docker inspect --format='{{json .State.Health}}' test-apphub
# 预期: "Status": "healthy"

# 9. 测试 Cockpit Web Terminal
# 浏览器访问 http://localhost:9090 → 登录 → Terminal 功能

# 10. 清理
docker stop test-apphub && docker rm test-apphub
```

### 第三阶段：Docker Compose 集成测试
```bash
# 1. 完整环境启动
cd docker
docker-compose -f docker-compose-dev.yml up -d

# 2. 验证所有服务
docker-compose ps
docker ps | grep websoft9

# 3. 验证 apphub 容器
docker logs websoft9-apphub | tail -20

# 4. 验证 Cockpit → FastAPI 通信
curl -H "x-api-key: test-key" http://localhost:8080/api/apps

# 5. 验证 Cockpit → Docker 交互
# 浏览器登录 Cockpit → 管理容器

# 6. 性能测试
ab -n 1000 -c 10 http://localhost:8080/api/health
```

### 第四阶段：构建性能测试
```bash
# 测试 Cockpit 层缓存效果
# 1. 首次构建 apphub（无缓存）
time docker build --no-cache -t test-apphub docker/apphub
# 记录时间 T1

# 2. 修改 apphub 代码后重新构建
echo "# test" >> apphub/src/main.py
time docker build -t test-apphub docker/apphub
# 记录时间 T2

# 预期: T2 < T1 * 0.5（Cockpit 层缓存生效）
```bash
# 启动容器
docker run -d --name test-apphub-cockpit \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /run/systemd:/run/systemd \
  -p 9000:9000 -p 8080:8080 \
  test-apphub-cockpit

# 测试 Cockpit
curl http://localhost:9000
# 预期: Cockpit 登录页面

# 测试 apphub API
curl http://localhost:8080/api/health
# 预期: {"status": "ok"}

# 测试健康检查
docker inspect --format='{{json .State.Health}}' test-apphub-cockpit

# 进入容器验证进程
docker exec -it test-apphub-cockpit supervisorctl status
# 预期: cockpit-ws RUNNING, apphub RUNNING

# 测试 Cockpit Web Terminal
# 浏览器访问 http://localhost:9000 → Terminal 功能
```

### 集成测试
```bash
# 完整环境测试
cd docker
docker-compose -f docker-compose-dev.yml up -d

# 验证所有服务
docker ps | grep websoft9

# 验证 Cockpit 到 FastAPI 的通信
curl -H "x-api-key: test-key" http://localhost:8080/api/apps
```

## 回滚方案
如果集成失败，可快速回退到当前架构：
1. 恢复使用 `install_cockpit.sh` 安装宿主机 Cockpit
2. 恢复原 `docker/apphub/Dockerfile`
3. 恢复原 `docker-compose.yml` 配置

## 迁移注意事项
- 现有用户升级时需要先卸载宿主机 Cockpit
- 需要更新文档和安装脚本
- 需要通知用户端口映射变更（如果有）
