from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AppAvailableResponse(BaseModel):
    sys: Dict[str, str] = Field(..., description="id", json_schema_extra={"example": {"id": "2KY3eyxKkWDp2ZDTS66aP4"}})
    key: Optional[str] = Field(..., description="Key", json_schema_extra={"example": "wordpress"})
    hot: Optional[int] = Field(0, description="Hot", json_schema_extra={"example": 1000})
    trademark: Optional[str] = Field(None, description="Trademark", json_schema_extra={"example": "WordPress"})
    summary: Optional[str] = Field(
        None,
        description="Summary",
        json_schema_extra={
            "example": "WordPress is a free and open-source content management system written in PHP and paired with a MySQL or MariaDB database."
        },
    )
    overview: Optional[str] = Field(
        None,
        description="Overview",
        json_schema_extra={
            "example": "WordPress is a free and open-source content management system written in PHP and paired with a MySQL or MariaDB database."
        },
    )
    websiteurl: Optional[str] = Field(None, description="Website URL", json_schema_extra={"example": "https://wordpress.org/"})
    screenshots: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Screenshots",
        json_schema_extra={
            "example": [
                {
                    "id": "8248371f-a25f-4ae6-82be-7c6d8f7b9bb0",
                    "key": "gui start",
                    "value": "https://libs.websoft9.com/Websoft9/DocsPicture/zh/gogs/gogs-guistart-websoft9.png",
                }
            ]
        },
    )
    distribution: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Distribution",
        json_schema_extra={"example": [{"id": "ff8ceafb-dd7f-4dfc-b523-f13edefa88a7", "key": "Community", "value": "0.13"}]},
    )
    vcpu: Optional[int] = Field(None, description="VCPU", json_schema_extra={"example": 1})
    memory: Optional[int] = Field(None, description="Memory(GB)", json_schema_extra={"example": 1})
    storage: Optional[int] = Field(None, description="Storage(GB)", json_schema_extra={"example": 1})
    logo: Dict[str, str] = Field(
        default_factory=dict,
        description="Logo",
        json_schema_extra={"example": {"imageurl": "https://libs.websoft9.com/Websoft9/logo/product/gogs-websoft9.png"}},
    )
    catalogCollection: Dict[str, Any] = Field(
        default_factory=dict,
        description="Catalog Collection",
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "key": "repository",
                        "title": "Code Repository",
                        "catalogCollection": {"items": [{"key": "itdeveloper", "title": "IT Developer"}]},
                    }
                ]
            }
        },
    )
    settings: Optional[Dict[str, str]] = Field(None, description="Default installation settings")
    is_web_app: Optional[bool] = Field(None, description="Whether the app accepts a web address")
    profiles: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Available installation profiles")
    help: Optional[Dict[str, str]] = Field(None, description="Application installation guidance")
