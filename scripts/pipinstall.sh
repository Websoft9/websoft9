function pipInstall() {
  requirementsFile=$1
  declare -a mirrors=(
    https://pypi.org
    https://pypi.tuna.tsinghua.edu.cn/simple/
    https://pypi.mirrors.ustc.edu.cn/simple/
    https://mirrors.aliyun.com/pypi/simple/
    https://pypi.hustunique.com/
    https://pypi.sdutlinux.org/
    https://pypi.douban.com/simple/
    https://repo.huaweicloud.com/repository/pypi/simple/
  )
  time=-1
  fastMirror=""
  for url in "${mirrors[@]}"; do
    SPEED_DOWNLOAD=$(curl --location --range 0-102400 --max-time 8 --silent --write-out %{speed_download} --output /dev/null "${url}")
    tempReult=$(echo "${SPEED_DOWNLOAD} ${time}" | awk '{if ($1 > $2) print 1; else print 0}')
    if [ "${tempReult}" -ne 0 ]; then
      time=${SPEED_DOWNLOAD}
      fastMirror=${url}
    fi
  done
  echo "choose the url: ${fastMirror}"
  pip install -r ${requirementsFile} -i ${fastMirror}
}

function retry() {
  local retries=$1
  shift

  local count=0
  until "$@"; do
    exit=$?
    wait=$((2 ** $count))
    count=$(($count + 1))
    if [ $count -lt $retries ]; then
      echo "Retry $count/$retries exited $exit, retrying in $wait seconds..."
      sleep $wait
    else
      echo "Retry $count/$retries exited $exit, no more retries left."
      return $exit
    fi
  done
  return 0
}
retry 3 pipInstall requirement.txt
