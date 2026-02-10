#!/bin/bash
# Websoft9 Console Entrypoint
# 容器启动脚本，负责环境初始化和服务启动

set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时报错

# ===============================
# 环境变量默认值
# ===============================
export ADMIN_USER="${ADMIN_USER:-websoft9}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-websoft9}"
export SUPERVISOR_PASSWORD="${SUPERVISOR_PASSWORD:-admin}"
export TZ="${TZ:-UTC}"

# 日志函数
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
}

log_warn() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $*"
}

# ===============================
# 管理员用户配置
# ===============================
log_info "Configuring admin user: $ADMIN_USER"

# 确保管理员用户存在并更新密码
if ! id "$ADMIN_USER" &>/dev/null; then
    log_info "Creating admin user: $ADMIN_USER"
    useradd -m -s /bin/bash -G sudo "$ADMIN_USER" || {
        log_error "Failed to create user $ADMIN_USER"
        exit 1
    }
fi

echo "$ADMIN_USER:$ADMIN_PASSWORD" | chpasswd || {
    log_error "Failed to set password for $ADMIN_USER"
    exit 1
}

# 配置 sudo 权限
echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/$ADMIN_USER > /dev/null
chmod 0440 /etc/sudoers.d/$ADMIN_USER

log_info "Admin user configured successfully"

# ===============================
# 创建运行时目录
# ===============================
log_info "Creating runtime directories..."

mkdir -p \
    /run/dbus \
    /run/cockpit \
    /run/sshd \
    /var/log/supervisor \
    /var/log/nginx \
    /data/compose \
    /websoft9/data/baas \
    /websoft9/data/portainer \
    /websoft9/data/gitea/{custom,data,log,data/gitea-repositories,data/sessions,data/avatars,data/repo-avatars,data/attachments} \
    /websoft9/runtime/media \
    /websoft9/runtime/library \
    /home/$ADMIN_USER/logs || {
        log_error "Failed to create runtime directories"
        exit 1
    }

# 设置正确的权限
chown -R "$ADMIN_USER:$ADMIN_USER" /home/$ADMIN_USER/logs || log_warn "Failed to set ownership for logs"
chmod -R 755 /home/$ADMIN_USER/logs || log_warn "Failed to set permissions for logs"
chown -R git:git /websoft9/data/gitea /etc/gitea 2>/dev/null || log_warn "Failed to set ownership for Gitea"
chmod -R 755 /websoft9/data/baas || log_warn "Failed to set permissions for Convex data"

# 清理旧的 PID 文件
rm -f /run/dbus/pid /var/run/dbus/pid /var/run/supervisord.pid 2>/dev/null || true

log_info "Runtime directories created"

# ===============================
# 运行服务初始化脚本
# ===============================
INIT_SCRIPT="$(dirname "$0")/init-services.sh"
if [ -f "$INIT_SCRIPT" ]; then
    log_info "Running service initialization script..."
    /bin/bash "$INIT_SCRIPT" || log_warn "Service initialization had errors (non-fatal)"
else
    log_warn "Service initialization script not found: $INIT_SCRIPT"
fi

# ===============================
# Gitea 初始化
# ===============================
if [ ! -f /websoft9/data/gitea/.initialized ]; then
    log_info "Scheduling Gitea admin user initialization..."
    (
        sleep 15  # 等待 Gitea 服务启动
        log_info "Creating Gitea admin user: $ADMIN_USER"
        su -c "/usr/local/bin/gitea admin user create \
            --admin \
            --username '$ADMIN_USER' \
            --password '$ADMIN_PASSWORD' \
            --email admin@websoft9.com \
            --config /etc/gitea/app.ini 2>/dev/null || true" git
        
        if [ $? -eq 0 ]; then
            touch /websoft9/data/gitea/.initialized
            log_info "Gitea admin user initialized successfully"
        else
            log_warn "Gitea admin user initialization may have failed (user might already exist)"
        fi
    ) &
else
    log_info "Gitea already initialized, skipping"
fi

# ===============================
# 系统服务配置
# ===============================
log_info "Configuring system services..."

# 确保 dbus 系统目录存在
if [ ! -d /var/run/dbus ]; then
    mkdir -p /var/run/dbus
fi

# 生成 dbus machine-id (如果不存在)
if [ ! -f /var/lib/dbus/machine-id ]; then
    log_info "Generating dbus machine-id..."
    dbus-uuidgen > /var/lib/dbus/machine-id || log_warn "Failed to generate dbus machine-id"
fi

# 确保 SSH host keys 存在
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    log_info "Generating SSH host keys..."
    ssh-keygen -A || log_warn "Failed to generate SSH host keys"
fi

# 确保 cockpit 配置目录权限正确
if [ -d /etc/cockpit ]; then
    chmod 755 /etc/cockpit
    chmod 644 /etc/cockpit/cockpit.conf 2>/dev/null || true
fi

log_info "System services configured"

# ===============================
# 配置验证
# ===============================
log_info "Validating configurations..."

# 测试 nginx 配置
if ! nginx -t 2>/dev/null; then
    log_error "Nginx configuration validation failed!"
    nginx -t  # 显示详细错误
    exit 1
fi

# 验证关键文件存在
for file in /usr/local/bin/gitea /portainer /usr/local/bin/convex-backend; do
    if [ ! -f "$file" ]; then
        log_error "Critical file not found: $file"
        exit 1
    fi
done

log_info "All configurations validated successfully"

# ===============================
# 启动信息
# ===============================
echo ""
echo "========================================="
echo "  Websoft9 Console Starting"
echo "========================================="
echo "Admin User:  $ADMIN_USER"
echo "Admin Pass:  ******** (hidden)"
echo ""
echo "Service URLs (internal):"
echo "  Dashboard: http://localhost/"
echo "  Portainer: http://localhost/w9deployment/"
echo "  Gitea:     http://localhost/w9git/"
echo "  Convex:    http://localhost/baas/"
echo "  Media:     http://localhost/w9media/"
echo "  Health:    http://localhost/health"
echo ""
echo "Environment:"
echo "  Timezone:  $TZ"
echo "  Language:  ${LANG:-en_US.UTF-8}"
echo "========================================="
echo ""

# 后台运行连接测试
TEST_SCRIPT="$(dirname "$0")/test-connections.sh"
if [ -f "$TEST_SCRIPT" ]; then
    log_info "Scheduling connection tests..."
    (sleep 30 && /bin/bash "$TEST_SCRIPT") &
else
    log_warn "Connection test script not found: $TEST_SCRIPT"
fi

# ===============================
# 启动主进程
# ===============================
log_info "Starting supervisord..."
exec "$@"
