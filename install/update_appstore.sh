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

fastest=$(fastest_url "${urls[@]}")
echo "fasturl is: "$fastest
cd /tmp && rm -rf /tmp/stackhub-web && git clone $fastest/Websoft9/stackhub-web
rm -rf /usr/share/cockpit/appstore/static/data && cp -r /tmp/stackhub-web/plugins/appstore/build/static/data /usr/share/cockpit/appstore/static
rm -rf /usr/share/cockpit/myapps/static/logos && cp -r /tmp/stackhub-web/plugins/myapps/build/static/logos /usr/share/cockpit/myapps/static

rm $0
}
LibraryUpdate