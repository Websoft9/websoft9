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