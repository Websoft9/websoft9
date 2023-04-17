#!/bin/bash

# 获取外部参数
USERNAME="$1"
REPO="$2"

# 生成仓库 URL
REPO_URL="https://github.com/$USERNAME/$REPO.git"

# 加速地址列表
MIRRORS=(
    "https://github.com"
    "https://github.com.cnpmjs.org"
    "https://hub.fastgit.org"
    "https://gitclone.com"
    "https://gh.api.99988866.xyz"
    "https://github.zhlh6.cn"
    "https://toolwa.com/github"
)

for mirror in "${MIRRORS[@]}"; do
    # 生成加速后的 URL
    mirror_url="${REPO_URL/https:\/\/github.com/$mirror}"
    # 尝试克隆仓库
    for i in {1..3}; do
        echo "Trying to clone from $mirror_url (attempt $i)"
        if git clone "$mirror_url"; then
            echo "Successfully cloned from $mirror_url"
            exit 0
        else
            echo "Failed to clone from $mirror_url (attempt $i)"
        fi
    done
done

echo "Failed to clone the repository after multiple attempts. Please check your network connection and try again later."
