#!/bin/bash
set -e

# 使用环境变量设置管理员账户（默认值在 Dockerfile 中定义）
ADMIN_USER=${ADMIN_USER:-websoft9}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-websoft9}

# 确保管理员用户存在并更新密码
if ! id "$ADMIN_USER" &>/dev/null; then
    echo "Creating admin user: $ADMIN_USER"
    useradd -m -s /bin/bash -G sudo "$ADMIN_USER"
fi
echo "$ADMIN_USER:$ADMIN_PASSWORD" | chpasswd
echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/$ADMIN_USER > /dev/null
chmod 0440 /etc/sudoers.d/$ADMIN_USER

# 创建必要的运行时目录
mkdir -p /run/dbus /run/cockpit /run/sshd /var/log/supervisor /var/log/nginx /portainer_data /data/compose
mkdir -p /var/lib/gitea/{custom,data,log,data/gitea-repositories,data/sessions,data/avatars,data/repo-avatars,data/attachments}
mkdir -p /websoft9/apphub/logs /websoft9/apphub/src/config
mkdir -p /home/$ADMIN_USER/logs

# 确保日志目录权限正确（使用管理员用户）
chown -R "$ADMIN_USER:$ADMIN_USER" /websoft9/apphub/logs /home/$ADMIN_USER/logs
chmod -R 755 /websoft9/apphub/logs /home/$ADMIN_USER/logs

rm -f /run/dbus/pid /var/run/dbus/pid

# Run service initialization script
echo "Running service initialization..."
/bin/bash "$(dirname "$0")/init-services.sh" || echo "Warning: Service initialization had errors (non-fatal)"

# Set Gitea directory ownership
chown -R git:git /var/lib/gitea /etc/gitea 2>/dev/null || true

# 初始化 Gitea 管理员账户（仅首次运行）
if [ ! -f /var/lib/gitea/.initialized ]; then
    echo "Initializing Gitea admin user: $ADMIN_USER"
    # 等待 Gitea 数据库初始化（在后台启动后）
    (sleep 15 && su -c "/usr/local/bin/gitea admin user create --admin --username $ADMIN_USER --password $ADMIN_PASSWORD --email admin@websoft9.com --config /etc/gitea/app.ini 2>/dev/null || true" git && touch /var/lib/gitea/.initialized) &
fi

# 确保 dbus 系统目录存在
if [ ! -d /var/run/dbus ]; then
    mkdir -p /var/run/dbus
fi

# 生成 dbus machine-id (如果不存在)
if [ ! -f /var/lib/dbus/machine-id ]; then
    dbus-uuidgen > /var/lib/dbus/machine-id
fi

# 确保 SSH host keys 存在
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    ssh-keygen -A
fi

# 确保 cockpit 配置目录权限正确
chmod 755 /etc/cockpit
chmod 644 /etc/cockpit/cockpit.conf 2>/dev/null || true

# 测试 nginx 配置
nginx -t

echo "=== Websoft9 Console Starting ==="
echo "Cockpit:   http://localhost/ ($ADMIN_USER/$ADMIN_PASSWORD)"
echo "Portainer: http://localhost/w9deployment/"
echo "Gitea:     http://localhost/w9git/"
echo "Apphub:    http://localhost/w9api/"
echo "Media:     http://localhost/w9media/"
echo "Health:    http://localhost/health"
echo "=================================="

# Run connection tests in background (after supervisord starts services)
(sleep 30 && /bin/bash "$(dirname "$0")/test-connections.sh") &

exec "$@"
