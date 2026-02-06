# Stage 1: 构建阶段（下载 Gitea + Library + 构建 apphub）
FROM websoft9/cockpit-base:latest AS builder
WORKDIR /websoft9
ARG GITEA_VERSION=1.22.6
ARG WEBSOFT9_ARTIFACT="https://artifact.websoft9.com/release/websoft9"

# 下载外部组件（分步执行，显示进度）
RUN echo "Downloading Gitea ${GITEA_VERSION}..." && \
    curl -fL --progress-bar -o /gitea https://dl.gitea.com/gitea/${GITEA_VERSION}/gitea-${GITEA_VERSION}-linux-amd64 && \
    chmod +x /gitea && \
    echo "Gitea downloaded successfully"

RUN echo "Downloading Media files..." && \
    curl -fL --progress-bar -o media.zip ${WEBSOFT9_ARTIFACT}/plugin/media/media-latest.zip && \
    unzip -q media.zip && rm media.zip && \
    [ -d "media" ] || mv media-* media 2>/dev/null || true && \
    echo "Media files ready"

RUN echo "Downloading Library plugin..." && \
    curl -fL --progress-bar -o library.zip ${WEBSOFT9_ARTIFACT}/plugin/library/library-latest.zip && \
    unzip -q library.zip && rm library.zip && \
    [ -d "library" ] || mv library-* library 2>/dev/null || true && \
    echo "Library plugin ready"

# 复制本地源码并安装 Python 依赖
# 先复制 requirements.txt（利用缓存层）
COPY apphub/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --upgrade -r requirements.txt

# 再复制完整源码
COPY apphub ./apphub
COPY version.json ./version.json
RUN pip3 install --no-cache-dir --break-system-packages -e ./apphub && \
    mkdir -p apphub/swagger-ui && \
    rm -rf apphub/docs apphub/tests /root/.cache

# Stage 2: 从 Portainer 镜像复制二进制文件
FROM portainer/portainer-ce:2.21.5-alpine AS portainer

# Stage 3: 最终镜像
FROM websoft9/cockpit-base:latest

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="337"
LABEL description="Websoft9 Cockpit: Cockpit 337 + Portainer + Gitea + Apphub + Nginx"

# 下载并安装 Cockpit 插件
ARG WEBSOFT9_ARTIFACT="https://artifact.websoft9.com/release/websoft9"
RUN echo "Downloading Cockpit plugins..." && \
    curl -fsSL -o /tmp/version.json ${WEBSOFT9_ARTIFACT}/version.json && \
    for plugin in $(python3 -c "import json; data=json.load(open('/tmp/version.json')); print(' '.join(data['plugins'].keys()))"); do \
        echo "Installing Cockpit plugin: $plugin" && \
        mkdir -p /tmp/plugin-${plugin} && \
        curl -fL --progress-bar -o /tmp/${plugin}.zip ${WEBSOFT9_ARTIFACT}/plugin/${plugin}/${plugin}-latest.zip && \
        unzip -q /tmp/${plugin}.zip -d /tmp/plugin-${plugin} && \
        mv /tmp/plugin-${plugin}/*/${plugin} /usr/share/cockpit/ 2>/dev/null || mv /tmp/plugin-${plugin}/${plugin} /usr/share/cockpit/ && \
        rm -rf /tmp/${plugin}.zip /tmp/plugin-${plugin}; \
    done && \
    rm /tmp/version.json && \
    echo "All Cockpit plugins installed"

# 从 Portainer 镜像复制文件
COPY --from=portainer /portainer /portainer
COPY --from=portainer /public /public
# Portainer 默认查找 /docker-compose
COPY --from=portainer /docker-compose /docker-compose
COPY --from=portainer /docker /docker

# 从构建阶段复制文件
COPY --from=builder /gitea /usr/local/bin/gitea
COPY --from=builder /websoft9 /websoft9
COPY --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages

# 创建 Gitea 用户和目录
RUN useradd -r -m -d /var/lib/gitea -s /bin/bash git && \
    mkdir -p /var/lib/gitea/{custom,data,log} /etc/gitea && \
    chown -R git:git /var/lib/gitea /etc/gitea && \
    chmod 750 /var/lib/gitea /etc/gitea

# 配置 PCP 目录（pcp 用户已由 pcp-zeroconf 包创建）
RUN mkdir -p /var/log/pcp/pmlogger /var/lib/pcp/config/pmlogger && \
    chown -R pcp:pcp /var/log/pcp /var/lib/pcp && \
    chmod 755 /var/log/pcp/pmlogger

# 创建 docker cli plugins 目录和 compose 符号链接（保持兼容性）
RUN mkdir -p /usr/lib/docker/cli-plugins /root/.docker/cli-plugins && \
    ln -sf /docker-compose /usr/lib/docker/cli-plugins/docker-compose && \
    ln -sf /docker-compose /root/.docker/cli-plugins/docker-compose && \
    ln -sf /docker-compose /usr/local/bin/docker-compose

# 复制自定义配置
COPY docker/cockpit/cockpit.conf /etc/cockpit/cockpit.conf
COPY docker/cockpit/menu_override/*.override.json /etc/cockpit/
COPY docker/cockpit/nginx.conf /etc/nginx/nginx.conf
COPY docker/cockpit/gitea.ini /etc/gitea/app.ini

# 创建必要的目录和文件
RUN mkdir -p /etc/nginx/conf.d /var/log/nginx /data /portainer_data /var/lib/gitea/data && \
    echo 'LANG=en_US.UTF-8' > /etc/default/locale && \
    # 禁用 nginx 默认站点
    rm -f /etc/nginx/sites-enabled/default

# 配置 SSH（仅允许本地连接，用于 Cockpit 认证）
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# 创建默认管理员账户（容器内认证用，用于 Cockpit 认证）
RUN useradd -m -s /bin/bash -G sudo websoft9 && \
    echo "websoft9:websoft9" | chpasswd && \
    echo "websoft9 ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Supervisor 配置（覆盖系统默认配置）
COPY docker/cockpit/supervisord.conf /etc/supervisor/supervisord.conf
RUN cat /etc/supervisor/supervisord.conf | grep -c "\[program:gitea\]" || (echo "ERROR: supervisord.conf not copied correctly" && exit 1)

# 启动脚本
COPY docker/cockpit/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 只暴露 Nginx 端口（所有服务通过路径转发访问）
EXPOSE 80

# 数据卷
VOLUME ["/portainer_data", "/var/lib/gitea", "/websoft9/apphub/logs", "/websoft9/apphub/src/config"]

# 健康检查（通过 nginx）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
