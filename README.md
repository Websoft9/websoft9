# StackHub

本项目开发中...

StackHub is for opensource stacks automation, it is developing...

## Funtction

* CLI
* Web Console 

## Development

* stack template
* stack core
* stack docker-compose

## API

* Docker API: http://IP:9009/

## CMD for referance
```
# Get all docker repo of Websoft9 org
gh repo list Websoft9 -L 500 | awk '{print $1}'  | grep docker > test
```
## All-in-one Installer
```
wget -N https://raw.githubusercontent.com/Websoft9/StackHub/main/scripts/install.sh;bash install.sh -r mongodb
```
