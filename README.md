# Websoft9

Websoft9 is complete solution for running 200+ apps on your own server. Just install it, don't any steps.
![image](https://github.com/Websoft9/websoft9/assets/16741975/8321780c-4824-4e40-997d-676a31534063)


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
