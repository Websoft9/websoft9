#!/bin/bash

# Create admin credential by admin cli
su -c '
    gitea admin user create --admin --username websoft9 --random-password --email help@websoft9.com > /tmp/credential
' git

# Read credential from tmp
username=$(grep -o "New user '[^']*" /tmp/credential | sed "s/New user '//")
password=$(grep -o "generated random password is '[^']*" /tmp/credential | sed "s/generated random password is '//")
# Create template credential
json="{\"username\":\"$username\",\"password\":\"$password\"}"
# Save to json
filename="/credential"
echo "$json" > "$filename"

# Config webhook url at Gitea admin

# Gitea API URL
api_url="http://localhost:3000/api/v1"
hook_url="http://gitea:8080"

# 创建新hook的数据
hook_data='{
  "type": "gitea",
  "config": {
    "url": "'"$hook_url"'",
    "content_type": "json"
  },
  "events": ["push"],
  "active": true
}'

# 从JSON文件中读取用户名和密码
username=$(jq -r '.username' "$filename")
password=$(jq -r '.password' "$filename")

# 发送POST请求创建新hook
response=$(curl -s -u "$username:$password" -X POST -H "Content-Type: application/json" -d "$hook_data" "$api_url/user/hooks")

# 检查响应状态码
status_code=$(echo "$response" | jq -r '.status')
if [[ $status_code == "ok" ]]; then
  echo "New hook created successfully."
else
  error_message=$(echo "$response" | jq -r '.message')
  echo "Failed to create new hook: $error_message"
fi

