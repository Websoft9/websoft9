## API结构

### 请求
    请求头-公共参数：
         Version：HTTP 请求头：X-TC-Version
	 Language：HTTP 请求头：X-TC-Language
         接口调用安全验证：通过nginx
    请求主体：
          接口参数

### 返回结果
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
                
