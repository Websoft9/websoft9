#!/bin/bash

# 请在此处设置您的仓库 URL 和镜像 URL

USERNAME=$1
REPO=$2

# 构建仓库 URL 和镜像 URL
REPO_URL="https://github.com/$USERNAME/$REPO.git"
MIRROR_URLS=("https://hub.fastgit.org/$USERNAME/$REPO.git" "https://github.com.cnpmjs.org/$USERNAME/$REPO.git")

# 定义最大重试次数
MAX_RETRIES=3

# 定义克隆函数
clone_repo() {
  local url=$1
  local retries=0

  # 尝试克隆，直到成功或达到最大重试次数
  while [ $retries -lt $MAX_RETRIES ]; do
    git clone $url

    # 如果克隆成功，则退出循环
    if [ $? -eq 0 ]; then
      return 0
    fi

    # 增加重试次数并等待一段时间再重试
    retries=$((retries + 1))
    echo "无法从 $url 克隆，等待 5 秒后重试 ($retries/$MAX_RETRIES)"
    sleep 5
  done

  # 如果达到最大重试次数，则返回非零值表示失败
  return 1
}

# 尝试从原始 URL 克隆
clone_repo $REPO_URL

# 检查上一个命令的退出状态
if [ $? -ne 0 ]; then
  # 遍历镜像 URL 数组
  for MIRROR_URL in "${MIRROR_URLS[@]}"; do
    echo "无法从 $REPO_URL 克隆，尝试从镜像 $MIRROR_URL 克隆"
    clone_repo $MIRROR_URL

    # 如果克隆成功，则退出循环
    if [ $? -eq 0 ]; then
      break
    fi
  done
fi
