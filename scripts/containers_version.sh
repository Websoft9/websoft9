#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# get applist
if [ -d StackHub ] ; then
  echo "StackHub is exists"
else
  git clone --depth=1 https://github.com/Websoft9/StackHub.git
fi 
appnames=$(ls StackHub/apps/roles |grep -v Template |grep -v README.md |grep -v role)

# 匹配成功的APP集合字符串
targetlist=""

# get all of the running container's information( containername and imagename)
for appinfo in $(docker ps --format '{{.Names}}%{{.Image}}'); do                                   
 
  containername=$(echo $appinfo |awk -F"%" '{print $1}')
  imagename=$(echo $appinfo |awk -F"%" '{print $2}')
  
  for appname in $appnames; do

    if [[ $containername == $appname ]];then
      if [[ $targetlist =~ $appname  ]];then
        continue
      fi
      echo "$containername容器匹配成功app:$appname"
      targetlist="$targetlist $appname"
      wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
      bash /tmp/$appname_get_version.sh $containername
      break
    elif [[ $imagename =~ $appname  ]];then
      if [[ $targetlist =~ $appname  ]];then
        continue
      fi
      tmpvar="-"
      if [[ $containername =~ $tmpvar ]];then
         echo "$imagename=镜像匹配成功app:$appname"
         targetlist="$targetlist $appname"
         wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
         bash /tmp/$appname_get_version.sh $containername
         break
      fi
    else
      realapp=echo $containername|awk -F"-" '{print $1}'
      services=docker compose -p $realapp ps  --services
      for service in $services; do
        if [[ $service == $appname ]];then
          echo "$containername容器匹配成功app:$appname"
          targetlist="$targetlist $appname"
          wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
          bash /tmp/$appname_get_version.sh $containername
          break
        fi
      done
    fi
  done 
done 
