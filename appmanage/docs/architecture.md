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

- installing: 创建中
- running: 运行中
- exited: 停止
- restarting: 异常
- failed: 创建失败（docker compose 中的 created || RQ 返回失败）
