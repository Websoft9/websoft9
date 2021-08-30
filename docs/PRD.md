# 概述

StackHub主要架构和技术选型如下：
架构：后台JS框架+后端Python提供API服务
后端：Python, Docker, Docker-compose, FastAPI, Typer

## 后端接口说明

### App安装接口（installApp）

#### 接口地址

http://ip:port/installApp

#### 访问方式

Http（get/post）


#### 接口参数

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| appName       | 安装app的名称|  str  |可选  |

#### 返回数据

| 变量名       | 说明       | 类型  | 备注  |
| ------------ | ------------ | ----- |----- |
| code       | 接口是否调用成功标志|  str  |"0":失败 "1":成功   |
| message       | 接口返回信息|  str  |如接口调用成功时返回"appName 安装成功"  |