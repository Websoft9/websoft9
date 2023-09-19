# Docker

## Test it

All backend services of Websoft9 is packaged to Docker image, if you have install Docker

```
sudo docker network create websoft9
wget https://websoft9.github.io/websoft9/docker/.env
wget https://websoft9.github.io/websoft9/docker/docker-compose.yml
sudo docker compose -p websoft9 up -d
```

## Develop it

The folder **apphub, deployment, git, proxy** stored development files, and used for:  

- Optimize dockerfile
- Release version
- Build docker image by Githuh action