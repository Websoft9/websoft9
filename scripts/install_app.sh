#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# About this Script and command-line options
# ==============================================================================
#
# --dist
# Use the --dist option to install distribution at variable.json file. default is community, for example:
#
#  $ sudo bash install_app.sh --dist community
#
# --version "2.0.1"
# Use the --version option to set application version. default is lastest, for example:
#
#   $ sudo bash install_app.sh --version "2.0.1"
#
# --appanme "wordpress"
# Use the --appanme option for install which application. default is wordpress, for example:
#
#  $ sudo bash install_app.sh --appanme "wordpress"
#
# --appid "mywp"
# Use the --appid option to distinguish installed application, default is mywp, for example:
#
#  $ sudo bash install_app.sh --appid "mywp"
#
# --domain_names "www.websoft9.com,dev.websoft9.com"
# Use the --domain_names option to binding domains for application,it can use any strings (not more than 2), default is "", for example:
#
#  $ sudo bash install.sh --domain_names "test.websoft9.com"
#  $ sudo bash install.sh --domain_names "47.92.175.174"
#  $ sudo bash install.sh --domain_names "test1.websoft9.com,test2.websoft9.com"
# ==============================================================================

# 设置参数的默认值
dist="community"
version="latest"
appname="wordpress"
appid="mywp"
domain_names=""
proxy_enabled=true

# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --dist)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --dist"
                exit 1
            fi
            dist="$1"
            shift
            ;;
        --version)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --version"
                exit 1
            fi
            version="$1"
            shift
            ;;
        --appname)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --appname"
                exit 1
            fi
            appname="$1"
            shift
            ;;
        --appid)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --appid"
                exit 1
            fi
            appid="$1"
            shift
            ;;
        --domain_names)
            shift
            if [[ $1 == --* ]]; then
                echo "Missing value for --domain_names"
                exit 1
            fi
            domain_names="$1"
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

have_websoft9=$(docker compose ls | grep websoft9)
if [ -z "$have_websoft9" ]; then
    echo "You must install websoft9 service first"
    exit 1
fi

echo "Start to get ip from script"
get_ip_path=$(find / -name get_ip.sh 2>/dev/null)
public_ip=$(bash "$get_ip_path")
if [ -z "$domain_names" ]; then
    domain_names="$public_ip"
fi

rm -rf /tmp/library && sudo docker cp websoft9-apphub:/websoft9/library /tmp
filename="/tmp/library/apps/${appname}/.env"
if ! grep -q "W9_URL" "$filename"; then
    proxy_enabled=false
else
    echo "W9_URL found in $filename."
fi

settings=$(grep "^W9_.*_SET=" "$filename" | awk -F '=' '{print $1, $2}' | \
while read -r key value; do
    jq -n --arg key "$key" --arg value "$value" '{($key): $value}'
done | jq -s add | jq -c .)

echo "Start to install $appname"
api_url="$public_ip/api/apps/install"
api_key=$(sudo docker exec -i websoft9-apphub apphub getconfig --section api_key --key key)
request_param=$(jq -n \
                  --arg app_name "$appname" \
                  --arg dist "$dist" \
                  --arg version "$version" \
                  --arg app_id "$appid" \
                  --argjson proxy_enabled "$proxy_enabled" \
                  --arg domain_names "$domain_names" \
                  --argjson settings "$settings" \
                  '{
                    "app_name": $app_name,
                    "edition": {
                      "dist": $dist,
                      "version": $version
                    },
                    "app_id": $app_id,
                    "proxy_enabled": $proxy_enabled,
                    "domain_names": [$domain_names],
                    "settings": $settings
                   }')

echo $request_param
response=$(curl -s -w "%{http_code}" -X POST "$api_url" \
                -H "Content-Type: application/json" \
                -H "x-api-key: $api_key" \
                -d "$request_param")

echo "$response"
echo "------------------------------"
# http_code=$(echo "$response" | tail -n1)
# response_body=$(echo "$response" | head -n -1)

# if [ "$http_code" -eq 200 ]; then
#     sudo docker ps -a |grep "$appid"
# else
#     error_message=$(echo "$response_body" | jq -r '.message')
#     error_details=$(echo "$response_body" | jq -r '.details')
#     echo "Error: $error_message, Details: $error_details"
# fi