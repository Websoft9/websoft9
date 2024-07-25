#!/bin/bash

# 设置密码目录
credential_path="/data/credential"

# 检查是否已经存在密码文件
if [ ! -f "$credential_path" ]; then
  # 设置用户名和生成随机密码
  INITIAL_ADMIN_EMAIL="admin@mydomain.com"
  INITIAL_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+' | cut -c1-16)

  # 设置环境变量
  export INITIAL_ADMIN_EMAIL
  export INITIAL_ADMIN_PASSWORD

  # 写入密码文件
  mkdir -p "$(dirname "$credential_path")"
  credential_json="{\"username\":\"$INITIAL_ADMIN_EMAIL\",\"password\":\"$INITIAL_ADMIN_PASSWORD\"}"
  echo "$credential_json" > "$credential_path"
else
  # 从密码文件中读取用户名和密码
  INITIAL_ADMIN_EMAIL=$(jq -r '.username' "$credential_path")
  INITIAL_ADMIN_PASSWORD=$(jq -r '.password' "$credential_path")

  # 设置环境变量
  export INITIAL_ADMIN_EMAIL
  export INITIAL_ADMIN_PASSWORD
fi

# 启动 Nginx
exec /init
