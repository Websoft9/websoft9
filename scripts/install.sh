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

# python2 -m pip == pip2
# python3 -m pip == pip3
# pip is already installed if you are using Python 2 >=2.7.9 or Python 3 >=3.4
# OracleLinux need install oaclelinux-developer-release-e* oracle-nodejs-release-e* oracle-epel-release-e* in Image before this script

if command -v yum > /dev/null; then
  sudo yum clean all 1>/dev/null 2>&1
  sudo yum makecache 1>/dev/null 2>&1
  sudo yum install -y epel-release 1>/dev/null 2>&1
  
  sudo yum install yum-utils git libselinux-python git python python3 git -y 1>/dev/null 2>&1
  sudo yum install python-pip -y 1>/dev/null 2>&1
  sudo yum install python2-pip -y 1>/dev/null 2>&1
  sudo yum install python3-pip -y 1>/dev/null 2>&1
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
  sudo apt-get install python-pip -y 1>/dev/null 2>&1
  sudo apt-get install python2-pip -y 1>/dev/null 2>&1
  sudo apt-get install python3-pip -y 1>/dev/null 2>&1
  if [[ $(cat /etc/os-release |grep VERSION_CODENAME |cut -d= -f2) == xenial ]];then
        curl -fsSL -o- https://bootstrap.pypa.io/pip/3.5/get-pip.py | python3.5
  fi 
  sudo python3 -m pip install -U --force-reinstall requests docker 1>/dev/null 2>&1
  sudo apt-get update 1>/dev/null 2>&1
  sudo apt install software-properties-common -y 1>/dev/null 2>&1
  if [[ $(cat /etc/os-release |grep VERSION_CODENAME |cut -d= -f2) == focal ]];then
        curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o /tmp/get-pip.py 1>/dev/null 2>&1
        python2 /tmp/get-pip.py 1>/dev/null 2>&1
  elif [[ $(cat /etc/os-release |grep VERSION_CODENAME |cut -d= -f2) == bionic ]];then
        sudo apt-add-repository --yes --update ppa:ansible/ansible
  fi
  sudo apt install ansible sshpass -y
fi
sudo python3 -m pip install --upgrade pip
sudo python2 -m pip -V
sudo python3 -m pip -V
sudo echo "Pre-installation has beend completed"

if [[ $repo_name != "" ]]
then
sudo rm -rf  /tmp/ansible-$repo_name
cd /tmp 
sudo git clone https://github.com/Websoft9/ansible-$repo_name.git
cd /tmp/ansible-$repo_name
ansible-galaxy install -r requirements.yml -f
sudo touch  /tmp/ansible-$repo_name/hosts
sudo echo "localhost" > /tmp/ansible-$repo_name/hosts
ansible-playbook -i hosts $repo_name.yml -c local -e init=$repo_init
echo  "System must restart after 2s, then installation completed"; sleep 2 ; sudo reboot
fi
