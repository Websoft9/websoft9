# Stage 1: 从 Portainer 镜像复制二进制文件
FROM portainer/portainer-ce:2.21.5-alpine AS portainer

# Stage 2: 下载 Gitea
FROM debian:bookworm-slim AS gitea-builder
ARG GITEA_VERSION=1.22.6
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL -o /gitea https://dl.gitea.com/gitea/${GITEA_VERSION}/gitea-${GITEA_VERSION}-linux-amd64 && \
    chmod +x /gitea

# Stage 3: 构建 apphub
FROM python:3.10-slim-bullseye AS apphub-builder
WORKDIR /websoft9
ARG MEDIA_VERSION="0.1.1"
ARG LIBRARY_VERSION="0.7.3"
ARG WEBSOFT9_REPO="https://github.com/Websoft9/websoft9"
ARG SOURCE_GITHUB_PAGES="https://websoft9.github.io/websoft9"
ARG WEBSOFT9_ARTIFACT="https://artifact.websoft9.com/release/websoft9"
ARG LIBRARY_REPO="https://github.com/Websoft9/docker-library"

RUN apt update && apt install -y --no-install-recommends curl git jq wget unzip zip && \
    curl -fsSL -o media.zip ${WEBSOFT9_ARTIFACT}/plugin/media/media-latest.zip && \
    git clone --depth=1 $LIBRARY_REPO && mv docker-library w9library && rm -rf w9library/.github && \
    unzip media.zip && rm -rf media.zip && mv media* w9media && \
    git clone --depth=1 https://github.com/swagger-api/swagger-ui.git && \
    wget https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js && \
    cp redoc.standalone.js swagger-ui/dist && \
    git clone --depth=1 $WEBSOFT9_REPO ./w9source && \
    cp -r ./w9media ./media && cp -r ./w9library ./library && \
    cp -r ./w9source/apphub ./apphub && \
    cp -r ./swagger-ui/dist ./apphub/swagger-ui && \
    cp -r ./w9source/apphub/src/config ./config && \
    curl -o /websoft9/version.json $SOURCE_GITHUB_PAGES/version.json && \
    pip install --no-cache-dir --upgrade -r apphub/requirements.txt && \
    pip install -e ./apphub && \
    rm -rf apphub/docs apphub/tests library.zip media.zip redoc.standalone.js swagger-ui w9library w9media w9source && \
    apt clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Stage 4: 最终镜像
FROM debian:bookworm-slim

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="337"
LABEL description="Websoft9 Console: Cockpit 337 + Portainer + Gitea + Apphub + Nginx"

# 安装最小化 Cockpit（使用 backports 源获取最新版本）
# 参考: https://cockpit-project.org/running.html#debian
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    . /etc/os-release && \
    echo "deb http://deb.debian.org/debian ${VERSION_CODENAME}-backports main" > /etc/apt/sources.list.d/backports.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends -t ${VERSION_CODENAME}-backports \
        cockpit \
        cockpit-ws \
        cockpit-bridge \
    && \
    # 安装 supervisor、SSH、nginx、git、Python 和必要工具
    apt-get install -y --no-install-recommends \
        supervisor \
        openssh-server \
        nginx-light \
        git \
        sudo \
        procps \
        dbus \
        python3 \
        python3-pip \
        cron \
        iproute2 \
        rsync \
    && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 从 Portainer 镜像复制文件
COPY --from=portainer /portainer /portainer
COPY --from=portainer /public /public
# Portainer 默认查找 /docker-compose
COPY --from=portainer /docker-compose /docker-compose
COPY --from=portainer /docker /docker

# 从 Gitea 构建阶段复制文件
COPY --from=gitea-builder /gitea /usr/local/bin/gitea

# 从 apphub 构建阶段复制文件
COPY --from=apphub-builder /websoft9 /websoft9
COPY --from=apphub-builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# 创建 Gitea 用户和目录
RUN useradd -r -m -d /var/lib/gitea -s /bin/bash git && \
    mkdir -p /var/lib/gitea/{custom,data,log} /etc/gitea && \
    chown -R git:git /var/lib/gitea /etc/gitea && \
    chmod 750 /var/lib/gitea /etc/gitea

# 创建 docker cli plugins 目录和 compose 符号链接（保持兼容性）
RUN mkdir -p /usr/lib/docker/cli-plugins /root/.docker/cli-plugins && \
    ln -sf /docker-compose /usr/lib/docker/cli-plugins/docker-compose && \
    ln -sf /docker-compose /root/.docker/cli-plugins/docker-compose && \
    ln -sf /docker-compose /usr/local/bin/docker-compose

# 复制自定义配置
COPY cockpit.conf /etc/cockpit/cockpit.conf
COPY menu_override/*.override.json /usr/share/cockpit/shell/
COPY nginx.conf /etc/nginx/nginx.conf
COPY gitea.ini /etc/gitea/app.ini
COPY apphub-supervisord.conf /etc/supervisor/conf.d/apphub.conf

# 创建必要的目录和文件
RUN mkdir -p /etc/cockpit/ws-certs.d /etc/default /run/dbus /run/sshd /etc/nginx/conf.d /var/log/nginx /data /portainer_data /var/lib/gitea/data && \
    echo 'LANG=en_US.UTF-8' > /etc/default/locale && \
    # 禁用 nginx 默认站点
    rm -f /etc/nginx/sites-enabled/default

# 配置 SSH（仅允许本地连接，用于 Cockpit 认证）
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# 创建默认管理员账户（容器内认证用）
RUN useradd -m -s /bin/bash -G sudo websoft9 && \
    echo "websoft9:websoft9" | chpasswd && \
    echo "websoft9 ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/cockpit.conf

# 启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露 Nginx、Cockpit、Portainer、Gitea 和 Apphub 端口
EXPOSE 80 9090 9000 3000 8080 8081

# 数据卷
VOLUME ["/portainer_data", "/var/lib/gitea", "/websoft9/apphub/logs", "/websoft9/apphub/src/config"]

# 健康检查（通过 nginx）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
