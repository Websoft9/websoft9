from typing import Optional

from pydantic import BaseModel, Field


class PortSuggestItem(BaseModel):
    key: str = Field(..., title="Install setting key that needs a host port")


class PortSuggestRequest(BaseModel):
    ports: list[PortSuggestItem] = Field(..., title="Install setting keys in display order")


class PortSuggestResult(BaseModel):
    key: str = Field(..., title="Install setting key")
    port: Optional[int] = Field(None, title="Assigned free host port, None when the range is exhausted")


class PortSuggestResponse(BaseModel):
    suggestions: list[PortSuggestResult] = Field(..., title="Port suggestions aligned with the request order")


class PortCheckResult(BaseModel):
    port: int = Field(..., title="Checked host port")
    available: bool = Field(..., title="Whether the host port is free")
    reason: Optional[str] = Field(None, title="Claimed by: container or installing")


class PortCheckResponse(BaseModel):
    results: list[PortCheckResult] = Field(..., title="Port check results aligned with the request order")
