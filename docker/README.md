# Docker

## Test it

All backend services of Websoft9 is packaged to Docker image, just these steps you can running them:  

```
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && sudo systemctl enable docker && sudo systemctl start docker
sudo docker network create websoft9
wget https://websoft9.github.io/websoft9/docker/.env
wget https://websoft9.github.io/websoft9/docker/docker-compose.yml
sudo docker compose -p websoft9 up -d
```
 > If you want only want to change to development, you should execute following commands:
 ```
 sudo docker compose -p websoft9 down -v
 wget https://websoft9.github.io/websoft9/docker/docker-compose-dev.yml
 # /data/source is development sources path in host
 docker compose -f docker-compose-dev.yml -p websoft9 up -d --build
 ```

## Develop it

The folder **apphub, deployment, git, proxy** stored development files, and used for:  

- Optimize dockerfile
- Release version
- Build docker image by Githuh action

## Runtime Skeleton

Current delivery still uses multiple containers through `docker-compose.yml`, but Story 1.3 defines the convergence contract for the next runtime phase.

- The single-container target contract now lives in `docker/deployment/single-container-runtime-skeleton.yaml`.
- The bootstrap phase skeleton now lives in `scripts/platform-entrypoint.sh`.
- The canonical health-entry skeleton is `scripts/platform-healthcheck.sh`.
- AppHub API and media are the required readiness processes; Gitea, Portainer, and Nginx Proxy Manager are explicit degraded-capable supporting processes until strict health is requested.
- The runtime contract keeps native service runtimes instead of collapsing the platform into one binary.