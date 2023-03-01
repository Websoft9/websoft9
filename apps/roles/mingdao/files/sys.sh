#!/bin/bash

if [[ -f /usr/local/MDPrivateDeployment/first ]];then   
  rm -rf /data/mingdao/  
  /bin/rm -f /usr/local/MDPrivateDeployment/first  
  /bin/bash /usr/local/MDPrivateDeployment/service.sh stopall  
  /bin/bash /usr/local/MDPrivateDeployment/service.sh start
else  
  sleep 30
  docker system prune -f
  /bin/bash /usr/local/MDPrivateDeployment/service.sh stopall
  /bin/bash /usr/local/MDPrivateDeployment/service.sh startall
fi
