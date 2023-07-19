[![](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/badges/main/pipeline.svg)](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/-/pipelines)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)
[![GitHub last commit](https://img.shields.io/github/last-commit/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Release Date](https://img.shields.io/github/release-date/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Repo stars](https://img.shields.io/github/stars/LydraFr/ansible-yunohost?style=social)](https://github.com/LydraFr/ansible-yunohost)

# What is Websoft9?

Websoft9 is complete minimalist and web-based PaaS for running [open source application](https://github.com/Websoft9/docker-library/tree/main/apps) that have more than 1k stars on your own server.

Although the architecture in cloud native emphasizes high availability and clustering, this is not suitable for simple applications or low-concurrency scenarios, after all, most applications on the Internet do not need to implement complex clusters or K8S.

Websoft9 solves the problem of using multiple applications in a single server from the beginning, and we strongly believe in the principle of minimalism.Microservices architecture on single machine is not outdated. On the contrary, it becomes more and more valuable as computing power increases

## Demos

You can see the sceenshoots below:

| ![image](https://github.com/Websoft9/websoft9/assets/16741975/8321780c-4824-4e40-997d-676a31534063) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/e842575b-60bc-4b0d-a57b-28c26b16196a) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/c598412a-9529-4286-ba03-6234d6da99b9) |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| ![image](https://github.com/Websoft9/websoft9/assets/16741975/7bed3744-1e9f-429e-8678-3714c8c262e2) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/a0923c69-2792-4cde-bfaf-bc018b61aee9) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/901efd1c-31a0-4b31-b79c-fc2d441bb679) |

## Features

- Install 200+ template applications with any configuration
- Web-base file browser to manage files and folder
- Manage user accounts
- Use a terminal on a remote server in your local web browser
- Nginx gui for proxy and free SSL with Let's Encrypt
- Deploy, configure, troubleshoot and secure containers in minutes on Kubernetes, Docker, and Swarm in any data center, cloud, network edge or IIOT device.
- Manage your Linux by GUI: Inspect and change network settings, Configure a firewall, Manage storage, Browse and search system logs, Inspect a system’s hardware, Inspect and interact with systemd-based services,
- Supported languages: English, Chinese（中文）

## Containers

Instead of reinventing the wheel, we integrate the best open source products into our interface so that customers don't have to learn new technology stacks or worry about the lack of maintenance of container components

- [Cockpit ](https://cockpit-project.org/): A web-based graphical interface for servers
- [Docker](https://www.docker.com/): Accelerate how you build, share, and run modern applications
- [Nginx Proxy Manager](https://nginxproxymanager.com/): A web-based Nginx management
- [Portainer](https://www.portainer.io/): Powerful container management for DevSecOps
- [Duplicati](https://www.duplicati.com/): Backup software to store encrypted backups online
- [Redis](https://redis.io/): The open source, in-memory data store
- [Appmanage](https://github.com/Websoft9/websoft9/tree/main/appmanage): API for manage docker compose based application powered by Wesoft9

# Install

## Installation

```
# when you have no root privileges
sudo su
wget https://websoft9.github.io/websoft9/install/install.sh && bash install.sh online
```

## Upgrade

```
# when you have no root privileges
sudo su
curl https://websoft9.github.io/websoft9/install/update.sh | bash
```

# Contributing

- websoft9 appmanage
- websoft9 docker-compose

# License

[LGPL-3.0](/License.md), Additional Terms: It is not allowed to publish free or paid image based on this repository in any Cloud platform's Marketplace without authorization (未经授权许可，不允许将基于本项目创建的镜像到云平台市场上售卖)
