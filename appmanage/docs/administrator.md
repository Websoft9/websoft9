# Administrator 管理手册

## 环境

### 安装组件

1. python 环境
   确保安装 python3.6+

2. python 的 pip 包 fastapi,uvicorn[standard],gunicorn

```
pip install -r requirements.txt
```

3. 安装 docker 以及 docker compose、创建 docker 网络 websoft9

### 启动

```
git clone https://github.com/Websoft9/stackhub.git && cd stackhub/docker/appmanage && docker compose up -d
```
