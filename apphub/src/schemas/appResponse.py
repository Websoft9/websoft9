from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AppResponse(BaseModel):
    app_id: str = Field("", description="App ID", json_schema_extra={"example": "wordpress"})
    tracking_id: Optional[str] = Field(
        None,
        description="Tracking ID for transient install tasks",
        json_schema_extra={"example": "d290f1ee-6c54-4b01-90e6-d701748f0851"},
    )
    endpointId: int = Field(-1, description="Endpoint ID(-1:Not install on app store)", json_schema_extra={"example": 1})
    app_name: Optional[str] = Field(None, description="App name", json_schema_extra={"example": "wordpress"})
    logo_url: Optional[str] = Field(
        None,
        description="Logo image URL returned by the API when available",
        json_schema_extra={"example": "https://libs.websoft9.com/app/wordpress/logo.png"},
    )
    app_dist: Optional[str] = Field(None, description="App dist", json_schema_extra={"example": "community"})
    app_version: Optional[str] = Field(None, description="App version", json_schema_extra={"example": "1.0.0"})
    app_official: bool = Field(True, description="App official", json_schema_extra={"example": True})
    is_compose_app: bool = Field(
        False, description="Whether this is a custom compose app (non-marketplace)", json_schema_extra={"example": True}
    )
    is_php_app: bool = Field(
        False, description="Whether the app belongs to the PHP capability list", json_schema_extra={"example": True}
    )
    is_monitor_app: bool = Field(
        False, description="Whether the app belongs to the monitor capability list", json_schema_extra={"example": False}
    )
    proxy_enabled: bool = Field(False, description="Proxy enabled", json_schema_extra={"example": False})
    status: int = Field(
        0,
        description="App status(0:unknown,1:active,2:inactive,3:installing,4:error,6:cancelled)",
        json_schema_extra={"example": 0},
    )
    creationDate: Optional[int] = Field(None, description="Creation date", json_schema_extra={"example": 0})
    domain_names: List[dict] = Field([], description="Domain names")
    env: dict[str, Any] = Field({}, description="Environment variables")
    gitConfig: dict[str, Any] = Field({}, description="Git configuration")
    containers: List[dict] = Field([], description="Containers")
    volumes: List[dict] = Field([], description="Volumes")
    error: Optional[str] = Field(None, description="Error message", json_schema_extra={"example": "Internal Server Error"})
    logs: Optional[List[Any]] = Field(
        default_factory=list,
        description="Logs",
        json_schema_extra={"example": ["Simple log message", {"status": "Installing...", "id": "db01ae396f16"}]},
    )
    phase: Optional[str] = Field(None, description="Current installation phase")
    cancel_requested: bool = Field(False, description="Whether image pull cancellation was requested")
