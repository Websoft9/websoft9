#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

# Check if user is root
if [ $(id -u) != "0" ]; then
echo -e "————————————————————————————————————————————————————
[ERROR] It is detected that you do not use root permissions to execute the script.
Please use the root account to log in to SSH to run this script
————————————————————————————————————————————————————"
exit

fi

clear
echo -e "————————————————————————————————————————————————————
Please enter the MySQL password you need to set up
Tip: do not enter a blank password.
————————————————————————————————————————————————————"

mysql_root_password=""
read -p "(Please enter the MySQL password you need to set up):" mysql_root_password
if [ "$mysql_root_password" = "" ]; then
echo "[ERROR] Please do not enter blank password\n"
exit 1
fi
printf "stop MySQL service......\n"
systemctl stop mysqld
printf "Setting the MySQL permissions table\n"
/usr/bin/mysqld_safe --skip-grant-tables >/dev/null 2>&1 &
printf "The permissions table is being refreshed and the password is reset\n"
sleep 10
/usr/bin/mysql -u root mysql << EOF
update user set password = Password('$mysql_root_password') where User = 'root';
EOF

reset_status=`echo $?`
if [ $reset_status = "0" ]; then
printf "The MySQL password has been set up successfully. Now restore the MySQL permissions table\n"
killall mysqld
sleep 10
printf "The MySQL service is being restarted\n"
systemctl start mysqld
echo -e "————————————————————————————————————————————————————
The MySQL password has been reset.
\033[33m $mysql_root_password \033[0m
————————————————————————————————————————————————————"
else
echo -e "————————————————————————————————————————————————————
[ERROR] Unable to reset the MySQL password.
————————————————————————————————————————————————————"
fi
