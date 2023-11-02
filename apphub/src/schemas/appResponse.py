from pydantic import BaseModel
from typing import List, Any
from pydantic import BaseModel, Field
from typing import Optional

class AppResponse(BaseModel):
    app_id: str=Field("", description="App ID",example="wordpress")
    endpointId: int=Field(-1, description="Endpoint ID(-1:Not install on app store)",example=1)
    app_name: Optional[str]=Field(None, description="App name",example="wordpress")
    app_port: Optional[int] = Field(None, description="App port", example=80)
    app_dist: Optional[str]=Field(None, description="App dist",example="community")
    app_version: Optional[str]=Field(None, description="App version",example="1.0.0")
    app_official: bool=Field(True, description="App official",example=True)              
    proxy_enabled: bool=Field(False, description="Proxy enabled",example=False)
    status: int=Field(0, description="App status(0:unknown,1:active,2:inactive)",example=0)
    creationDate: Optional[int]=Field(None, description="Creation date",example=0)
    domain_names: List[dict]=Field([], description="Domain names")
    env: dict[str, Any] = Field({}, description="Environment variables")
    gitConfig: dict[str, Any] = Field({}, description="Git configuration")
    containers: List[dict]  = Field([], description="Containers")
    volumes: List[dict] = Field([], description="Volumes")
