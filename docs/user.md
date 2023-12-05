# User Guide

## FAQ

#### user can not sudo?

```
# add user to sudo/admin group (select one command)
usermod -aG wheel username
usermod -aG sudo username

# sudo not need to input password
```

#### Can not login with correct credential?

Many reason may make you login failed with the correct credential:

- Cookie at you browser if IP change, need to clear cookie
- *.override.json is not correct
- TLS certificate
- User not allowed login, need to modify ssh_config file

More details, you can get it from `sudo grep cockpit /var/log/messages`

#### How to modify Websoft9 port?

Access web console > settings or use cli to modify port

#### 当服务器IP怎么办？

服务器 IP 变更，Websoft9 控制台能够自动适用，即使用新的 IP 访问即可。   

但是，部分没有绑定域名的应用不能自动适用，即当应用无法访问时，您需要需要重新编排应用，将 env 中的 W9_URL 更换新的 IP 后，重建应用。

#### 如何创建多用户并赋予权限？

Websoft9 控制台 > 【用户账号】菜单中创建用户，创建完成后在面板中将新用户增加到 docker 用户组中。

如果需要给用户添加 sudo，需要通过命令 visudo 将下面的内容增加到 sudoers 文件中(user001 表示您新创建的用户名)  
```
user001 ALL=(ALL:ALL) ALL
```

#### appstore 502 error?

Try `docker restart websoft9-proxy` to solved it