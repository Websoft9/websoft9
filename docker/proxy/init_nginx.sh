#!/bin/bash

# Define variables
credential_path="/data/credential"
INNER_GATEWAY_PORT=${INNER_GATEWAY_PORT:-80}

# Migrating initproxy.conf file
if [ ! -d /data/nginx/default_host ]; then mkdir -p /data/nginx/default_host; fi

#替换占位符并复制配置文件
sed "s/{{INNER_GATEWAY_PORT}}/$INNER_GATEWAY_PORT/g" /etc/websoft9/initproxy.conf > /tmp/initproxy.conf
cp -f /tmp/initproxy.conf /data/nginx/default_host/initproxy.conf

[ -f /etc/websoft9/initproxy.conf ] && rm -f /data/nginx/proxy_host/initproxy.conf

# Deploy Websoft9 landing pages
if [ ! -d /data/nginx/default_www/landing ]; then
    mkdir -p /data/nginx/default_www/ 
    cp -r /etc/websoft9/landing /data/nginx/default_www/
else
    echo "/data/nginx/default_www/landing already exists."
fi

# If credential file then create it and init credential for NPM
# Reload NPM docker image Environments

if [ ! -f "$credential_path" ]; then
  # Set init credential
  INITIAL_ADMIN_EMAIL="admin@mydomain.com"
  INITIAL_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+' | cut -c1-16)

  # Write credential to file
  mkdir -p "$(dirname "$credential_path")"
  echo "{\"username\":\"$INITIAL_ADMIN_EMAIL\",\"password\":\"$INITIAL_ADMIN_PASSWORD\"}" > "$credential_path"

else
  read -r INITIAL_ADMIN_EMAIL INITIAL_ADMIN_PASSWORD < <(jq -r '.username + " " + .password' "$credential_path")
fi

# Reload NPM docker image Environments
export INITIAL_ADMIN_EMAIL
export INITIAL_ADMIN_PASSWORD

# 主执行函数
main() {
    echo "启动NPM主进程..."
    exec /init "$@"
}

# 后台初始化任务
{
  # 初始化标记检查
  INIT_FLAG="/data/.initialized"
  if [ -f "$INIT_FLAG" ]; then
      echo "⏩ 检测到已初始化，跳过证书配置"
      exit 0
  fi


  # 等待API就绪并获取JWT
  MAX_RETRY=30
  RETRY_INTERVAL=2
  JWT=""

  for ((i=1; i<=MAX_RETRY; i++)); do
      echo "尝试获取访问令牌（第 $i 次）..."
      
      JWT_RESPONSE=$(timeout 5 curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "http://localhost:81/api/tokens" \
          -H "Content-Type: application/json" \
          -d "{\"identity\":\"$INITIAL_ADMIN_EMAIL\", \"secret\":\"$INITIAL_ADMIN_PASSWORD\", \"scope\":\"user\"}")

      HTTP_STATUS=${JWT_RESPONSE##*HTTP_STATUS:}
      RESPONSE_BODY=${JWT_RESPONSE/HTTP_STATUS:*/}

      if [ "$HTTP_STATUS" -eq 200 ]; then
          JWT=$(jq -r '.token' <<< "$RESPONSE_BODY")
          [ -n "$JWT" ] && break
          echo "⚠️ 令牌为空，继续重试..."
      elif [ "$HTTP_STATUS" -ge 400 ] && [ "$HTTP_STATUS" -lt 500 ]; then
          echo "❌ 认证失败 [HTTP $HTTP_STATUS] 请检查账号密码"
          exit 1
      else
          echo "⚠️ 服务暂不可用 [HTTP $HTTP_STATUS]，等待重试..."
      fi
      
      sleep $RETRY_INTERVAL
  done

  [ -z "$JWT" ] && { echo "❌ 获取访问令牌失败，请确认服务已正常启动"; exit 1; }

  echo "✅ 认证成功，服务已就绪"

  #创建证书记录
  CERT_JSON='{"nice_name":"websoft9-inner","provider":"other"}'
  CERT_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "http://localhost:81/api/nginx/certificates" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT" \
    -d "$CERT_JSON")

  # 解析响应
  HTTP_STATUS=${CERT_RESPONSE##*HTTP_STATUS:}
  RESPONSE_BODY=${CERT_RESPONSE/HTTP_STATUS:*/}

  # 处理结果
  if [[ $HTTP_STATUS = 20* ]]; then  # 匹配200/201等2xx状态码
      CERT_ID=$(jq -r '.id' <<< "$RESPONSE_BODY")
      if [[ $CERT_ID =~ ^[0-9]+$ ]]; then
          echo "🔄 证书创建成功，ID: $CERT_ID"
      else
          echo "❌ 证书ID提取异常，响应内容：$RESPONSE_BODY"
          exit 1
      fi
  else
      echo "❌ 证书创建失败 [HTTP $HTTP_STATUS] 响应内容：$RESPONSE_BODY"
      exit 1
  fi

  #上传自定义证书
  SSL_DIR="/data/custom_ssl"
  CERT_FILE="$SSL_DIR/websoft9-self-signed.cert"
  KEY_FILE="$SSL_DIR/websoft9-self-signed.key"

  mkdir -p "$SSL_DIR"
  echo "🔄 强制生成新的自签名证书（有效期1年）..."
  openssl req -x509 -newkey rsa:4096 -nodes \
      -keyout "$KEY_FILE" \
      -out "$CERT_FILE" \
      -days 365 \
      -subj "/CN=Websoft9 Universal Certificate" \
      -addext "basicConstraints=critical,CA:TRUE" \
      -addext "keyUsage=digitalSignature,keyEncipherment" \
      -addext "extendedKeyUsage=serverAuth" \
      -addext "subjectAltName=DNS:*,IP:0.0.0.0" 2>/dev/null

  echo "✅ 证书扩展信息："
  openssl x509 -in "$CERT_FILE" -text -noout | grep -E 'DNS|IP|Usage'

  # 严格权限控制
  chmod 644 "$CERT_FILE"
  chmod 600 "$KEY_FILE"


 # 生成随机边界
  BOUNDARY="boundary$(openssl rand -hex 16)"
  UPLOAD_URL="http://localhost:81/api/nginx/certificates/$CERT_ID/upload"

  # 创建临时文件
  TMP_REQ=$(mktemp)

  # 构建请求体到临时文件
  {
      printf -- "--%s\r\n" "$BOUNDARY"
      printf "Content-Disposition: form-data; name=\"certificate\"; filename=\"%s\"\r\n" "$(basename "$CERT_FILE")"
      printf "Content-Type: application/octet-stream\r\n\r\n"
      cat "$CERT_FILE"
      printf "\r\n--%s\r\n" "$BOUNDARY"
      printf "Content-Disposition: form-data; name=\"certificate_key\"; filename=\"%s\"\r\n" "$(basename "$KEY_FILE")"
      printf "Content-Type: application/octet-stream\r\n\r\n"
      cat "$KEY_FILE"
      printf "\r\n--%s--\r\n" "$BOUNDARY"
  } > "$TMP_REQ"

  # 执行上传
  UPLOAD_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$UPLOAD_URL" \
      -H "Content-Type: multipart/form-data; boundary=$BOUNDARY" \
      -H "Authorization: Bearer $JWT" \
      --data-binary "@$TMP_REQ")

  # 清理临时文件
  rm -f "$TMP_REQ"

  # 解析上传响应
  HTTP_STATUS_UPLOAD=${UPLOAD_RESPONSE##*HTTP_STATUS:}
  RESPONSE_BODY_UPLOAD=${UPLOAD_RESPONSE/HTTP_STATUS:*/}

  if [[ "$HTTP_STATUS_UPLOAD" = 20* ]]; then
      echo "✅ 证书上传成功（HTTP $HTTP_STATUS_UPLOAD）"
  else
      echo "❌ 证书上传失败 [HTTP $HTTP_STATUS_UPLOAD]"
      echo "错误详情：$(echo "$RESPONSE_BODY_UPLOAD" | jq -r '.detail // .message')"
      exit 1
  fi

  touch "$INIT_FLAG"
  echo "🏁 初始化完成标记已创建"

}&

# 执行主进程
main "$@"
