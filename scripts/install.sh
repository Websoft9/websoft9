#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
clear

# Check if user is root
[ $(id -u) != "0" ] && { echo "Error: You must be root to run this script, please use 'sudo su -' command to change root"; exit 1; }

version(){
    echo "version: 0.1"
    echo "updated date: 2019-12-30"
}

Show_Help(){
    version
    echo "Usage: $0 command ...[parameters]...
    --help, -h           Show this help message
    --version, -v        Show version info
    "
}

# r:repository; i:init
while getopts ":r:"":i:"  opt
do
    case $opt in
        r)
        repo_name=$OPTARG;;
        i)
        repo_init=$OPTARG
        ;;
        ?)
        echo "no repository"
        exit 1;;
    esac
done
echo $repo_name
echo $repo_init

echo "Pre-installation is starting, please wait for 1-3 minutes..."

# OracleLinux need install oaclelinux-developer-release-e* oracle-nodejs-release-e* oracle-epel-release-e* in Image before this script

if command -v yum > /dev/null; then
  sudo yum clean all 1>/dev/null 2>&1
  sudo yum makecache 1>/dev/null 2>&1
  sudo yum install -y epel-release 1>/dev/null 2>&1
  
  sudo yum install yum-utils git libselinux-python git python python3 git -y 1>/dev/null 2>&1
  sudo python3 -m pip install -U --force-reinstall requests docker 1>/dev/null 2>&1
  if command -v amazon-linux-extras > /dev/null; then
	echo "amazon-linux-extras install ansible2"
	sudo amazon-linux-extras install ansible2 
   else
	echo "yum install ansible"
	sudo yum install ansible sshpass -y 1>/dev/null 2>&1
  fi
fi

if command -v apt > /dev/null; then
  sudo apt-get update 1>/dev/null 2>&1
  sudo apt-get install git python python3 git -y 1>/dev/null 2>&1
  sudo apt-get update 1>/dev/null 2>&1
  sudo apt install software-properties-common -y 1>/dev/null 2>&1
  if [[ $(cat /etc/os-release |grep VERSION_CODENAME |cut -d= -f2) == focal ]];then
        echo "have ansible pkg"
  elif [[ $(cat /etc/os-release |grep VERSION_CODENAME |cut -d= -f2) == bionic ]];then
        sudo apt-add-repository --yes --update ppa:ansible/ansible
  fi
  sudo apt install ansible sshpass -y
fi

sudo echo "Pre-installation has beend completed"

cd /tmp 
rm -rf stackhub
sudo git clone --depth=1 https://github.com/Websoft9/stackhub.git
cd stackhub/apps
sudo echo "localhost" > hosts
ansible-playbook -i hosts application.yml -c local -e init=$repo_init -e appname=$repo_name
if [ "$?"= "0" ]; then
   echo  "System must restart after 2s, then installation completed"; sleep 2 ; sudo reboot
else
   echo "Ansible execute error!" 1>&2
   exit 1
fi 
