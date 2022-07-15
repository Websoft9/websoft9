#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

containername=$1
imagename=$2

# get applist
if [ -d StackHub ] ; then
  echo "StackHub is exists"
else
  git clone --depth=1 https://github.com/Websoft9/StackHub.git
fi 
appnames=$(ls StackHub/apps/roles |grep -v Template |grep -v README.md |grep -v role)

for appname in $appnames; do                                   

  if [[ $containername == $appname ]];then
    echo "$containername容器匹配成功app:$appname"
    break
  elif [[ $imagename =~ $appname  ]];then
    tmpvar="-"
    if [[ $containername =~ $tmpvar ]];then
      echo "$imagename=镜像匹配成功app:$appname"
      break
    else
      echo "need other mothod "
    fi
  else
    echo "容器镜像均未匹配成功app:$appname"
  fi
done 
