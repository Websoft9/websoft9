# Dev-Setup

## Development runtime

You can use Windows/Linux/Mac for AppMange development if you have Docker and Python3.8 on you machine.

Then running below commands for development rutime:

```
git clone --depth=1 https://github.com/Websoft9/websoft9.git
cd websoft9/appmanage
pip install -r requirements.txt
```

You should fork this repository and push your branch to remote repository.

## Deployment

This repository only support deployment on Linux:

1. Install websoft9 on you Linux
   ```
   wget https://websoft9.github.io/websoft9/install/install.sh && bash install.sh
   ```
2. **git clone** your remote repository, and build your AppManage container and running it
   ```
   cd websoft9/appmanage && docker build -t websoft9dev/appmanage:latest-pr .
   cd websoft9/docker/appmanage && export APP_VERSION=latest-pr && docker compose up -d
   ```

## Structure

### API

```
├── api
│   ├── exception
│   ├── model -- Data models and database schema
│   ├── service -- Controllers
│   ├── utils -- Common modules and tools
│   └── v1 -- Views
```

### Route

New API use apps.router, don't create a new route

### Post method

Support [get,post] submit

### API URL

Access API by: **http://Internet IP:5000/docs**

### Test Automation

Coming soon...
