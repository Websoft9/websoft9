Ansible Role: Template
=========

This role is for you to install **Docker**, **Docker-Compose** and **some popular docker applications**.  

The applications includes:

* adminMongo - GUI tool for MongoDB
* Adminer - GUI tools for major DB
* Mongo-Express - GUI tool for MongoDB
* OnlyOffice Document Server - Office view and edit online middleware
* phpMyAdmin - GUI tool for MySQL
* phpPgAdmin - GUI tool for PostgreSQL
* Portainer - GUI tool for Docker

If you want this role to support more applications, you can [**submit Issues**](https://github.com/websoft9dev/role_docker/issues/new/choose) for us.

## Requirements

Make sure these requirements need before the installation:

| **Items**      | **Details** |
| ------------------| ------------------|
| Operating system | CentOS7.x Ubuntu18.04 |
| Python version | Python2  |
| Python components |  requests, docker-compose  |
| Runtime | No |

Note: 

1. python's requests need a suitable verion, otherwise Docker API may not available (ansible docker is based on Docker API).
2. Ansible Docker need to install docker-compose, but docker-compose have compatibility problem on Python2 or Python3, so this repository is not use ansible docker.

## Related roles

This Role does not depend on other role variables in syntax, but it depend on other role before:

```
roles:
  - { role: role_common }
  - { role：role_docker }
```


## Variables

The main variables of this Role and how to use them are as follows:

| **Items**      | **Details** | **Format**  | **Need to assignment** |
| ------------------| ------------------|-----|-----|
| docker_applications |install docker applications, e.g - adminmongo - onlyofficedocumentserver... | List | No |
| docker_addnetwork | add new network for docker, e.g "apps" | String| No |
| docker_apps_dir:  | set the applications's directory, e.g "/data/apps" | String | No |

Note: 

1. docker_applications is used to install more than two applications

## Example

```
docker_applications
  - phpmyadmin
  - adminmongo
  - onlyofficedocumentserver

docker_applications
  - phpmyadmin
  
docker_apps_dir: "/data/apps"
  
```

## License

[LGPL-3.0](/License.md), Additional Terms: It is not allowed to publish free or paid image based on this repository in any Cloud platform's Marketplace.

Copyright (c) 2016-present, Websoft9

## FAQ

#### Why did this project not use ansible's docker module?

The Ansible Docker module uses API to communicate with Docker, which is prone to errors. Therefore, enabling this module and directly using Docker commands are more stable and reliable, and you can be familiar with Docker commands. You don’t need to master the use of Ansible.

#### How to add new application of Docker?

You just need to add a docker compose file to the templates folder refer to /framework/apps-template-compose.yml
