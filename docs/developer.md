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

## Cockpit 插件

待补充。。。
