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

if [ -f "$versions_local_file" ]; then
  echo "File $versions_local_file exists."
else
  echo "File $versions_local_file does not exist. Downloading from $versions_url"
  wget -q $versions_url -O $versions_local_file
fi

plugins=$(jq -c '.plugins' $versions_local_file)
if [ -z "$plugins" ]; then
  echo "No plugins found in $versions_local_file"
  exit 1
fi

for key in $(jq -r '.plugins | keys[]' $versions_local_file); do
  version=$(jq -r ".plugins.${key}" $versions_local_file)
  file_url=$artifact_url/$key/$key-$version$file_suffix
  file_name=$key-$version$file_suffix
  echo "Download from $file_url"
  wget -q $file_url -O $file_name
  unzip -oq $file_name -d $plugin_path
  rm -rf $file_name
done

find /usr/share/cockpit -type f -name "*.py3" -exec chmod +x {} \;

echo "Plugins install successfully..."
