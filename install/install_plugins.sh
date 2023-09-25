#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH


# Command-line options
# ==========================================================
#
# --channel <release|dev>
# Use the --channel option to install a release(production) or dev distribution. default is release, for example:
#
#  $ sudo sh install.sh --channel release
#
# ==============================================================================

# get input and define vars
while [[ $# -gt 0 ]]; do
    case $1 in
        --channel)
            channel="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done


if [ -z "$channel" ]; then
  channel="release"
fi

if [ -z "$source_github_pages" ]; then
  source_github_pages="https://websoft9.github.io/websoft9"
fi

if [ -z "$install_path" ]; then
  install_path="/data/websoft9/source"
fi


echo "Your installation parameters are as follows: "
echo "--channel: $channel"

artifact_url="https://w9artifact.blob.core.windows.net/$channel/websoft9/plugin"
echo_prefix_cockpit=$'\n[Plugins] - '
mydata=""

version_json(){

    if [ -f "$install_path/version.json" ]; then
        echo "Find version file on your $install_path "
        mydata=$(cat "$install_path/version.json")
        echo $mydata
    else
        echo "Get version.json from $source_github_pages/version.json"
        mydata=$(curl -s "$source_github_pages/version.json")
        if [ $? -ne 0 ]; then
            echo "URL does not exist or cannot be accessed."
            exit 1
        else
            echo "$mydata"
        fi
    fi
}


install_plugins() {
    echo "$echo_prefix_cockpit Start to install plugins"
    echo $mydata

    # 解析数据文件，获取 plugins 的子元素和对应的版本号
    plugins=$(echo "$data" | jq -r '.plugins | keys_unsorted[]')
    versions=$(echo "$data" | jq -r '.plugins | .[]')

    echo $plugins
    echo $versions

    # 定义数组变量
    declare -a artifact_array

    # 构建数组内容
    readarray -t plugins_array <<<"$plugins"
    readarray -t versions_array <<<"$versions"

    for ((i=0; i<${#plugins_array[@]}; i++)); do
    artifact_array+=("$artifact_url/${plugins_array[$i]}-${versions_array[$i]}")
    done

    # 打印数组元素
    for element in "${artifact_array[@]}"; do
    echo "$element"
    done
}

version_json
install_plugins
