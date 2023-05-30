# StackHub

This repository will replace the [Websoft9 Ansible project](https://github.com/websoft9private) before

StackHub is for opensource stacks automation, it is developing...

## Funtction

- CLI
- Web Console

## Development

- stack template
- stack core
- stack docker-compose

## API

- Docker API: http://IP:9009/

## CMD for referance

```
# Get all docker repo of Websoft9 org
gh repo list Websoft9 -L 500 | awk '{print $1}'  | grep docker > test
```

## All-in-one Installer

### only one app

```
# for example, app is mongodb
wget -N https://websoft9.github.io/StackHub/scripts/install.sh; bash install.sh -r mongodb
```

### stackhub include appstore

```
sudo su # when you have no root privileges
curl https://websoft9.github.io/StackHub/install/install.sh | bash
```

## Upgrade

```
sudo su # when you have no root privileges
curl https://websoft9.github.io/StackHub/install/update.sh | bash
```
