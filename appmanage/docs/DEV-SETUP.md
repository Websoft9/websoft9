# Dev-Setup

## Deployment

Install python3.6+ and Docker on your development environment, then 

```
pip install -r requirements.txt
docker build https://github.com/Websoft9/websoft9.git#main:appmanage -t websoft9dev/appmanage:latest-pr
docker network create websoft9
git clone https://github.com/Websoft9/websoft9.git && cd websoft9/docker/appmanage && export APP_VERSION=latest-pr && docker compose up -d
```

## API UI

Access API by: **http://Internet IP:5000/docs**

### Test Automation

Coming soon...
