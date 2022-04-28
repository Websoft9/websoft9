#!/bin/bash
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

set -e

# Please modify this version and time after update
version(){
    sudo echo "version: 1.6"
    sudo echo "updated date: 2021-05-26"
}

# Tool list, apt or yum installation is only supported  
tool_list=(
git
pwgen
jq
wget
curl
figlet
boxes
)

help_str="
Usage:
  -h, --help       Show this help message         
  -r, --repo_name  The name of the warehouse
  -p, --package    Making local packs,Only when you need to pack
  -v, --version    Show version info
example: bash install.sh -r template -p  
"
make_package=false

# Get option parameters
getopt_cmd=$(getopt -o r:phv --long repo_name:,package,help,version -n "Parameter error" -- "$@")
eval set -- "$getopt_cmd"

while [ -n "$1" ]
do
    case "$1" in
        -r|--repo_name)
            repo_name=$2
            shift ;;
        -h|--help)
            sudo echo -e "$help_str"
            exit ;;
        -p|--package)
            make_package=true
            shift ;;
        -v|--version)
            version
            shift ;;
         --) 
            break
            shift ;;
    esac
    shift
done

   
  [ ! -n "$repo_name" ] && exit 1

install_tools(){
  if command -v apt > /dev/null;then  
    sudo apt update 1>/dev/null 2>&1
    sudo apt install ${tool_list[*]} -y  1>/dev/null 2>&1
  elif  command -v yum > /dev/null;then 
    sudo yum clean all 1>/dev/null 2>&1
    sudo yum makecache 1>/dev/null 2>&1
    sudo yum install ${tool_list[*]} -y 1>/dev/null 2>&1
  fi
}

download_docker_source(){
    docker_download_url="https://download.docker.com/linux/static/stable/x86_64/docker-20.10.6.tgz"
    cd /tmp/
    sudo rm -rf docker.tgz
    sudo wget $docker_download_url -O docker.tgz 1>/dev/null 2>&1
    sudo echo -e "docker downloaded successfully"
sudo cat > /tmp/docker.service <<EOF
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
After=network-online.target firewalld.service
Wants=network-online.target
[Service]
Type=notify
# the default is not to use systemd for cgroups because the delegate issues still
# exists and systemd currently does not support the cgroup feature set required
# for containers run by docker
ExecStart=/usr/bin/dockerd
ExecReload=/bin/kill -s HUP \$MAINPID
# Having non-zero Limit*s causes performance problems due to accounting overhead
# in the kernel. We recommend using cgroups to do container-local accounting.
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
# Uncomment TasksMax if your systemd version supports it.
# Only systemd 226 and above support this version.
#TasksMax=infinity
TimeoutStartSec=0
# set delegate yes so that systemd does not reset the cgroups of docker containers
Delegate=yes
# kill only the docker process, not all processes in the cgroup
KillMode=process
# restart the docker process if it exits prematurely
Restart=on-failure
StartLimitBurst=3
StartLimitInterval=60s
[Install]
WantedBy=multi-user.target
EOF
}

install_docker_script(){
  if command -v docker > /dev/null;then 
    sudo echo -e `docker -v`
    sudo echo -e "Docker installed successfully"
  else 
    sudo curl -fsSL https://get.docker.com -o get-docker.sh &>/dev/null && sh get-docker.sh &>/dev/null 
    sudo rm -rf get-docker.sh
    sudo systemctl start docker 
    sudo systemctl enable docker &>/dev/null
    sudo echo -e `docker -v`
    sudo echo -e "Docker installed successfully"
  fi
  
}

uninstall_docker(){
    sudo rm -f /etc/systemd/system/docker.service 
    sudo rm -rf /usr/bin/docker*
    sudo systemctl daemon-reload
    sudo echo -e "Docker uninstalled successfully"
}

download_docker_compose(){
   sudo curl -L "https://github.com/docker/compose/releases/download/1.29.0/docker-compose-$(uname -s)-$(uname -m)" -o /tmp/docker-compose 1>/dev/null 2>&1
   sudo chmod +x /tmp/docker-compose 
   sudo echo -e "docker-compose downloaded successfully"   
}

install_docker_compose(){ 
    curl -L "https://github.com/docker/compose/releases/download/1.29.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose 1>/dev/null 2>&1
    sudo chmod +x /usr/local/bin/docker-compose 
    sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose &>/dev/mull || true
    sudo echo `docker-compose -v`
    sudo echo -e "docker-compose installed successfully"
}

save_images(){
    sudo rm -rf /tmp/docker-$repo_name
    sudo git clone https://github.com/Websoft9/docker-$repo_name.git /tmp/docker-$repo_name || sudo git clone https://github.com.cnpmjs.org/Websoft9/docker-$repo_name.git /tmp/docker-$repo_name
    sudo docker rmi `docker images -aq` -f &>/dev/null || true

    cd /tmp/docker-$repo_name


# Pull images and save images
    sudo systemctl start docker
    docker-compose pull 
    sudo echo -e "In image packaging, there is a long wait..." 
    sudo docker save $(docker images | grep -v REPOSITORY | awk 'BEGIN{OFS=":";ORS=" "}{print $1,$2}') -o /tmp/$repo_name.tar 
    sudo echo -e "The image was successfully saved as a tar package" 
}

installation(){
    sudo rm -rf $install_dir 
    sudo mkdir -p $install_dir /credentials 1>/dev/null 2>&1 &&  cd $install_dir  
    sudo git clone https://github.com/Websoft9/docker-$repo_name.git $install_dir   || sudo git clone https://github.com.cnpmjs.org/Websoft9/docker-$repo_name.git $install_dir

# Rename compose and env file name
    cd $install_dir

# Stop the container and remove the Volumes for sec_installation
    cd $install_dir
    rm -rf volumes
    sudo docker-compose down -v 1>/dev/null 2>&1

# Avoiding db port conflicts
    sudo echo -e "The database port is changing"
    db_port_lines=$(cat $install_dir/.env |grep DB_.*PORT |wc -l)
    db_port=$(cat $install_dir/.env |grep DB_.*PORT |cut -d= -f2 |sed -n 1p)
 
    while true 
    do 
       if [ "$db_port_lines" -gt 0 ];then
          os_db_port_lines=$(ss -ntulp |grep -w "$db_port" |wc -l)
          if [ "$os_db_port_lines" -gt 0 ];then
              db_port=`expr $db_port + 1`
              sed -ri "s/(DB.*_PORT=).*/\1$db_port/" $install_dir/.env
          else 
              break
          fi
       else
          break
       fi
    done

# DB Random password
    sudo echo -e "---$repo_name Installation Wizard----" |boxes |tee -a /credentials/password.txt
    new_password=$(pwgen -ncCs 15 1)

    db_password_lines=`cat $install_dir/.env |grep DB.*PASSWORD |wc -l`
    db_user_lines=`cat $install_dir/.env |grep DB_.*_USER |wc -l`

    if  [ $db_password_lines -gt 0 ];then 
        if  [ $db_user_lines -gt 0 ];then 
          db_username=$(cat $install_dir/.env |grep DB_.*_USER |cut -d= -f2 |sed -n 1p )
          sudo echo "db username: $db_username" |tee -a /credentials/password.txt
        else
          sudo echo "db username: root" |tee -a /credentials/password.txt
        fi
      sudo sed -ri "s/(DB_.*_PASSWORD=).*/\1$new_password/" $install_dir/.env &>/dev/null || true
      sudo echo "db password: $new_password" |tee -a /credentials/password.txt
    else
      sudo echo "No database password" |tee -a /credentials/password.txt
    fi

    if [ "$db_port_lines" -gt 0 ];then
      sudo echo "db port: $db_port" |tee -a /credentials/password.txt
    fi

    sudo echo -e "************************************\n"|tee -a /credentials/password.txt

# APP Random password
    app_password_lines=$(cat $install_dir/.env |grep -w "APP_PASSWORD_INIT" |wc -l)
    app_user_lines=$(cat $install_dir/.env |grep -w "APP_USER" |wc -l)
    app_port_lines=$(cat $install_dir/.env |grep -w "APP_PORT" |wc -l)

    if [ "$app_user_lines" -gt 0 ];then
      app_username=$(cat $install_dir/.env |grep -w "APP_USER" |cut -d= -f2 |sed -n 1p) 
      sudo echo "$repo_name login username: $app_username" |tee -a /credentials/password.txt
    else
        sudo echo "$repo_name login username: default username, please see the $install_dir/.env" |tee -a /credentials/password.txt
    fi
    
    if  [ "$app_password_lines" -gt 0 ];then 
      sudo sed -ri "s/(APP_PASSWORD=).*/\1$new_password/" $install_dir/.env &>/dev/null || true
      sudo echo "$repo_name login password: $new_password" |tee -a /credentials/password.txt
    else
      sudo echo "$repo_name login password: default password, please see the $install_dir/.env" |tee -a /credentials/password.txt
    fi

    if [ "$app_port_lines" -gt 0 ];then
      app_port=$(cat $install_dir/.env |grep -w "APP_PORT" |cut -d= -f2 |sed -n 1p) 
      sudo echo "$repo_name login port: $app_port" |tee -a /credentials/password.txt
    fi

    sudo echo -e "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" |tee -a /credentials/password.txt

# Modify public network IP
  public_ip=`wget -O - https://download.websoft9.com/ansible/get_ip.sh 2>/dev/null |bash` 
  case $repo_name in
    "erpnext")
      sudo sed -i "s/APP_SITE_NAME.*/APP_SITE_NAME=$public_ip/g" $install_dir/.env
      sudo sed -i "s/APP_SITES=.*/APP_SITES=\`$public_ip\`/g" $install_dir/.env
      ;;
    "graylog")
      sudo sed -i "s#APP_HTTP_EXTERNAL_URI=.*#APP_HTTP_EXTERNAL_URI=http://$public_ip:9001/#g" $install_dir/.env
      ;;
    "rocketchat")
      sudo sed -i "s#APP_ROOT_URL=.*#APP_ROOT_URL=http://$public_ip:9001/#g" $install_dir/.env
      ;;
    *) 
      ;;
  esac
    
# Change compose cli environment
    export DOCKER_CLIENT_TIMEOUT=500
    export COMPOSE_HTTP_TIMEOUT=500
    
    sudo systemctl start docker
    sudo docker-compose up -d 
    sleep 5
    sudo clear 
    sudo echo -e "\n $repo_name installation complete\n" |boxes -d whirly
    sudo echo -e "\n Please go to $repo_name to view the README file"
    sudo docker ps -a   
}

add_install_script(){
    sudo rm -rf /tmp/install.sh /tmp/README /tmp/setup.sh

# Mirror package installation script
cat > /tmp/install.sh <<-EOF
# Install docker
    sudo tar -xf docker.tgz 
    sudo systemctl stop docker &>/dev/mull || true
    sudo mv docker.service /etc/systemd/system/docker.service 
    sudo mv docker/* /usr/bin/  1>/dev/null 2>&1
    sudo systemctl daemon-reload
    sudo systemctl start docker
    sudo systemctl enable docker &>/dev/null
    sudo echo \$(docker -v)
    sudo echo -e "Docker was installed successfully"
# Install docker-compose
    sudo mv docker-compose /usr/local/bin/docker-compose 1>/dev/null 2>&1
    sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose &>/dev/mull || true
    sudo echo \$(docker-compose -v)
    sudo echo -e "docker-compose installed successfully"
# Pre_installation
    sudo rm -rf $install_dir
    sudo mkdir -p $install_dir /credentials  1>/dev/null 2>&1
    sudo docker load -i $repo_name.tar 
    cur_dir=\$(pwd)
    upper_dir=\$(dirname $install_dir)
    sudo rm -rf \$upper_dir/$repo_name
    cp=\$(which cp)
    \$cp -rf \$cur_dir/docker-$repo_name \$upper_dir/$repo_name 1>/dev/null 2>&1
    sudo mv README \$upper_dir/$repo_name/README 1>/dev/null 2>&1
# Stop the container and remove the Volumes for sec_installation
    cd $install_dir
    rm -rf volumes
    sudo docker-compose down -v 1>/dev/null 2>&1 
    
# Avoiding db port conflicts
    db_port_lines=\$(cat $install_dir/.env |grep DB_.*PORT |wc -l)
    db_port=\$(cat $install_dir/.env |grep DB_.*PORT |cut -d= -f2 |sed -n 1p)
    while true 
    do 
       if [ "\$db_port_lines" -gt 0 ];then
          os_db_port_lines=\$(ss -ntulp |grep \$db_port |wc -l)
          if [ "\$os_db_port_lines" -gt 0 ];then
              db_port=`expr \$db_port + 1`
              sed -ri "s/(DB.*_PORT=).*/\1\$db_port/" $install_dir/.env
          else 
              break
          fi
       else
          break
       fi
    done
# DB Random password
    sudo echo -e "---$repo_name Installation Wizard---\n" |tee -a /credentials/password.txt
    new_password=\$(date | md5sum | awk '{print $1}' |cut -c 3-18)
    db_password_lines=\$(cat $install_dir/.env |grep DB.*PASSWORD |wc -l)
    db_user_lines=\$(cat $install_dir/.env |grep DB_.*_USER |wc -l)
  if  [ \$db_password_lines -gt 0 ];then 
      if  [ \$db_user_lines -gt 0 ];then 
        db_username=\$(cat $install_dir/.env |grep DB_.*_USER |cut -d= -f2 |sed -n 1p)
        sudo echo "db username: \$db_username" |tee -a /credentials/password.txt
      else
        sudo echo "db username: root" |tee -a /credentials/password.txt
      fi
    sudo sed -ri "s/(DB_.*_PASSWORD=).*/\1\$new_password/" $install_dir/.env &>/dev/null || true
    sudo echo "db password: \$new_password" |tee -a /credentials/password.txt
  else
    sudo echo "No database password" |tee -a /credentials/password.txt
  fi
  if [ "\$db_port_lines" -gt 0 ];then
      sudo echo "db port: \$db_port" |tee -a /credentials/password.txt
  fi
    sudo echo -e "************************************\n" |tee -a /credentials/password.txt
# APP Random password  
  app_user_lines=\$(cat $install_dir/.env |grep -w "APP_USER" |wc -l)
  app_password_lines=\$(cat $install_dir/.env |grep -w "APP_PASSWORD_INIT" |wc -l)
  app_port_lines=\$(cat $install_dir/.env |grep -w "APP_PORT" |wc -l)
  if [ "\$app_user_lines" -gt 0 ];then
      app_username=\$(cat $install_dir/.env |cut -d= -f2 |sed -n 1p) 
      sudo echo "$repo_name login username: \$app_username" |tee -a /credentials/password.txt
  else
      sudo echo "$repo_name login username: default username, please see the $install_dir/.env" |tee -a /credentials/password.txt
  fi
  
  if  [ "\$app_password_lines" -gt 0 ];then 
    sudo sed -ri "s/(APP_PASSWORD=).*/\1\$new_password/" $install_dir/.env &>/dev/null || true
    sudo echo "$repo_name login password: \$new_password" |tee -a /credentials/password.txt
  else
    sudo echo "$repo_name login password: default password, please see the $install_dir/.env" |tee -a /credentials/password.txt
  fi
  if [ "\$app_port_lines" -gt 0 ];then
      app_port=\$(cat $install_dir/.env |grep -w "APP_PORT" |cut -d= -f2 |sed -n 1p) 
      sudo echo "$repo_name login port: \$app_port" |tee -a /credentials/password.txt
  fi
    sudo rm -rf \$cur_dir/{$repo_name.tar,get-docker.sh,docker.service,docker-compose,docker.tgz,docker,install.sh,docker-$repo_name} 
    sudo echo -e "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" |tee -a /credentials/password.txt
# Modify public network IP
  public_ip=\$(wget -O - https://download.websoft9.com/ansible/get_ip.sh 2>/dev/null | timeout 10 bash)
  case $repo_name in
    "erpnext")
      sudo sed -i "s/APP_SITE_NAME.*/APP_SITE_NAME=\$public_ip/g" $install_dir/.env
      sudo sed -i "s/APP_SITES=.*/APP_SITES=\`\$public_ip\`/g" $install_dir/.env
      ;;
    "graylog")
      sudo sed -i "s#APP_HTTP_EXTERNAL_URI=.*#APP_HTTP_EXTERNAL_URI=http://\$public_ip:9001/#g" $install_dir/.env
      ;;
    "rocketchat")
      sudo sed -i "s#APP_ROOT_URL=.*#APP_ROOT_URL=http://\$public_ip:9001/#g" $install_dir/.env
      ;;
    *)  
      ;;
  esac
# Change compose cli environment
    export DOCKER_CLIENT_TIMEOUT=500
    export COMPOSE_HTTP_TIMEOUT=500
    
    sudo systemctl start docker
    sudo docker-compose up -d 
    sudo clear && sudo docker ps -a 
    sudo echo -e "\n $repo_name installation complete\n"  
    sudo echo -e "\n Please go to \$upper_dir/$repo_name to view the README file"
EOF

# README file
cat > /tmp/README <<-EOF
Document address:
    http://support.websoft9.com/docs/$repo_name/zh/
Project address: 
    https://github.com/websoft9/docker-$repo_name
Password file location: 
    /credentials/password.txt
EOF

# Unpack the pre-installed script
cat > /tmp/setup.sh <<-EOF
#!/bin/bash   
line=\`wc -l \$0|awk '{print \$1}'\`   
line=\`expr \$line - 7\`   
tail -n \$line \$0 |tar zx -C ~ 
cd ~
./install.sh   
ret=\$?   
exit \$ret
EOF

sudo chmod +x /tmp/install.sh 
sudo chmod +x /tmp/setup.sh 
}

get_install_information(){
   install_dir=`curl -s https://raw.githubusercontent.com/Websoft9/docker-$repo_name/main/variables.json |jq -r .installpath` 1>/dev/null
   compose_file_name=`curl -s https://raw.githubusercontent.com/Websoft9/docker-$repo_name/main/variables.json |jq -r .compose_file` 1>/dev/null
   compose_env_url="https://raw.githubusercontent.com/Websoft9/docker-$repo_name/main/.env"
   url_status=`curl -s -m 5 -IL $compose_env_url |grep 200 || true`
if [[ $url_status == "" ]];then
       sudo echo "The env file does not exist"
       exit 1
fi

if [[ $install_dir == "null" || $compose_file_name = "null" ]];then
       sudo echo "variables.json has an undefined parameter"
       exit 1
fi
     sudo echo install path $install_dir 
     sudo echo compose filename $compose_file_name
}

make_package(){
   sudo rm -rf /tmp/$repo_name.tgz install-$repo_name
   cd /tmp && tar -zcf /tmp/$repo_name.tgz ./{install.sh,README,$repo_name.tar,docker-$repo_name,docker.tgz,docker.service,docker-compose}
   sudo cat setup.sh $repo_name.tgz > ~/install-$repo_name
   sudo chmod +x ~/install-$repo_name
   cd ~  && sudo echo -e "Image packaging successfully" |boxes -d whirly
}

print_information(){
  sudo figlet websoft9
# Check if the repo exists
  repo_name_exists=$(curl -s --head https://github.com/Websoft9/docker-$repo_name | head -n 1 |grep -c '200') 
  [ "$repo_name_exists" -ne 1 ] && sudo echo -e "The repo does not exist !" && exit 1 
      
# Print installation information
  if [ -n "$repo_name" ] && [ "$make_package" == false ];then
      sudo echo "docker-$repo_name to be installed..."
  fi

  if [ -n "$repo_name" ] && [ "$make_package" == true ];then
      sudo echo "$repo_name will be packaged as an image..."
  fi
}

install_tools

print_information

get_install_information  

if [ $make_package = false ]; then
   install_docker_script
   install_docker_compose
   installation
fi

if [ $make_package = true ]; then
   install_docker_script
   install_docker_compose
   download_docker_source
   download_docker_compose
   save_images
   add_install_script
   make_package
fi
