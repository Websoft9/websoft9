function get_os_type() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
    else
        OS=$(uname -s)
    fi

    if [[ "$OS" == "CentOS Linux" ]]; then
        echo "CentOS"
    elif [[ "$OS" == "CentOS Stream" ]]; then
        echo "CentOS Stream"
    elif [[ "$OS" == "Rocky Linux" ]]; then
        echo "Rocky Linux"
    elif [[ "$OS" == "Oracle Linux Server" ]]; then
        echo "OracleLinux"
    elif [[ "$OS" == "Debian GNU/Linux" ]]; then
        echo "Debian"
    elif [[ "$OS" == "Ubuntu" ]]; then
        echo "Ubuntu"
    elif [[ "$OS" == "Fedora Linux" ]]; then
        echo "Fedora"
    elif [[ "$OS" =~  "Red Hat Enterprise Linux" ]]; then
        echo "Redhat"
    else
        echo $OS
    fi
}

function get_os_version() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VERSION=$(lsb_release -sr)
    else
        OS=$(uname -s)
        VERSION=$(uname -r)
    fi

    echo $VERSION
}
os_type=$(get_os_type)
os_version=$(get_os_version)

CheckEnvironment(){

echo "---------------------------------- Welcome to install websoft9's appstore, it will take 3-5 minutes -------------------------------------------------------" 

echo "Check  environment ..."
echo  os_type: $os_type
echo  os_version: $os_version
if [ $(id -u) != "0" ]; then
    echo "Please change to root or 'sudo su' to up system privileges, and  reinstall the script again ."
    exit 1
fi

if [ $(getconf WORD_BIT) = '32' ] && [ $(getconf LONG_BIT) = '64' ] ; then
    echo "64-bit operating system detected."
else
    echo "This script only works on 64-bit operating systems."
    exit 1
fi

if [ "$os_type" == 'CentOS' ] ;then
  if [ "$os_version" != "7" ]; then
      echo "This app only supported on CentOS 7"
      exit 1
  fi
fi

if  [ "$os_type" == 'CentOS Stream' ] ;then
  if [ "$os_version" != "8" ] || [ "$os_version" != "9" ]; then
      echo "This app only supported on CentOS Stream 8,9"
      exit 1
  fi
fi

if [ "$os_type" == 'Rocky Linux' ] ;then
  if [ "${os_version:0:1}" == "8" ] || [ "${os_version:0:1}" == "9" ]; then
      echo ""
  else
      echo "This app only supported on Rocky Linux 8"
      exit 1
  fi
fi

if  [ "$os_type" == 'Fedora' ];then
  if [ "$os_version" != "37" ]; then
      echo "This app only supported on Fedora 37"
      exit 1
  fi
fi

if  [ "$os_type" == 'Redhat' ];then
  if [ "${os_version:0:1}" != "7" ] && [ "${os_version:0:1}" != "8" ]  && [ "${os_version:0:1}" != "9" ]; then
      echo "This app only supported on Redhat 7,8"
      exit 1
  fi
fi

if  [ "$os_type" == 'Ubuntu' ];then
  if [ "$os_version" != "22.04" ] && [ "$os_version" != "20.04" ] && [ "$os_version" != "18.04" ]; then
      echo "This app only supported on Ubuntu 22.04,20.04,18.04"
      exit 1
  fi
fi

if  [ "$os_type" == 'Debian' ];then
  if [ "$os_version" != "11" ];then
      echo "This app only supported on Debian 11"
      exit 1
  fi
fi

# Check port used
if netstat -tuln | grep -qE ':(80|443|9000)\s'; then
    echo "Port 80,443,9000  is already in use."
    exit 1
else
    echo "Port 80,443, 9000 are free."
fi
          
}


InstallCockpit(){
echo "Prepare to install Cockpit ..." 

if [ "${os_type}" == 'Debian' ]; then
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo echo "deb http://deb.debian.org/debian ${VERSION_CODENAME}-backports main" >/etc/apt/sources.list.d/backports.list
  sudo apt update
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  sudo apt install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'Ubuntu' ]; then
  if grep -q "^#.*deb http://mirrors.tencentyun.com/ubuntu.*backports" /etc/apt/sources.list; then
      echo "Add backports deb ..." 
      sudo sed -i 's/^#\(.*deb http:\/\/mirrors.tencentyun.com\/ubuntu.*backports.*\)/\1/' /etc/apt/sources.list
      apt update
  fi
  VERSION_CODENAME=$(cat /etc/os-release |grep VERSION_CODENAME|cut -f2 -d"=")
  sudo apt install -t ${VERSION_CODENAME}-backports cockpit -y
  sudo apt install cockpit-pcp -y 1>/dev/null 2>&1
  echo "Cockpit allow root user" 
  echo "" >/etc/cockpit/disallowed-users 1>/dev/null 2>&1
fi

if [ "${os_type}" == 'CentOS' ] || [ "$os_type" == 'OracleLinux' ]; then
  sudo yum install cockpit -y 
  sudo yum install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --permanent --zone=public --add-service=cockpit
  sudo firewall-cmd --reload
fi

if [ "$os_type" == 'Fedora' ]; then
  sudo dnf install cockpit -y 
  sudo dnf install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'Redhat' ] ; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo yum install cockpit-pcp cockpit-packagekit -y 1>/dev/null 2>&1
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
fi

if [ "$os_type" == 'CentOS Stream' ]; then
  sudo subscription-manager repos --enable rhel-7-server-extras-rpms 1>/dev/null 2>&1
  sudo yum install cockpit -y
  sudo yum install cockpit-pcp -y 1>/dev/null 2>&1
  sudo systemctl enable --now cockpit.socket
  sudo firewall-cmd --add-service=cockpit
  sudo firewall-cmd --add-service=cockpit --permanent
  sudo setenforce 0  1>/dev/null 2>&1
  sudo sed -i 's/SELINUX=.*/SELINUX=disabled/' /etc/selinux/config  1>/dev/null 2>&1
  
fi

file="/etc/cockpit/disallowed-users"

if [ -f "$file" ]; then
    echo "" > "$file"
else
    echo "$file is not exist"
fi

echo "Set cockpit port to 9000 ..." 
sudo sed -i 's/ListenStream=9090/ListenStream=9000/' /lib/systemd/system/cockpit.socket


}