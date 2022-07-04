# 概述

StackHub主要架构和技术选型如下：
架构：后台JS框架+后端Python提供API服务  
后端：Python, Docker, Docker-compose, FastAPI, Typer
打包工具：[porter](https://porter.sh/)

## 后端接口说明

### 用户相关（登陆，退出，注册等 待讨论？）

### APP详情（是否共用websoft9主站信息 待讨论？）

### APP列表（是否共用websoft9主站信息 待讨论？）

### App安装接口（installApp）

#### 接口地址

http://ip:port/installApp

#### 访问方式

Http（get/post）
同步/异步：异步


#### 接口参数

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| appName       | 安装app的名称|  str  |必须  |

e.g.
```
{
    "appName":"redmine"
}
```
#### 返回数据

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| code       | 接口是否调用成功标志|  str  |"0":失败 "1":成功   |
| message       | 接口返回信息|  str  |如接口调用成功时返回"appName安装成功"  |
| data       | APP相关信息|  Json  |主容器名： websoft9-appName App端口: port(9001) |

e.g.  
```
{
    "code":"1",
    "message":"appName安装成功",
    "data":{
        "containerName": "websoft9-appName",
        "port": "9001",
        "db_port": "3307",
        "info": "XXXX"
    }
}
```

#### 接口主要内容

通过调用该接口，判断服务器是否已经存在websoft9-appName容器，如存在返回失败信息，并提示已经存在该App；如不存在，在服务器端启动一个名为websoft9-appName的容器以及相关容器，主容器以及相关容器的端口需要根据服务器状态动态设定。



### App卸载接口（uninstallApp）

#### 接口地址

http://ip:port/uninstallApp

#### 访问方式

Http（get/post）
同步/异步：同步

#### 接口参数

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| appName       | 卸载app的名称|  str  |必须 |

e.g.
```
{
    "appName":"redmine"
}
```

#### 返回数据

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| code       | 接口是否调用成功标志|  str  |"0":失败 "1":成功   |
| message       | 接口返回信息|  str  |如接口调用成功时返回"appName卸载成功"  |

e.g.
```  
{
    "code":"0",
    "message":"appName卸载失败，任然在运行，端口为9001，请ssh登陆如服务器后使用docker-ps查看，并手动停止容器"
}
```


### App状态查询接口（getAppInfo）

#### 接口地址

http://ip:port/getAppInfo

#### 访问方式

Http（get/post）
同步/异步：同步


#### 接口参数

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| appName       | 安装app的名称|  str  |必须  |

e.g.
```
{
    "appName":"redmine"
}
```
#### 返回数据

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| code       | 接口是否调用成功标志|  str  |"0":失败 "1":成功   |
| message       | 接口返回信息|  str  |如接口调用成功时返回"appName状态信息查询"  |
| data       | APP相关信息|  Json  |状态：启动成功  App端口: port(9001) |

e.g.  
```
{
    "code":"1",
    "message":"appName状态信息查询成功",
    "data":{
        "status": "0", // 0:未启动 1:启动成功 2：启动失败(状态信息不正常，将错误信息返回到info字段?)
        "port": "",
        "db_port": "",
        "info": ""
    }
}
```


### 客户已安装App状态查询接口（getAllAppInfo）？


### 卸载客户已安装App（uninstallAllApp）？


### 服务器状态查询接口（searchServer）

#### 接口地址

http://ip:port/searchServer

#### 访问方式

Http（get/post）
同步/异步：同步


#### 接口参数

无

#### 返回数据

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| code       | 接口是否调用成功标志|  str  |"0":失败 "1":成功   |
| message       | 接口返回信息|  str  |如接口调用成功时返回"服务器状态信息查询成功"  |
| data       | APP相关信息|  Json  |服务器各种信息，如cpu使用率，内存使用率，磁盘占有率 |

e.g.  
```
{
    "code":"1",
    "message":"服务器状态信息查询成功",
    "data":{
        "cpu": "10%", 
        "memory": "54%",
        "hdd": "",
        "risk": "3",
         ...
        "info": ""
    }
}
```
