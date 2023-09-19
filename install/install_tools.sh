#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

InstallTools

### -----------------------------------------------------###

InstallTools(){

echo "Prepare to install Tools ..."

if [ "$os_type" == 'CentOS' ] || [ "$os_type" == 'Rocky Linux' ] || [ "$os_type" == 'CentOS Stream' ]  || [ "$os_type" == 'Fedora' ] || [ "$os_type" == 'OracleLinux' ] || [ "$os_type" == 'Redhat' ];then
  sudo yum update -y
  sudo yum install  git curl wget yum-utils jq bc unzip -y

fi

if [ "$os_type" == 'Ubuntu' ] || [ "$os_type" == 'Debian' ] ;then
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
      echo "Waiting for other software managers to finish..."
      sleep 5
  done
  sudo apt update -y 1>/dev/null 2>&1
  if command -v git > /dev/null;then  
    echo "git installed ..."
  else
    sudo apt install git -y
  fi
  if command -v curl > /dev/null;then  
    echo "jcurlq installed ..."
  else
    sudo apt install curl -y
  fi
  if command -v wget > /dev/null;then  
    echo "wget installed ..."
  else
    sudo apt install wget -y
  fi
  if command -v jq > /dev/null;then  
    echo "jq installed ..."
  else
    sudo apt install jq -y
  fi

  if command -v bc > /dev/null;then  
    echo "bc installed ..."
  else
    sudo apt install bc -y
  fi
  if command -v unzip > /dev/null;then  
    echo "unzip installed ..."
  else
    sudo apt install unzip -y
  fi
fi

}
