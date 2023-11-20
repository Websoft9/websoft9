from pydantic import BaseModel, Field, HttpUrl

class NginxProxyManagerSetting(BaseModel):
    base_url: HttpUrl = Field(..., title="The base url for nginx proxy manager")
    user_name: str = Field(..., title="The user name for nginx proxy manager")
    user_pwd: str = Field(..., title="The user password for nginx proxy manager")

class GiteaSetting(BaseModel):
    base_url: HttpUrl = Field(..., title="The base url for gitea")
    user_name: str = Field(..., title="The user name for gitea")
    user_pwd: str = Field(..., title="The user password for gitea")

class PortainerSetting(BaseModel):
    base_url: HttpUrl = Field(..., title="The base url for portainer")
    user_name: str = Field(..., title="The user name for portainer")
    user_pwd: str = Field(..., title="The user password for portainer")

class ApiKeySetting(BaseModel):
    key: str = Field(..., title="The api key")

class Domain(BaseModel):
    wildcard_domain: str = Field(None, title="The domain name")

class Cockpit(BaseModel):
    port: int = Field(..., title="The port of cockpit")

class AppSettings(BaseModel):
    nginx_proxy_manager: NginxProxyManagerSetting
    gitea: GiteaSetting
    portainer: PortainerSetting
    api_key: ApiKeySetting
    domain: Domain
    cockpit: Cockpit