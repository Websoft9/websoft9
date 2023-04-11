# Administrator 管理手册

## 环境

### 安装组件

1. python环境
确保安装python3.6+

2. python的pip包fastapi,uvicorn[standard],gunicorn

```
pip install -r requirements.txt
```

3. 安装docker以及docker compose、创建docker 网络websoft9

### 启动

```
git clone https://github.com/Websoft9/StackHub.git && cd StackHub/docker/appmanage && docker compose up -d
```


