#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# get applist
if [ -d StackHub ] ; then
  echo "StackHub is exists"
else
  git clone --depth=1 https://github.com/Websoft9/StackHub.git
fi 
appnames=$(ls StackHub/apps/roles |grep -v Template |grep -v README.md |grep -v role)

# get all of the running container's information( containername and imagename)
for appinfo in $(docker ps --format '{{.Names}}%{{.Image}}'); do                                   
 
  containername=$(echo $appinfo |awk -F"%" '{print $1}')
  imagename=$(echo $appinfo |awk -F"%" '{print $2}')
  
  for appname in $appnames; do                                   
  
    if [[ $containername == $appname ]];then
  	echo "$appname和$containername容器匹配成功"
  	wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
  	bash /tmp/$appname_get_version.sh $containername
  	break
    elif [[ $imagename =~ $appname  ]];then
  	tmpvar="-"
  	if [[ $containername =~ $tmpvar ]];then
  	  echo "$appname和$imagename镜像匹配成功"
  	  wget -O /tmp/$appname_get_version.sh https://raw.githubusercontent.com/Websoft9/docker-$appname/main/src/get_version.sh
  	  bash /tmp/$appname_get_version.sh $containername
  	  break
  	else
  	  echo "need other mothod "
  	fi
    else
  	echo "$appname和容器镜像均未匹配成功"
    fi
  done 
done 
