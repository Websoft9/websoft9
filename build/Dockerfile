# ===========================
# Stage 1: 构建阶段
# ===========================
# 下载外部组件（Gitea、Media、Library）并构建 apphub
FROM websoft9-base:latest AS builder

WORKDIR /websoft9

# 构建参数（可在构建时通过 --build-arg 覆盖）
ARG GITEA_VERSION=1.22.6
ARG PORTAINER_VERSION=2.21.5
ARG WEBSOFT9_ARTIFACT="https://artifact.websoft9.com/release/websoft9"
ARG PIP_INDEX_URL="https://pypi.org/simple"

# 下载外部组件（分步执行以便调试，每层独立缓存）
# Layer 1: Gitea 二进制文件
RUN set -eux; \
    echo "==> Downloading Gitea ${GITEA_VERSION}..."; \
    curl -fsSL --retry 3 --connect-timeout 10 \
        -o /gitea https://dl.gitea.com/gitea/${GITEA_VERSION}/gitea-${GITEA_VERSION}-linux-amd64; \
    chmod +x /gitea; \
    /gitea --version; \
    echo "✓ Gitea downloaded successfully"

# Layer 2: Media 静态资源
RUN set -eux; \
    echo "==> Downloading Media files..."; \
    curl -fsSL --retry 3 -o media.zip ${WEBSOFT9_ARTIFACT}/plugin/media/media-latest.zip; \
    unzip -q media.zip; \
    rm media.zip; \
    [ -d "media" ] || mv media-* media 2>/dev/null || true; \
    echo "✓ Media files ready: $(du -sh media | cut -f1)"

# Layer 3: Library 插件
RUN set -eux; \
    echo "==> Downloading Library plugin..."; \
    curl -fsSL --retry 3 -o library.zip ${WEBSOFT9_ARTIFACT}/plugin/library/library-latest.zip; \
    unzip -q library.zip; \
    rm library.zip; \
    [ -d "library" ] || mv library-* library 2>/dev/null || true; \
    echo "✓ Library plugin ready: $(du -sh library | cut -f1)"

# Layer 4: Dashboard 静态文件（Epic 7 产出）
COPY dashboard/dist ./dashboard

# ===========================
# Stage 2: Convex 后端
# ===========================
FROM ghcr.io/get-convex/convex-backend:latest AS convex

# ===========================
# Stage 3: Portainer 二进制
# ===========================
FROM portainer/portainer-ce:2.21.5-alpine AS portainer

# ===========================
# Stage 4: 最终镜像
# ===========================
FROM websoft9-base:latest

# 元数据
LABEL maintainer="Websoft9<help@websoft9.com>" \
      org.opencontainers.image.title="Websoft9 Console" \
      org.opencontainers.image.description="All-in-one container: Cockpit + Portainer + Gitea + Convex BaaS" \
      org.opencontainers.image.vendor="Websoft9" \
      org.opencontainers.image.version="338" \
      org.opencontainers.image.url="https://www.websoft9.com" \
      org.opencontainers.image.source="https://github.com/websoft9/websoft9"

# 复制 Cockpit 插件（只复制构建产物）
RUN mkdir -p /usr/share/cockpit
COPY --chown=root:root plugins/cockpit-files/build /usr/share/cockpit/cockpit-files
COPY --chown=root:root plugins/services/build /usr/share/cockpit/services
COPY --chown=root:root plugins/store/build /usr/share/cockpit/store


# 复制 Convex 后端
COPY --from=convex --chown=root:root /convex/convex-local-backend /usr/local/bin/convex-backend

# 复制 Portainer 组件
COPY --from=portainer --chown=root:root /portainer /portainer
COPY --from=portainer --chown=root:root /public /public
COPY --from=portainer --chown=root:root /docker-compose /docker-compose
COPY --from=portainer --chown=root:root /docker /docker

# 复制构建产物（Gitea + Media + Library + Dashboard）
COPY --from=builder --chown=root:root /gitea /usr/local/bin/gitea
COPY --from=builder --chown=root:root /websoft9/media /websoft9/runtime/media
COPY --from=builder --chown=root:root /websoft9/library /websoft9/runtime/library
COPY --from=builder --chown=root:root /websoft9/dashboard /usr/share/nginx/html/dashboard

# 系统用户和目录配置（合并以减少层数）
RUN set -eux; \
    # 创建 Gitea 用户
    useradd -r -m -d /websoft9/data/gitea -s /bin/bash git; \
    # 创建统一目录结构
    mkdir -p /websoft9/data/baas \
             /websoft9/data/portainer \
             /websoft9/data/gitea/{custom,data,log,data/gitea-repositories,data/sessions,data/avatars,data/repo-avatars,data/attachments} \
             /websoft9/runtime/media \
             /websoft9/runtime/library \
             /etc/gitea; \
    chown -R git:git /websoft9/data/gitea /etc/gitea; \
    chmod 750 /websoft9/data/gitea /etc/gitea; \
    # 创建 docker-compose 符号链接（多位置兼容）
    mkdir -p /usr/lib/docker/cli-plugins /root/.docker/cli-plugins; \
    ln -sf /docker-compose /usr/lib/docker/cli-plugins/docker-compose; \
    ln -sf /docker-compose /root/.docker/cli-plugins/docker-compose; \
    ln -sf /docker-compose /usr/local/bin/docker-compose; \
    # 验证链接
    ls -lh /usr/local/bin/docker-compose

# 复制自定义配置
COPY build/cockpit.conf /etc/cockpit/cockpit.conf
COPY build/menu_override/*.override.json /etc/cockpit/
COPY build/nginx.conf /etc/nginx/nginx.conf
COPY build/gitea.ini /etc/gitea/app.ini

# 服务配置（合并多个配置步骤）
RUN set -eux; \
    # 创建必要的运行时目录
    mkdir -p /etc/nginx/conf.d /var/log/nginx; \
    # 设置语言环境
    echo 'LANG=en_US.UTF-8' > /etc/default/locale; \
    # 禁用 nginx 默认站点
    rm -f /etc/nginx/sites-enabled/default; \
    # 配置 SSH (仅用于 Cockpit 本地认证)
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config; \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config; \
    sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 127.0.0.1/' /etc/ssh/sshd_config; \
    ssh-keygen -A; \
    # 创建默认管理员账户
    useradd -m -s /bin/bash -G sudo websoft9; \
    echo "websoft9:websoft9" | chpasswd; \
    echo "websoft9 ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/websoft9; \
    chmod 0440 /etc/sudoers.d/websoft9

# 环境变量：运行时配置
ENV ADMIN_USER=websoft9 \
    ADMIN_PASSWORD=websoft9 \
    TZ=UTC \
    LANG=en_US.UTF-8

# 复制配置文件和脚本
COPY --chmod=644 build/supervisord.conf /etc/supervisor/supervisord.conf
COPY --chmod=755 build/entrypoint.sh /entrypoint.sh

# 验证关键配置
RUN set -eux; \
    grep -q "\[program:gitea\]" /etc/supervisor/supervisord.conf || { echo "ERROR: supervisord.conf validation failed"; exit 1; }; \
    test -x /entrypoint.sh || { echo "ERROR: entrypoint.sh not executable"; exit 1; }; \
    test -x /usr/local/bin/gitea || { echo "ERROR: gitea binary not found"; exit 1; }; \
    test -x /usr/local/bin/convex-backend || { echo "ERROR: convex-backend not installed"; exit 1; }; \
    nginx -t || { echo "ERROR: nginx config validation failed"; exit 1; }

# 只暴露 Nginx 端口（所有服务通过路径转发访问）
EXPOSE 80

# 数据卷（统一持久化目录）
VOLUME ["/websoft9/data"]

# 健康检查（检查关键服务）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD supervisorctl -c /etc/supervisor/supervisord.conf status | grep -E 'RUNNING|STARTING' > /dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
