# Dev-Setup

AppManage is based Python, and you should read the [Architecture docs](./architecture.md) if you want to contributing code for it.  

## Code format

You can refer to [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/) and use fomatter tool [Black](https://github.com/psf/black):

```
pip install black
black {source_file_or_directory}
```

## Test

You can test function,class,module and unit by automatic tools [Unittest](https://docs.python.org/3/library/unittest.html)


## Development runtime

You can use Windows/Linux/Mac for AppMange development if you have Docker and Python3.8 on you machine.

1. Prepare a Linux (not use WSL) instance for development

2. Connect your local IDE to Linux for codespace

3. Install websoft9 on you Linux
   ```
   wget https://websoft9.github.io/websoft9/install/install.sh && bash install.sh
   ```

4. Running below commands to create project on remote Linux

   ```
   git clone --depth=1 https://github.com/Websoft9/websoft9.git
   cd websoft9/appmanage
   pip install -r requirements.txt
   ```

5. Once you have change code, you should build your AppManage docker image and running it
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
