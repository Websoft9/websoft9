from typing import Dict, List

from pydantic import BaseModel, Field


class AppPhpInfoResponse(BaseModel):
    version: str = Field(..., description="Current PHP version", json_schema_extra={"example": "PHP 8.2.28"})
    modules: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="PHP modules grouped by section",
        json_schema_extra={"example": {"PHP Modules": ["curl", "json"], "Zend Modules": ["Zend OPcache"]}},
    )
