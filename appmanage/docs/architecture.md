# appmanage

![image](https://user-images.githubusercontent.com/43192516/231104572-a57940b1-273b-4761-ae82-7139a8966f70.png)


## RQ 

### 设计

RQ 用于异步处理**创建应用**的事务任务，需保证任务成功或失败后续处理。

它提供的状态有：  

- creating: 创建中
- failed: 创建失败


### RQ status

RQ 主要解决创建应用的状态

![image](https://user-images.githubusercontent.com/43192516/231103506-22bbfc80-f31f-4ba0-a331-4a05a345ec25.png)

## docker compose status

- running: 运行中
- exited: 停止
- restarting: 重启
- created: 创建失败

## API status

- installing(创建中): 来源于 RQ 的queue或StartedJobRegistry， 可进行操作[无法进行任何操作]
- running(运行中):  来源于docker compose，可进行操作[所有操作]
- exited(停止):   来源于docker compose，可进行操作[Start,Restart,Uninstall,日志查看]
- restarting(反复重启):  来源于docker compose，可进行操作[Stop,Restart,Uninstall,日志查看]
- failed(失败): 来源于 docker compose 中的 created || RQ 的 FailedJobRegistry 可进行操作[Uninstall]
