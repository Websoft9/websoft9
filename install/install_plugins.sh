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

# channel,source_github_pages,install_path from install.sh priority
if [ -z "$channel" ]; then
  channel="release"
fi

if [ -z "$source_github_pages" ]; then
  source_github_pages="https://websoft9.github.io/websoft9"
fi

if [ -z "$install_path" ]; then
  install_path="/data/websoft9/source"
fi

echo -e "\n\n-------- Plugins --------"
echo "Your installation parameters are as follows: "
echo "--channel: $channel"
echo "--install_path: $install_path"

artifact_url="https://w9artifact.blob.core.windows.net/$channel/websoft9/plugin"
echo_prefix_plugins=$'\n[Plugins] - '

versions_local_file="$install_path/version.json"
versions_url="$source_github_pages/version.json"
file_suffix=".zip"
plugin_path="/usr/share/cockpit"

echo "$echo_prefix_plugins Starting download plugin and update it"

python3 - << END
import requests
import json
import queue
import os
import sys
import zipfile
import io

def get_plugin_versions(versions_local_file, versions_url, artifact_url, file_suffix, plugin_path):
    if os.path.exists(versions_local_file):
        print("Get version file on your local install"+versions_local_file)
        with open(versions_local_file) as f:
            data = json.load(f)
    else:
        try:
            print("Get version file from URL " + versions_url)
            response = requests.get(versions_url, timeout=5)  # Set timeout to 5 seconds
            data = json.loads(response.text)
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print("Error occurred while getting version file from URL: ", e)
            sys.exit(1)  # Exit the program if an error occurred

    plugins = data.get('plugins', {})

    q = queue.Queue()
    for plugin, version in plugins.items():
        q.put(f'{artifact_url}/{plugin}/{plugin}-{version}{file_suffix}')

    return q

# 使用函数
q = get_plugin_versions("${versions_local_file}", "${versions_url}", "${artifact_url}", "${file_suffix}", "${plugin_path}")

# 下载并解压缩文件
while not q.empty():
    try:
        file_url = q.get()
        print(f"Downloading {file_url}...")
        response = requests.get(file_url, stream=True, timeout=120)  # Set timeout to 120 seconds

        # Make sure the download was successful
        response.raise_for_status()  

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall("${plugin_path}")
        print(f"Successfully extracted {file_url} to ${plugin_path}")
    except Exception as e:
        print(f"Error occurred while downloading or extracting file: {e}")
        sys.exit(1)  # Exit the program if an error occurred
END

echo "Plugins install successfully..."
