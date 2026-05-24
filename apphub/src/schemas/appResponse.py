from typing import List, Any
from pydantic import BaseModel, Field
from typing import Optional

class AppResponse(BaseModel):
    app_id: str=Field("", description="App ID",example="wordpress")
    tracking_id: Optional[str]=Field(None, description="Tracking ID for transient install tasks", example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    endpointId: int=Field(-1, description="Endpoint ID(-1:Not install on app store)",example=1)
    app_name: Optional[str]=Field(None, description="App name",example="wordpress")
    logo_url: Optional[str]=Field(None, description="Logo image URL returned by the API when available", example="https://libs.websoft9.com/app/wordpress/logo.png")
    app_dist: Optional[str]=Field(None, description="App dist",example="community")
    app_version: Optional[str]=Field(None, description="App version",example="1.0.0")
    app_official: bool=Field(True, description="App official",example=True)              
    is_php_app: bool=Field(False, description="Whether the app belongs to the PHP capability list", example=True)
    is_monitor_app: bool=Field(False, description="Whether the app belongs to the monitor capability list", example=False)
    proxy_enabled: bool=Field(False, description="Proxy enabled",example=False)
    status: int=Field(0, description="App status(0:unknown,1:active,2:inactive,3:installing,4:error)",example=0)
    creationDate: Optional[int]=Field(None, description="Creation date",example=0)
    domain_names: List[dict]=Field([], description="Domain names")
    env: dict[str, Any] = Field({}, description="Environment variables")
    gitConfig: dict[str, Any] = Field({}, description="Git configuration")
    containers: List[dict]  = Field([], description="Containers")
    volumes: List[dict] = Field([], description="Volumes")
    error:Optional[str] = Field(None,description="Error message",example="Internal Server Error")
    logs: Optional[List[Any]] = Field(default_factory=list, description="Logs", example=["Simple log message", {"status": "Installing...", "id": "db01ae396f16"}])
