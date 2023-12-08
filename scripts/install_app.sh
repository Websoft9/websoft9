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
appname=""
appid="demo"
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

check_appname() {
    if [ -z "$appname" ]; then
        echo "appname cannot be empty"
        exit 1
    fi
    if [ ! -d "/tmp/library/apps/$appname" ]; then
        echo "websoft9 can not support to install this app"
        exit 1
    fi
}

get_public_ip() {
    get_ip_path=$(find / -name get_ip.sh 2>/dev/null)
    public_ip=$(bash "$get_ip_path")
    echo "$public_ip"
}

get_domain_names() {
    local domain_names="$1"
    local public_ip="$2"
    local ip_regex="^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    if [ -z "$domain_names" ]; then
        domain_names="$public_ip"
    elif [[ $domain_names =~ $ip_regex ]]; then
        domain_names="$domain_names"
    fi
    echo "$domain_names"
}

get_proxy_enabled() {
    local domain_names="$1"
    local ip_regex="^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    local proxy_enabled=true
    if [ -z "$domain_names" ] || [[ $domain_names =~ $ip_regex ]]; then
        proxy_enabled=false
    fi
    echo "$proxy_enabled"
}

get_settings() {
    local filename="$1"
    local settings=$(grep "^W9_.*_SET=" "$filename" | awk -F '=' '{print $1, $2}' | \
    while read -r key value; do
        jq -n --arg key "$key" --arg value "$value" '{($key): $value}'
    done | jq -s add | jq -c .)
    echo "$settings"
}

install_app(){
  
  check_appname
  public_ip=$(get_public_ip)
  domain_names=$(get_domain_names "$domain_names" "$public_ip")
  proxy_enabled=$(get_proxy_enabled "$domain_names")
  rm -rf /tmp/library && sudo docker cp websoft9-apphub:/websoft9/library /tmp
  filename="/tmp/library/apps/${appname}/.env"
  settings=$(get_settings "${filename}")
  api_url="localhost/api/apps/install"
  api_key=$(sudo docker exec -i websoft9-apphub apphub getconfig --section api_key --key key)
  request_param=$(jq -n \
                    --arg app_name "$appname" \
                    --arg dist "$dist" \
                    --arg version "$version" \
                    --arg app_id "$appid" \
                    --arg proxy_enabled "$proxy_enabled" \
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

  response=$(curl -s -w "\n%{http_code}" -X POST "$api_url" \
                  -H "Content-Type: application/json" \
                  -H "x-api-key: $api_key" \
                  -d "$request_param")
  echo "$response"
  
}

app_list(){
  api_url="localhost/api/apps"
  api_key=$(sudo docker exec -i websoft9-apphub apphub getconfig --section api_key --key key)
  response=$(curl -s -w "\n%{http_code}" -X GET "$api_url" \
                  -H "Content-Type: application/json" \
                  -H "x-api-key: $api_key")
  echo "$response"
}

echo "-----------------Start to install ${appname}---------------------"
response=$(install_app)

http_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)

echo "Install HTTP Code: $http_code"
echo "Response Body: $response_body"

if [ "$http_code" -eq 200 ]; then
    
    max_attempts=50
    for (( i=1; i<=$max_attempts; i++ ))
    do
        result=$(app_list)
        result_body=$(echo "$result" | head -n -1)
        echo $result_body
        if echo "$result_body" | jq -e --arg app_id "$appid" '.[] | select((.app_id | startswith($app_id)) and .status != 3)' >/dev/null; then
            echo "$appname install success."
            echo "---------check $appname status for docker---------"
            sudo docker ps -a |grep $appid
            break
        else
            echo "App is installing, waiting for 5 seconds..."
            sleep 5
        fi
    done
else
    error_message=$(echo "$response_body" | jq -r '.message')
    error_details=$(echo "$response_body" | jq -r '.details')
    echo "Install failed: $error_message, Details: $error_details"
fi