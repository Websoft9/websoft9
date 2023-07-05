[![](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/badges/main/pipeline.svg)](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/-/pipelines)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)
[![GitHub last commit](https://img.shields.io/github/last-commit/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Release Date](https://img.shields.io/github/release-date/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Repo stars](https://img.shields.io/github/stars/LydraFr/ansible-yunohost?style=social)](https://github.com/LydraFr/ansible-yunohost)

# Websoft9

Websoft9 is complete solution for running 200+ apps on your own server. Just install it, don't any steps.
![image](https://github.com/Websoft9/websoft9/assets/16741975/8321780c-4824-4e40-997d-676a31534063)

## Funtction

- CLI
- Web Console

## Development

- websoft9 appmanage
- websoft9 docker-compose

## API

- Docker API: http://IP(内网):5000/

## CMD for referance

```
# Get all docker repo of Websoft9 org
gh repo list Websoft9 -L 500 | awk '{print $1}'  | grep docker > test
```

## All-in-one Installer

### Only one app

```
# for example, app is mongodb
wget -N https://websoft9.github.io/websoft9/scripts/install.sh; bash install.sh -r mongodb
```

### websoft9 include appstore

```
sudo su # when you have no root privileges
curl https://websoft9.github.io/websoft9/install/install.sh | bash
```

## Upgrade

```
sudo su # when you have no root privileges
curl https://websoft9.github.io/websoft9/install/update.sh | bash
```
