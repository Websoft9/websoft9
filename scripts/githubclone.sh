#!/bin/bash


# This script is created by Bing Chat
# 你可以使用以下修改后的 shell 脚本来自动尝试从 github.com 克隆仓库，如果失败了，再尝试使用不同的加速地址来克隆仓库。这个脚本会先尝试从 github.com 克隆仓库，如果失败了，再尝试使用我之前提到的加速地址来克隆仓库，直到成功为止。每个地址都会尝试克隆 3 次。如果克隆失败，脚本会输出友好的错误提示。这个脚本接受两个外部参数：$1 是用户名，$2 是仓库名。
# 获取外部参数
USERNAME="$1"
REPO="$2"

# 生成仓库 URL
REPO_URL="https://github.com/$USERNAME/$REPO.git"

# 加速地址列表
MIRRORS=(
    "https://github.com"
    "https://ghproxy.com/https://github.com"
)

for mirror in "${MIRRORS[@]}"; do
    # 生成加速后的 URL
    mirror_url="${REPO_URL/https:\/\/github.com/$mirror}"
    # 尝试克隆仓库
    for i in {1..3}; do
        echo "Trying to clone from $mirror_url (attempt $i)"
        if git clone  --depth=1 "$mirror_url"; then
            echo "Successfully cloned from $mirror_url"
            exit 0
        else
            echo "Failed to clone from $mirror_url (attempt $i)"
        fi
    done
done

echo "Failed to clone the repository after multiple attempts. Please check your network connection and try again later."
