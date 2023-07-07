[![](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/badges/main/pipeline.svg)](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/-/pipelines)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)
[![GitHub last commit](https://img.shields.io/github/last-commit/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Release Date](https://img.shields.io/github/release-date/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Repo stars](https://img.shields.io/github/stars/LydraFr/ansible-yunohost?style=social)](https://github.com/LydraFr/ansible-yunohost)

# What is Websoft9?


Websoft9 is complete PaaS solution for running 200+ apps on your own server. Just install it, don't any steps.

Although the architecture in cloud native emphasizes high availability and clustering, this is not suitable for simple applications or low-concurrency scenarios, after all, most applications on the Internet do not need to implement complex clusters or K8S.

Websoft9 solves the problem of using multiple applications in a single server from the beginning, and we strongly believe in the principle of minimalism.Microservices architecture on single machine is not outdated. On the contrary, it becomes more and more valuable as computing power increases  

Instead of reinventing the wheel, we integrate the best open source products into our interface so that customers don't have to learn new technology stacks or worry about the lack of maintenance of components

- [Cockpit ](https://cockpit-project.org/): A web-based graphical interface for servers
- [Docker](https://www.docker.com/): Accelerate how you build, share, and run modern applications
- [Nginx Proxy Manager](https://nginxproxymanager.com/): A web-based Nginx management
- [Portainer](https://www.portainer.io/): Powerful container management for DevSecOps
- [Redis](https://redis.io/): The open source, in-memory data store

You can see the sceenshoots below:  

| ![image](https://github.com/Websoft9/websoft9/assets/16741975/8321780c-4824-4e40-997d-676a31534063) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/e842575b-60bc-4b0d-a57b-28c26b16196a) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/c598412a-9529-4286-ba03-6234d6da99b9)|
| ---- | ---- | ---- |
| ![image](https://github.com/Websoft9/websoft9/assets/16741975/7bed3744-1e9f-429e-8678-3714c8c262e2)|![image](https://github.com/Websoft9/websoft9/assets/16741975/a0923c69-2792-4cde-bfaf-bc018b61aee9) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/901efd1c-31a0-4b31-b79c-fc2d441bb679)|



## Funtction

- CLI
- Web Console
- Languages: English, Chinese（中文）

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

### only one app

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
