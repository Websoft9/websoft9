# Scripts

## install.sh

install.sh 是我们提供的一键安装脚本，用于部署基于Docker的应用项目

```
#安装项目，初始化
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh -r magento -i 1


#安装项目，不初始化
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh -r magento -i 0 或
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh; bash install.sh -r magento
```
install.sh 支持两个参数：

* -r 代表项目名称，例如：magento, lamp, lnmp, wordpress, joomla, gitlab 等
* -i 代表是否初始化，支持 0（默认值）和1 两种参数

### 一键安装中途中断怎么办？

执行如下命令:
```
cd /tmp/stackhub/apps
ansible-playbook -i hosts application.yml -c local -e init=【一键安装脚本的-i 参数】 -e appname=【一键安装脚本的-r 参数】
```

## reset_mysql_password.sh

1. 该脚本目前只适用于CentOS7以上的系统和MySQL5.6版本；
2. 该脚本基于 https://github.com/EwigeveMicca/Mysql_ResetPasswd_Script 进行修改；
3. 使用方法：远程连接到服务器，运行一下命令，按提示输入新密码即可。
   ```
   sudo git clone https://github.com/Websoft9/linuxscript.git; cd linuxscript/Mysql_ResetPasswd_Script;sudo sh reset_mysql_password.sh
   ```
