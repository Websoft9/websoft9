from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AppCatalogResponse(BaseModel):
    key: str = Field(..., description="Key", json_schema_extra={"example": "analytics"})
    position: Optional[int] = Field(0, description="Position", json_schema_extra={"example": 0})
    title: Optional[str] = Field(None, description="Title", json_schema_extra={"example": "Data Analytics"})
    linkedFrom: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Linked From",
        json_schema_extra={"example": {"items": [{"key": "itdeveloper", "title": "IT Developer"}]}},
    )
