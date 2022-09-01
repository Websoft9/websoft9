# Scripts
# 脚本说明


## install.sh

install.sh 安装 Stackhub 的自动化脚本，支持两个参数：

* -r 代表项目名称，例如：magento, lamp, lnmp, wordpress, joomla, gitlab 等
* -i 代表是否用于镜像生产，支持 0（默认值，不用于镜像生产）和 1 两种参数

主要有两种使用场景

### 制作镜像

制作镜像的场景下，脚本会删除服务器上的密钥对或运行云平台的某些恢复服务器出厂设置命令。

```
# 安装应用
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh; bash install.sh -r magento -i 1

# 中断后命令
cd /tmp/stackhub/apps && ansible-playbook -i hosts application.yml -c local -e init=1 -e appname=magento
```

### 安装应用立即使用

此场景下，安装完成后，系统会强制重启

```
# 安装应用
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh; bash install.sh -r magento -i 0

# 中断后命令
cd /tmp/stackhub/apps && ansible-playbook -i hosts application.yml -c local -e init=0 -e appname=magento
```

## reset_mysql_password.sh

1. 该脚本目前只适用于CentOS7以上的系统和MySQL5.6版本；
2. 该脚本基于 https://github.com/EwigeveMicca/Mysql_ResetPasswd_Script 进行修改；
3. 使用方法：远程连接到服务器，运行一下命令，按提示输入新密码即可。
   ```
   sudo git clone https://github.com/Websoft9/linuxscript.git; cd linuxscript/Mysql_ResetPasswd_Script;sudo sh reset_mysql_password.sh
   ```
