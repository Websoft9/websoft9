#!/bin/bash

set -e

cred_path="/var/websoft9/credential"
admin_username="websoft9"
admin_email="help@websoft9.com"

if [ -e "$cred_path" ]; then
  echo "File $cred_path exists. Exiting script."
  exit 1
fi

echo "create diretory"
mkdir -p "$(dirname "$cred_path")"


# TODO IF admin is exists, echo it to cred_path

echo "Create admin credential by admin cli"
su -c "
    gitea admin user create --admin --username '$admin_username' --random-password --email '$admin_email' > /tmp/credential
" git

echo "Read credential from tmp"
username=$(grep -o "New user '[^']*" /tmp/credential | sed "s/New user '//")
if [ -z "$username" ]; then
  username="websoft9"
fi
password=$(grep -o "generated random password is '[^']*" /tmp/credential | sed "s/generated random password is '//")

echo "Save to credential"
json="{\"username\":\"$username\",\"password\":\"$password\"}"
echo "$json" > "$cred_path"
