#!/bin/bash

if [ -e "/credential" ]; then
  echo "File /credential exists. Exiting script."
  exit 1
fi

# Create admin credential by admin cli
su -c '
    gitea admin user create --admin --username websoft9 --random-password --email help@websoft9.com > /tmp/credential
' git

# Read credential from tmp
username=$(grep -o "New user '[^']*" /tmp/credential | sed "s/New user '//")
if [ -z "$username" ]; then
  username="websoft9"
fi
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

# Param data
hook_data='{
  "type": "gitea",
  "config": {
    "url": "'"$hook_url"'",
    "content_type": "json"
  },
  "events": ["push"],
  "active": true
}'

# Create a hook
curl -s -u "$username:$password" -X POST -H "Content-Type: application/json" -d "$hook_data" "$api_url/user/hooks"