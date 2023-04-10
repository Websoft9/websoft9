## API结构

### 请求

### 请求头（公共参数）
| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| Version   | appmanae接口版本 | string   |必须   |
| Language | 接口显示语言 | string   |必须  |

 > 接口调用安全验证：通过nginx

### 请求主体

[各个接口业务参数](#API 接口说明)



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
  "ResponseData": {
  "Error": {
            "Code": "AuthFailure.SignatureFailure",
            "Message": "The provided credentials could not be validated. Please check your signature is correct."
           }
}
```

## API 接口说明

### app 列表查询接口

