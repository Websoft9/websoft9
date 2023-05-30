# API 设计文档

## API 结构

### 请求

#### 请求方式

支持如下两种调用方式：

- get
- post

#### 请求头（公共参数）

| 参数名称 | 用途         | 类型   | 必要性 |
| -------- | ------------ | ------ | ------ |
| Version  | 接口版本     | string | 可选   |
| Language | 接口显示语言 | string | 可选   |

#### 安全验证

本微服务没有安全验证模块，需通过 API 网关实现

#### 请求主体

[业务接口详情](#业务接口详情)

### 响应结果

#### 响应头（公共参数）

| 返回参数    | 用途                               | 类型    | 必要性 |
| ----------- | ---------------------------------- | ------- | ------ |
| HTTP 状态码 | 判断接口调用是否成功（200 或 404） | Integer | 必须   |

#### 响应主体

| 返回参数     | 用途                 | 类型                 | 必要性                 |
| ------------ | -------------------- | -------------------- | ---------------------- |
| ResponseData | 各个接口的业务数据   | object(依据接口而异) | 必须                   |
| Error        | 错误 code 和错误信息 | ErrorInfo            | 非必须 ,无错误时不返回 |

```
{
  "ResponseData": {
           app_id: "xxxx",
           StatusReason: {
              Code: "Requirement.NotEnough",
              Message: "Insufficient system resources (cpu, memory, disk space).",
              Detail: "Error detail information"
           }
          },
  "Error": {
            Code: "Requirement.NotEnough",
            Message: "Insufficient system resources (cpu, memory, disk space).",
            Detail: "Error detail information"
           }
}
```

#### 错误代码设计

错误代码参考 [AWS API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/errors-overview.html) 的分类方式：

- Client errors: These errors are usually caused by something the client did, such as specifying an incorrect or invalid parameter in the request, or using an action or resource on behalf of a user that doesn't have permission to use the action or resource. These errors are accompanied by a 400-series HTTP response code.

- Server errors: These errors are usually caused by an AWS server-side issue. These errors are accompanied by a 500-series HTTP response code.

##### Client errors

| code                                  | message        | detail |
| ------------------------------------- | -------------- | ------ |
| Client.Parameter.Blank.Error          | p 必填参数为空 | null   |
| Client.Parameter.Format.Error         | p 参数语法不符 | null   |
| Client.Parameter.Value.NotExist.Error | p 参数值错误   | null   |
| Client.Parameter.Value.Repeat.Error   | p 参数值重复   | null   |

##### Server errors

| code                   | message                | detail       |
| ---------------------- | ---------------------- | ------------ |
| Server.Container.Error | Docker 返回原始错误    | 错误详细信息 |
| Server.SystemError     | 系统原始错误           | 错误详细信息 |
| Server.\*\*\*          | 其他可以友好提示的错误 | 错误详细信息 |

## 业务接口详情

各个业务接口的详细说明，公共参数不在这里继续说明。

### App 安装

#### Action

AppInstall

#### 请求参数

| 参数名称          | 用途               | 类型   | 必要性 |
| ----------------- | ------------------ | ------ | ------ |
| app_name          | 应用名称           | string | 必须   |
| customer_app_name | 用户自定义应用名称 | string | 必须   |
| app_version       | 应用版本           | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | String(AppID) | 必须   |
| Error        | ErrorInfo     | 非必须 |

### App 卸载

#### Action

AppUninstall

#### 请求参数

| 参数名称 | 用途       | 类型   | 必要性 |
| -------- | ---------- | ------ | ------ |
| app_id   | 卸载该 app | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | String(AppID) | 必须   |
| error        | ErrorInfo     | 非必须 |

### App 重启

#### Action

AppRestart

#### 请求参数

| 参数名称 | 用途       | 类型   | 必要性 |
| -------- | ---------- | ------ | ------ |
| app_id   | 重启该 app | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | String(AppID) | 必须   |
| error        | ErrorInfo     | 非必须 |

### App 启动

#### Action

AppStart

#### 请求参数

| 参数名称 | 用途       | 类型   | 必要性 |
| -------- | ---------- | ------ | ------ |
| app_id   | 启动该 app | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | String(AppID) | 必须   |
| error        | ErrorInfo     | 非必须 |

### App 停止

#### Action

AppStop

#### 请求参数

| 参数名称 | 用途       | 类型   | 必要性 |
| -------- | ---------- | ------ | ------ |
| app_id   | 停止该 app | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | String(AppID) | 必须   |
| error        | ErrorInfo     | 非必须 |

### App 状态查询

#### Action

AppStatus

#### 请求参数

| 参数名称 | 用途              | 类型   | 必要性 |
| -------- | ----------------- | ------ | ------ |
| app_id   | 查询该 app 的信息 | string | 必须   |

#### 返回结果

| 返回值       | 类型          | 必要性 |
| ------------ | ------------- | ------ |
| ResponseData | AppStatusInfo | 必须   |
| error        | ErrorInfo     | 非必须 |

AppStatusInfo 说明:

```
{

  app_id：应用ID,

  status：应用运行状态,[installing(创建中)，running(运行中)，exited(停止)，restarting(反复重启)，failed(失败)]

  status_reason：{ // 只有failed时才有内容
    Code：错误代码
    Message：错误提示信息
    Detail：错误真实信息
  }
  
}
```

### App 列表查询

#### Action

AppList

#### 请求参数

| 参数名称 | 用途           | 类型   | 必要性 |
| -------- | -------------- | ------ | ------ |
| app_id   | 查询指定的 app | string | 非必须 |

#### 返回结果

| 返回值       | 类型                   | 必要性 |
| ------------ | ---------------------- | ------ |
| ResponseData | Array of AppDetailInfo | 必须   |
| error        | ErrorInfo              | 非必须 |

AppDetailInfo 说明:

```
{

  app_id：应用ID,

  name：应用名,

  customer_name：自定义应用名,

  trade_mark：应用商标,

  status：应用运行状态,[installing(创建中)，running(运行中)，exited(停止)，restarting(反复重启)，failed(失败)]

  status_reason：{ // 只有failed时才有内容
    Code：错误代码
    Message：错误提示信息
    Detail：错误真实信息
  },

  official_app：是否为官方应用,

  image_url：图片路径,

  running_info: { // 只有status=running才有值，其他时候为空

      port：应用端口,

      compose_file：docker compose文件路径,

      url：应用网址,

      admin_url：管理员网址,

      user_name：用户名,

      password：密码,

      default_domain: 默认域名,

      set_domain: 用户自定义域名,
  }
  
}
```
