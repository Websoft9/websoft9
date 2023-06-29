# Developer Guide

## Appmanage

### 开发环境以及组件

Python3.10, FastAPI, RQ, logging

### 关键技术实现

#### 日志分割

    ```
        logPath = 'logs/'
        if not os.path.exists(logPath):
            os.makedirs(logPath)
        logName = 'app_manage.log'
        logFile = logPath + logName
        formatter = logging.Formatter('%(asctime)s %(levelname)s:  %(message)s')
        # handler
        time_rotating_file_handler = handlers.TimedRotatingFileHandler(filename=logFile, when="MIDNIGHT", interval=1, encoding='utf-8')
        time_rotating_file_handler.setLevel(logging.DEBUG)
        time_rotating_file_handler.setFormatter(formatter)
    ```

#### RQ

任务管理器启动：

    ```
    rq worker --url redis://websoft9-redis:6379/0
    ```

RQ 队列创建：

    ```
    # 指定 Redis 容器的主机名和端口
    redis_conn = Redis(host='websoft9-redis', port=6379)

    # 使用指定的 Redis 连接创建 RQ 队列
    q = Queue(connection=redis_conn,default_timeout=3600)
    ```

RQ 队列新增排队任务：

```
q.enqueue(install_app_delay, app_name, customer_name, app_version, job_id=app_id)
```

获取队列中任务的信息：

```
# 获取 StartedJobRegistry 实例
started = StartedJobRegistry(queue=q)
finish = FinishedJobRegistry(queue=q)
deferred = DeferredJobRegistry(queue=q)
failed = FailedJobRegistry(queue=q)
scheduled = ScheduledJobRegistry(queue=q)
cancel = CanceledJobRegistry(queue=q)

# 获取正在执行的作业 ID 列表
run_job_ids = started.get_job_ids()
finish_job_ids = finish.get_job_ids()
wait_job_ids = deferred.get_job_ids()
failed_jobs = failed.get_job_ids()
scheduled_jobs = scheduled.get_job_ids()
cancel_jobs = cancel.get_job_ids()
```

### API 文档

[FastAPI 文档](https://github.com/Websoft9/StackHub/blob/main/appmanage/docs/developer.md) 使用 swagger 自动生成，访问地址：http://IP:PORT/docs。

## 版本管理

### 命名规则

[major:大版本].[minor:功能版本].[patch:Bug 修复版本]

- major 主版本号，软件架构或软件界面发生重大变化。
- minor 次版本号，软件功能新增或删减。
- patch 错误修复版本号，软件缺陷修复。

> 版本通过 release 发布时指定，主版本号小于 1 时为预发布(pre-release)

### 软件内部组件版本

Websoft9 的 release 的版本号由项目主版本号和各微服务和插件版本号以及操作系统依赖构成，参照 version.json 说明：

```
{
    "SERVICES": {
        "PORTAINER": "2.18.3", // portainer 版本号，即对应docker镜像的版本号
        "NGINX": "2.10.3",  // nginxproxymanager 版本号，即对应docker镜像的版本号
        "APPMANAGE": "0.7.0", // app管理后台 版本号，即对应docker镜像的版本号
        "REDIS": "7.0.11"  // app管理后台 版本号，即对应docker镜像的版本号
    },
    "PLUGINS": {
        "PORTAINER": "1.0.0", // cockpit插件 PORTAINER 版本号
        "NGINX": "1.0.0",   // cockpit插件 nginx 版本号
        "MYAPPS": "1.0.1", // cockpit插件 myapps 版本号
        "APPSTORE": "1.0.0" // cockpit插件 myapps 版本号
    },
    "LIBRARY": {
        "VERSION": "1.0.0" // app项目应用库 docker-library 版本号
    },
    "OS_SUPPORT": {
        "CentOS": ["7.9"],
        "Ubuntu": ["18.04","20.04","22.04"],
        "RedHat": ["7.9","8.6","9.2"]
    },
    "VERSION": "0.7.0" // StackHub项目版本号，上面所有组件的更新都会引起其版本更新
}
```

### 版本更新内容

通过项目下 CHANGELOG.md 来进行管理，格式如下：

```
## 0.3.0 release on 2023-06-06

1. appmanage docker 镜像更新到 0.3.0
2. 修复 prestashop 无法访问的 bug
3. 修复 odoo 无法安装的 bug

```

### 制品库管理

版本管理部仅仅是对代码的管理，还需要对软件可执行成果物-制品的管理，websoft9 项目会将所有成果作为公开制品。

#### 制品库选型

Dockerhub, Github packages, Azure artifacts, CODING 制品库

> 非容器类制品优先选择 Github packages

#### 制品库自动化

* 插件制品管理：开发人员开发测试完成后，修改插件版本，触发 Action 构建 Github packages 制品
* docker-libaray 库制品管理：开发人员测试完成后，修改 library 版本，触发 Action 构建 Github packages 制品
* websoft9 制品管理：开发人员修改 appmanage 源码或微服务 docker-compose 测试完成后，修改 微服务 版本，触发 Action 构建 Dockerhub 镜像制品以及后台微服务 Github packages 制品

> Portainer,redis,nginxproxymanager 使用外部 dockerhub 镜像

### 自动化测试

当各个制品更新后，项目管理者修改 version_test.json 对应的组件的版本，构建 Action 触发自动化系统测试。
自动化测试失败，通知各开发人员，删除制品，修改后重新生成制品。
自动化测试成功，同步 version_test.json 到 version.json， 新制品正式发布。

### 升级

升级主要分成软件商店升级和内核升级。

#### 软件商店升级

主要是软件商店插件更新后引起的升级。
当本地 appstore 版本小于最新 version.json 的版本时，升级 appstore 插件以及 library 制品。

#### 内核升级

内核升级会将所有组件升级到最新，除了软件商店升级外，还需要升级以下内容：

1. docker， cockpit 系统组件
2. 后台微服务容器
3. cockpit 对应插件

升级都会从制品库获取 version.json 对应版本的制品。

#### 升级限制

内核升级可能会因为架构系统等原因无法升级，在 version.json 中含有支持升级操作系统依赖，据此来判断是否能升级。

## Cockpit 插件

待补充。。。
