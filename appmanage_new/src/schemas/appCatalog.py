from typing import Any, Dict, List,Optional
from pydantic import BaseModel, Field

class AppCatalogResponse(BaseModel):
    key: str=Field(..., description="Key",example="analytics")
    position: Optional[int]=Field(0, description="Position",example=0)
    title: Optional[str]=Field(None, description="Title",example="Data Analytics")
    linkedFrom: Dict[str, Dict[str, Any]] = Field(..., description="Linked From",example={"items": [{"key": "itdeveloper","title": "IT Developer"}]})
