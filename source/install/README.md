# Install

- The [install.sh](./install.sh) is the entry file for install or upgrade
- You can separate running the [install_cockpit.sh](./install_cockpit.sh), [install_docker.sh](./install_docker.sh), [install_plugins.sh](./install_plugins.sh) also
- The [uninstall.sh](./install.sh) is the entry file for uninstall


## User it

```
# install or upgrade Websoft9
wget -O install.sh https://websoft9.github.io/websoft9/install/install.sh && bash install.sh

# install or upgrade Websoft9 with parameters
wget -O install.sh https://websoft9.github.io/websoft9/install/install.sh && bash install.sh --port 9000 --channel release --path "/data/websoft9/source" --version "latest"

# install or upgrade Cockpit with parameters
wget -O - https://websoft9.github.io/websoft9/install/install_cockpit.sh | bash --port 9000

# install or upgrade Docker
wget -O - https://websoft9.github.io/websoft9/install/install_docker.sh | bash

# uninstall by default
curl https://websoft9.github.io/websoft9/install/uninstall.sh | bash

# uninstall all
wget -O - https://websoft9.github.io/websoft9/install/uninstall.sh | bash /dev/stdin --cockpit --files
```

## Develop it

This install script have below related resources:

- Tools: Install or upgrade some useful software packages at Linux
- Source Code: Download source code from artifactory
- Docker: Install and upgrade Docker, compose up **backend service** with docker-compose.yml
- Cockpit: Install and upgrade Cockpit and its Packages, manage it port, fix it menu
- Plugins: Install and upgrade Websoft9 plugins which is the **frontend**
- Systemd: Install and upgrade websoft9.serivce
- Set Firewalld: let 80,443 and Cockpit port allowed, Cockpit and Docker service with firewalld

The install script should adhere to the following principles:

1. Not allowed to modify the source code of the application.
2. Every task must have an exception exit mechanism.
3. Both installation and updates should be considered simultaneously.
4. Upgrade script should not overwrite existing configurations.
5. Duplication of codes in any form is not allowed, it must used function.
6. Paths, ports, etc. must be defined using variables.


Some default parameters you should know:

- Websoft9 root path：*/data/websoft9/source* 
- Websoft9 Systemd script path: */opt/websoft9/systemd*  
- Plugins path: */usr/share/cockpit*  
- Cockpit config path: */ect/cockpit* 
- Cockpit default port: 9000
