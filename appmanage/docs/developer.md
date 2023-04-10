# API设计文档

## API结构

### 请求

### 请求头（公共参数）
| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| Version   | appmanage接口版本 | string   |必须   |
| Language | 接口显示语言 | string   |必须  |

 > 接口调用安全验证：通过nginx

### 请求主体

[详细参照各个接口业务参数](#API接口说明)



### 响应结果

### 响应头（公共参数）
|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| HTTP状态码   | 判断接口调用是否成功（200或404） | Integer   |必须   |

### 响应主体
|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| error   | 错误code和错误信息 | object   | 非必须 ,无错误时不返回  |
| responseData   | 各个接口的业务数据 | object   |必须   |

```
{
  "ResponseData": {app_id: "xxxx"},
  "Error": {
            "Code": "Requirement.NotEnough",
            "Message": "Insufficient system resources (cpu, memory, disk space)."
           }
}
```

## API接口说明

各个业务接口的详细说明，公共参数不在这里继续说明。

### app 安装接口

#### 请求URL

请求URL=FastAPI通用URL/AppInstall

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
| error   | ErrorInfo   |非必须   |


ErrorInfo 说明:
| code                                          |message  |
| --------------------------------------------- | ------ |
| Param.AppName.Blank   | APP名称为空   |
| Param.AppName.NotExis  | 不支持安装指定的App   |
| Param.CustomerAppName.Blank   | 用户自定义APP名称为空   |
| Param.CustomerAppName.FormatError   | 用户自定义APP名称只能是数字和小写字母组成    |
| Param.CustomerAppName.Repeat   | 已经安装了此应用，请重新指定APP名称   |
| Param.CustomerAppName.Wait   | 同名应用已经在安装等待中，请重新指定APP名称   |
| Requirement.NotEnough| 系统资源（cpu，内存，磁盘空间）不足   |
| Container.Command.Error   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |


### app 卸载接口

#### 请求URL

请求URL=FastAPI通用URL/AppUninstall

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
| Param.APPID.Blank   | APP_ID不能为空   |
| Param.APPID.FormatError   | APP_ID只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |
| Container.Command.Error   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |

### App 重启接口

#### 请求URL

请求URL=FastAPI通用URL/AppRestart

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
| Container.Command.Error   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |

### App 启动接口

#### 请求URL

请求URL=FastAPI通用URL/AppStart

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
| Container.Command.Error   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |

### App 停止接口

#### 请求URL

请求URL=FastAPI通用URL/AppStop

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
| Container.Command.Error   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |

### app 状态查询接口

#### 请求URL

请求URL=FastAPI通用URL/AppStatus

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
| Param.APPID.Blank   | APP_ID不能为空   |
| Param.APPID.FormatError   | APP_ID只能是数字和小写字母组成   |
| Param.APPID.NotExist   | APP不存在   |
| Container.CommandError   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |


### app 列表查询接口

#### 请求URL

请求URL=FastAPI通用URL/AppList

#### 请求参数
| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| app_name   | 查询app列表信息，当app_name不为空时，查询该app的信息 | string   |非必须   |

#### 返回结果
| 返回值  |类型  |必要性 |
| ------  | ------ |------ |
| ResponseData   | AppDetailInfo list   |必须   |
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
  }
  
}
```

ErrorInfo 说明:
| code                                          |message  |
| --------------------------------------------- | ------ |
| Container.CommandError   | 操作容器指令发生错误   |
| SystemError  |系统异常，请联系管理员（系统报错返回）   |
