from typing import Any, Dict, List,Optional
from pydantic import BaseModel, Field

class AppAvailableResponse(BaseModel):
    sys: Dict[str, str] = Field(..., description="id",example={"id": "2KY3eyxKkWDp2ZDTS66aP4"})
    key: Optional[str] = Field(..., description="Key",example="wordpress")
    hot: Optional[int] = Field(0, description="Hot",example=1000)
    trademark: Optional[str] = Field(None, description="Trademark",example="WordPress")
    summary: Optional[str] = Field(None, description="Summary",example="WordPress is a free and open-source content management system written in PHP and paired with a MySQL or MariaDB database.")
    overview: Optional[str] = Field(None, description="Overview",example="WordPress is a free and open-source content management system written in PHP and paired with a MySQL or MariaDB database.")
    websiteurl: Optional[str] = Field(None, description="Website URL",example="https://wordpress.org/")
    screenshots: List[Dict[str, Any]] = Field(None, description="Screenshots",example=[{"id": "8248371f-a25f-4ae6-82be-7c6d8f7b9bb0","key": "gui start","value": "https://libs.websoft9.com/Websoft9/DocsPicture/zh/gogs/gogs-guistart-websoft9.png"}])
    distribution: List[Dict[str, Any]] = Field(None, description="Distribution",example=[{"id": "ff8ceafb-dd7f-4dfc-b523-f13edefa88a7","key": "Community", "value": "0.13"}])
    vcpu: Optional[int] = Field(None, description="VCPU",example=1)
    memory: Optional[int] = Field(None, description="Memory(GB)",example=1)
    storage: Optional[int] = Field(None, description="Storage(GB)",example=1)
    logo: Dict[str, str] = Field(None, description="Logo",example={"imageurl": "https://libs.websoft9.com/Websoft9/logo/product/gogs-websoft9.png"})
    catalogCollection: Dict[str, Any] = Field(None, description="Catalog Collection", example={"items": [{"key": "repository", "title": "Code Repository","catalogCollection": {"items": [{"key": "itdeveloper", "title": "IT Developer"}]}}]})
    