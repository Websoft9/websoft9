#!/bin/bash
set -e

# 创建必要的运行时目录
mkdir -p /run/dbus /run/cockpit /run/sshd /var/log/supervisor /var/log/nginx /portainer_data /data/compose
mkdir -p /var/lib/gitea/{custom,data,log,data/gitea-repositories,data/sessions,data/avatars,data/repo-avatars,data/attachments}
mkdir -p /websoft9/apphub/logs /websoft9/apphub/src/config
rm -f /run/dbus/pid /var/run/dbus/pid

# 设置 Gitea 目录权限
chown -R git:git /var/lib/gitea /etc/gitea 2>/dev/null || true

# 初始化 Gitea 管理员账户（仅首次运行）
if [ ! -f /var/lib/gitea/.initialized ]; then
    echo "Initializing Gitea admin user..."
    # 等待 Gitea 数据库初始化（在后台启动后）
    (sleep 15 && su -c '/usr/local/bin/gitea admin user create --admin --username websoft9 --password websoft9 --email admin@websoft9.com --config /etc/gitea/app.ini 2>/dev/null || true' git && touch /var/lib/gitea/.initialized) &
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
echo "Cockpit:   http://localhost/ (websoft9/websoft9)"
echo "Portainer: http://localhost/w9deployment/"
echo "Gitea:     http://localhost/w9git/"
echo "Apphub:    http://localhost/w9api/"
echo "Media:     http://localhost/w9media/"
echo "Health:    http://localhost/health"
echo "=================================="

exec "$@"
