from typing import Optional

from pydantic import BaseModel, Field


class ProductEditionUpdateRequest(BaseModel):
    edition_key: str = Field(..., description="Target edition key")
    note: Optional[str] = Field(default=None, description="Optional support note")


class ProductEditionStateResponse(BaseModel):
    version: Optional[str] = Field(default=None, description="Current program version")
    edition_key: str = Field(..., description="Current effective edition key")
    edition_name: str = Field(..., description="Current effective edition display name")
    max_apps: Optional[int] = Field(default=None, description="Current effective max apps")
    state_source: str = Field(..., description="Runtime edition state source")
    updated_by: str = Field(..., description="Last updater")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    note: Optional[str] = Field(default=None, description="Optional support note")