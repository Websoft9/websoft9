#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# get applist
if [ -d StackHub ] ; then
  echo "StackHub is exists"
else
  git clone --depth=1 https://ghproxy.com/https://github.com/Websoft9/StackHub.git
fi 
appnames=$(ls StackHub/apps/roles |grep -v Template |grep -v README.md |grep -v role)

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
      echo "$containername容器名匹配成功app:$appname"
      targetlist="$targetlist $appname"
      cp /data/apps/library/apps/"$appname"/src/get_version.sh /tmp/"$appname"_get_version.sh
      chmod +x /tmp/"$appname"_get_version.sh
      bash /tmp/"$appname"_get_version.sh $containername
      break
    fi
  done 
done 

for appinfo in $(docker ps --format '{{.Names}}%{{.Image}}'); do                                   
 
  containername=$(echo $appinfo |awk -F"%" '{print $1}')
  imagename=$(echo $appinfo |awk -F"%" '{print $2}')
  
  for appname in $appnames; do

    if [[ $imagename =~ $appname  ]];then
      if [[ $targetlist =~ $appname  ]];then
        continue
      fi
      tmpvar="-"
      if [[ $containername =~ $tmpvar ]];then
         echo "$imagename=镜像名匹配成功app:$appname, and容器名是：$containername"
         targetlist="$targetlist $appname"
         cp /data/apps/library/apps/"$appname"/src/get_version.sh /tmp/"$appname"_get_version.sh
         chmod +x /tmp/"$appname"_get_version.sh
         bash /tmp/"$appname"_get_version.sh $containername
         break
      fi
    else
      realapp=echo $containername|awk -F"-" '{print $1}'
      services=docker compose -p $realapp ps  --services
      for service in $services; do
        if [[ $service == $appname ]];then
          echo "$service服务名匹配成功app:$appname, and容器名是：$containername"
          targetlist="$targetlist $appname"
          cp /data/apps/library/apps/"$appname"/src/get_version.sh /tmp/"$appname"_get_version.sh
          chmod +x /tmp/"$appname"_get_version.sh
          bash /tmp/"$appname"_get_version.sh $containername
          break
        fi
      done
    fi
  done 
done 
