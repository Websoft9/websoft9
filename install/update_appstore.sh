#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

function  error_exit {
  echo "$1" 1>&2
  exit 1
}
trap 'error_exit "Please push issue to: https://github.com/Websoft9/StackHub/issues"' ERR

urls=(
    https://ghproxy.com/https://github.com
    https://github.com
    https://gitee.com
)

function fastest_url() {
  urls=("$@")
  fastest_url=""
  fastest_time=0

  for url in "${urls[@]}"; do
    if curl --output /dev/null --silent --head --fail --max-time 3 "$url"; then
        data="url is available"
    else
        continue
    fi 
    time=$(curl --connect-timeout 3 -s -w '%{time_total}\n' -o /dev/null $url)
    if (( $(echo "$time < $fastest_time || $fastest_time == 0" | bc -l) )); then
      fastest_time=$time
      fastest_url=$url
    fi
  done

  echo "$fastest_url"
}

LibraryUpdate(){
echo "auto_update start..." >> /tmp/auto_update.txt
if [ ! -f /data/library/install/version.json ]; then
    old_library_version="0.0.1"
else
    old_library_version=$(cat /data/library/install/version.json | jq .VERSION | tr -d '"')
fi
latest_library_version=$(curl https://websoft9.github.io/docker-library/install/version.json | jq .VERSION | tr -d '"')

if [ "$old_library_version" \< "$latest_library_version" ]; then
    echo "start to update Library..."
    release_version=$(curl https://websoft9.github.io/stackhub-web/CHANGELOG.md | head -n 1 |cut -d' ' -f2)
    fastest=$(fastest_url "${urls[@]}")
    echo "fasturl is: "$fastest
    cd /tmp && rm -rf /tmp/library /tmp/stackhub-web
    if [[ $fastest == *gitee.com* ]]; then
        echo "update from gitee"
        wget $fastest/websoft9/docker-library/repository/archive/$latest_library_version
        unzip $latest_library_version
        mv docker-library* library
        rm -f $latest_library_version

        wget $fastest/websoft9/stackhub-web/repository/archive/$release_version
        unzip $release_version
        mv stackhub-web* stackhub-web
        rm -f $release_version
    else
        echo "update from github"
        wget $fastest/websoft9/docker-library/archive/refs/tags/$latest_library_version.zip
        unzip $latest_library_version.zip
        mv docker-library* library
        rm -f $latest_library_version.zip

        wget $fastest/websoft9/stackhub-web/archive/refs/tags/$release_version.zip
        unzip $release_version.zip
        mv stackhub-web* stackhub-web
        rm -f $release_version.zip
    fi
    rm -rf /data/library && cp -r /tmp/library /data
    rm -rf /usr/share/cockpit/appstore/static/data && cp -r /tmp/stackhub-web/plugins/appstore/build/static/data /usr/share/cockpit/appstore/static
    rm -rf /usr/share/cockpit/myapps/static/logos && cp -r /tmp/stackhub-web/plugins/myapps/build/static/logos /usr/share/cockpit/myapps/static
    
else
    echo "Library is not need to update"
fi
rm $0
}
LibraryUpdate