[![](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/badges/main/pipeline.svg)](https://lab.frogg.it/lydra/yunohost/ansible-yunohost/-/pipelines)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)
[![GitHub last commit](https://img.shields.io/github/last-commit/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Release Date](https://img.shields.io/github/release-date/LydraFr/ansible-yunohost)](https://github.com/LydraFr/ansible-yunohost)
[![GitHub Repo stars](https://img.shields.io/github/stars/LydraFr/ansible-yunohost?style=social)](https://github.com/LydraFr/ansible-yunohost)

# What is Websoft9?

Websoft9 is web-based PaaS platform for running 200+ hot [open source application](https://github.com/Websoft9/docker-library/tree/main/apps) on your own server.

Websoft9 help you running multiple applications in a single server, that means we believe Microservices on single machine is reasonable. On the contrary, it becomes more and more valuable as computing power increases

Although the Cloud Native emphasizes high availability and clustering, but most of the time, applications do not need to implement complex clusters or K8S.

Websoft9's [architecture](https://github.com/Websoft9/websoft9/blob/main/docs/architecture.md) is simple, it did not create any new technology stack, and we fully utilize popular technology components to achieve our product goals, allowing users and developers to participate in our projects without the need to learn new technologies.

## Demos

You can see the sceenshoots below:

| ![image](https://github.com/Websoft9/websoft9/assets/16741975/8321780c-4824-4e40-997d-676a31534063) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/e842575b-60bc-4b0d-a57b-28c26b16196a) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/c598412a-9529-4286-ba03-6234d6da99b9) |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| ![image](https://github.com/Websoft9/websoft9/assets/16741975/7bed3744-1e9f-429e-8678-3714c8c262e2) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/a0923c69-2792-4cde-bfaf-bc018b61aee9) | ![image](https://github.com/Websoft9/websoft9/assets/16741975/901efd1c-31a0-4b31-b79c-fc2d441bb679) |

## Features

- Applications listing
- Install 200+ template applications without any configuration
- Web-based file browser to manage files and folder
- Manage user accounts
- Use a terminal on a remote server in your local web browser
- Nginx gui for proxy and free SSL with Let's Encrypt
- Deploy, configure, troubleshoot and secure containers in minutes on Kubernetes, Docker, and Swarm in any data center, cloud, network edge or IIOT device.
- Manage your Linux by GUI: Inspect and change network settings, Configure a firewall, Manage storage, Browse and search system logs, Inspect a system’s hardware, Inspect and interact with systemd-based services,
- Supported languages: English, Chinese（中文）

# Install & Upgrade

You should have root privileges user to install or upgrade Websoft9, if you use no-root user you can `sudo su` for it

```
# Install by default
curl https://websoft9.github.io/websoft9/install/install.sh | bash


# Install Websoft9 special version by development artifact and install path at /data/websoft9/source ...
wget https://websoft9.github.io/websoft9/install/install.sh &&  bash install.sh --port 9000 --channel dev --path "/data/websoft9/source" --version "0.8.25"
```
After installation, access it by: **http://Internet IP:9000** and using **Linux user** for login

# Contributing

Follow the [contributing guidelines](CONTRIBUTING.md) if you want to propose a change in the Websoft9 core. For more information about participating in the community and contributing to the Websoft9 project, see [this page](https://support.websoft9.com/docs/community/contributing).

- Documentation for [Websoft9 core maintainers](docs/MAINTAINERS.md)
- Documentation for application templates based on Docker maintainers is in the [docker-library](https://github.com/Websoft9/docker-library).
- [Articles promoting Websoft9](https://github.com/Websoft9/websoft9/issues/327)

# License

Websoft9 is licensed under the [LGPL-3.0](/License.md), and additional Terms: It is not allowed to publish free or paid image based on this repository in any Cloud platform's Marketplace without authorization