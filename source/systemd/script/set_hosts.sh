#!/bin/bash
# Define PATH
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
# Export PATH

set -e

# 容器名称
container_name="websoft9-apphub"

# 最大尝试次数
max_attempts=6

# 获取容器的内网IP
attempt=0
while [ $attempt -lt $max_attempts ]; do
    container_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $container_name)

    if [ -n "$container_ip" ]; then
        break
    fi

    attempt=$(( $attempt + 1 ))
    sleep 5
done

# 检查获取IP是否成功
if [ -z "$container_ip" ]; then
    echo "Failed to get IP for container $container_name after $max_attempts attempts"
    exit 1
fi

# 检查 /etc/hosts 文件中是否已经存在一个条目与容器名称相同
if grep -q $container_name /etc/hosts; then
    # 如果存在，使用 sed 命令更新这个条目
    sed -i "/$container_name/d" /etc/hosts
    echo "$container_ip $container_name" | tee -a /etc/hosts > /dev/null
    echo "Container $container_name IP updated to $container_ip in /etc/hosts"
else
    # 如果不存在，添加一个新的条目
    echo "$container_ip $container_name" | tee -a /etc/hosts > /dev/null
    echo "Container $container_name IP $container_ip added to /etc/hosts"
fi
