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
initdata=""

# get all of the running container's information( containername and imagename)
for appinfo in $(docker ps --format '{{.Names}}%{{.Image}}'); do                                   
 
  containername=$(echo $appinfo |awk -F"%" '{print $1}')
  imagename=$(echo $appinfo |awk -F"%" '{print $2}')
  
  for appname in $appnames; do

    if [[ $containername == $appname ]];then
      # app的版本已经输出
      if [[ $initdata =~ $appname  ]];then
        continue
      fi
      echo "$containername容器匹配成功app:$appname"
      initdata="$initdata $appname"
      wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
      bash /tmp/$appname_get_version.sh $containername
      break
    elif [[ $imagename =~ $appname  ]];then
      # app的版本已经输出
      if [[ $initdata =~ $appname  ]];then
        continue
      fi
      tmpvar="-"
      if [[ $containername =~ $tmpvar ]];then
         echo "$imagename=镜像匹配成功app:$appname"
         initdata="$initdata $appname"
         wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
         bash /tmp/$appname_get_version.sh $containername
         break
  	  fi
    else
      echo "通过服务名匹配"
    fi
  done 
done 
