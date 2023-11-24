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