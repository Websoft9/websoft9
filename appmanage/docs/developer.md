# API设计文档

## API结构

### 请求

### 请求头（公共参数）

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| Version   | 接口版本 | string   |必须   |
| Language | 接口显示语言 | string   |必须  |

 > 接口调用安全验证：通过 API 网关

### 请求主体

[详细参照各个接口业务参数](#API接口说明)


### 响应结果

#### 响应头（公共参数）

|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| HTTP状态码   | 判断接口调用是否成功（200或404） | Integer   |必须   |

#### 响应主体

|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| ResponseData   | 各个接口的业务数据 | object(依据接口而异)   |必须   |
| Error   | 错误code和错误信息 | ErrorInfo   | 非必须 ,无错误时不返回  |

```
{
  "ResponseData": {app_id: "xxxx"},
  "Error": {
            "Code": "Requirement.NotEnough",
            "Message": "Insufficient system resources (cpu, memory, disk space).",
            "Detail": "Error detail information"
           }
}
```

#### 公共错误代码

| code                                          |message  |  detail |
| --------------------------------------------- | ------ | ------ |
| Container.Command.Error   | Docker 返回错误，联系支持：https://support.websoft9.com   |错误详细信息   |
| SystemError   | 系统错误，联系支持：https://support.websoft9.com   | 错误详细信息   |


## API接口说明

各个业务接口的详细说明，公共参数不在这里继续说明。

### app 安装

#### Action

AppInstall

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_name   | 应用名称 | string   |必须   |
| customer_app_name   | 用户自定义应用名称 | string   |必须   |
| app_version | 应用版本 | string   |必须   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | String(AppID)   |必须   |
| Error   | ErrorInfo   |非必须   |

ErrorInfo 说明:

| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.AppName.Blank   | APP名称为空   |
| Param.AppName.NotExis  | 不支持安装指定的App   |
| Param.CustomerAppName.Blank   | 用户自定义APP名称为空   |
| Param.CustomerAppName.FormatError   | 用户自定义APP名称只能是数字和小写字母组成    |
| Param.CustomerAppName.Repeat   | 已经安装了此应用，请重新指定APP名称   |
| Param.CustomerAppName.Wait   | 同名应用已经在安装等待中，请重新指定APP名称   |
| Param.AppVersion.Blank  | 安装App的版本不能为空   |
| Requirement.NotEnough| 系统资源（cpu，内存，磁盘空间）不足   |


### app 卸载

#### Action

AppUninstall

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_id   | 卸载该app | string   |必须   |
| delete_image   | 是否删除镜像 | boolean   |非必须，默认为False   |
| delete_data   | 是否删除所有数据 | boolean   |非必须，默认为True   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | String(AppID)   |必须   |
| error   | ErrorInfo   |非必须   |


ErrorInfo 说明:

| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.APPID.Blank   | APP_ID 不能为空   |
| Param.APPID.FormatError   | APP_ID 只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |


### App 重启

#### Action

AppRestart

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_id   | 重启该app | string   |必须   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | String(AppID)   |必须   |
| error   | ErrorInfo   |非必须   |


ErrorInfo 说明:

| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.APPID.Blank   | APP_ID不能为空   |
| Param.APPID.FormatError   | APP_ID只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |


### App 启动

#### Action

AppStart

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_id   | 启动该app | string   |必须   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | String(AppID)   |必须   |
| error   | ErrorInfo   |非必须   |


ErrorInfo 说明:
| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.APPID.Blank   | APP_ID不能为空   |
| Param.APPID.FormatError   | APP_ID只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |


### App 停止

#### Action

AppStop

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_id   | 停止该app | string   |必须   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | String(AppID)   |必须   |
| error   | ErrorInfo   |非必须   |


ErrorInfo 说明:
| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.APPID.Blank   | APP_ID不能为空   |
| Param.APPID.FormatError   | APP_ID只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |

### app 状态查询

#### Action

AppStatus

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_id   | 查询该app的信息 | string   |必须   |

#### 返回结果

| 返回值 |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | AppStatusInfo   |必须   |
| error   | ErrorInfo   |非必须   |

AppStatusInfo 说明:
```
{

  app_id：应用ID,

  name：应用名,

  customer_name：自定义应用名,

  trade_mark：应用商标,

  status_code：应用运行状态码,（queuing:'00',pulling:'10'，creating:'11'，initing:'12'，running:'30'，stop：'40'，error：'50'）

  status：应用运行状态,（queuing:排队等待,pulling:镜像拉取中，creating:容器启动中，initing:初始化中，running:正常运行，stop：停止，error：错误）
  
  official_app：是否为官方应用,
  
  image_url：图片路径
  
}
```

ErrorInfo 说明:

| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.APPID.Blank   | APP_ID 不能为空   |
| Param.APPID.FormatError   | APP_ID 只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |


### app 列表查询

#### Action

AppList

#### 请求参数

| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| customer_app_name   | 查询指定的 customer_app_name | string   | 非必须   |

#### 返回结果

| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | Array of AppDetailInfo   |必须   |
| error   | ErrorInfo   |非必须   |

AppDetailInfo 说明:
```
{

  app_id：应用ID,

  name：应用名,

  customer_name：自定义应用名,

  trade_mark：应用商标,

  status_code：应用运行状态码,（queuing:'00',pulling:'10'，creating:'11'，initing:'12'，running:'30'，stop：'40'，error：'50'）

  status：应用运行状态,（queuing:排队等待,pulling:镜像拉取中，creating:容器启动中，initing:初始化中，running:正常运行，stop：停止，error：错误）
  
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

ErrorInfo 说明:


| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.CustomerAppName.FormatError   | 用户自定义APP名称只能是数字和小写字母组成    |
