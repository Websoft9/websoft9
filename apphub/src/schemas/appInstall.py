import re
from typing import Optional, List
from pydantic import BaseModel, Field, validator

from src.core.exception import CustomException

class Edition(BaseModel):
    dist: str = Field(..., description="The edition of the app",examples=["community"])
    version: str  = Field(..., description="The version of the app",examples=["1.0.0","latest"])

    @validator('dist')
    def validate_dist(cls, v):
        if v != 'community':
            raise CustomException(400,"Invalid Request","'dist' must be 'community'.")
        return v
    
    @validator('version')
    def validate_fields(cls, v):
        if not v.strip():
            raise CustomException(400,"Invalid Request","'version' cannot be empty.")
        return v

class appInstall(BaseModel):
    app_name: str = Field(...,description="The name of the app",examples=["wordpress","mysql"])
    edition: Edition = Field(..., description="The edition of the app", example={"dist":"community","version":"1.0.0"})
    app_id: str = Field(...,description="The custom identifier for the application. It must be a combination of 2 to 20 lowercase letters and numbers, and cannot start with a number.", example="wordpress")
    proxy_enabled: bool = Field(..., 
        description="""Whether to enable proxy for the app:  
        If true,the app will be accessed through the proxy server,  
        If false, the app will be accessed through the port of the host machine.""", example=True)
    domain_names: Optional[List[str]] = Field(..., 
        description="""The domain or IP for the app:  
        If proxy_enabled is true, provide the domain name.The first domain name will be used as the primary domain name.(e.g., ["wordpress.example1.com", "wordpress.example2.com"])
        If proxy_enabled is false, provide the host machine's IP address.(e.g., ["192.168.1.1"])""",
        example=["wordpress.example1.com", "wordpress.example2.com"])
    settings: Optional[dict] = Field(None, description="The settings for the app", example={"W9_HTTP_PORT_SET": "9001"})
   
    @validator('app_name')
    def validate_app_name(cls, v):
        if not v.strip():
            raise CustomException(400,"Invalid Request","'app_name' cannot be empty.")
        return v

    @validator('app_id')
    def validate_app_id(cls, v):
        pattern = re.compile("^[a-z][a-z0-9]{1,19}$")
        if not pattern.match(v):
            raise CustomException(400,"Invalid Request","The app_id must be a combination of 2 to 20 lowercase letters and numbers, and cannot start with a number.")
        return v
    
    @validator('domain_names', each_item=True)
    def validate_domain_name(cls, v):
        if not v.strip():
            raise CustomException(400,"Invalid Request","domain_names' cannot be empty string.")
        return v
    
    @validator('domain_names')
    def validate_domain_names(cls, v,values):
        if not v:
            raise CustomException(400,"Invalid Request","domain_names' cannot be empty.")
        
        if 'proxy_enabled' in values:
            if not values['proxy_enabled'] and v and len(v) > 1:
                raise CustomException(400,"Invalid Request","When proxy is disabled, you can only provide one IP address.")
            
            if v and len(set(v)) != len(v):
                raise CustomException(400,"Invalid Request","Duplicate entries found in 'domain_names'. All domains must be unique.")
        return v