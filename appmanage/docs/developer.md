## API结构

### 请求

### 请求头（公共参数）
| 参数名称 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| Version   | appmanae接口版本 | string   |必须   |
| Language | 接口显示语言 | string   |必须  |

 > 接口调用安全验证：通过nginx

### 请求主体

各个接口业务参数



### 响应结果

### 响应头（公共参数）
|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| HTTP状态码   | 判断接口调用是否成功（200或404） | Integer   |必须   |

### 响应主体
|返回参数 | 用途                                          |类型  |必要性 |
| ------ | --------------------------------------------- | ------ |------ |
| HTTP状态码   | 判断接口调用是否成功（200或404） | Integer   |必须   |

HTTP状态码：接口调用成功统一返回 200，通过错误码区分
	{
        		"Response": {
            		"Error": {
               	 		"Code": "AuthFailure.SignatureFailure",
                		"Message": "The provided credentials could not be validated. Please check your signature is correct."
           			 },
           		 "RequestId": "ed93f3cb-f35e-473f-b9f3-0d451b8b79c6"
       	 	}
   	 }
	响应主体：
                api/v1/apps/list
                api/v1/user/list

                api/v1/AppsList
                api/v1/UsersList
                
