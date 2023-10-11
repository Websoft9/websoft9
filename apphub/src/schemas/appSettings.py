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

class DockerLibrarySetting(BaseModel):
    path: str = Field(..., title="The path of docker library")

class AppMediaSetting(BaseModel):
    path: str = Field(..., title="The path of app media")

class AppSettings(BaseModel):
    nginx_proxy_manager: NginxProxyManagerSetting
    gitea: GiteaSetting
    portainer: PortainerSetting
    docker_library: DockerLibrarySetting
    app_media: AppMediaSetting