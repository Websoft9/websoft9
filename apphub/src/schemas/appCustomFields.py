from typing import Optional
from pydantic import BaseModel, Field


class AppCustomFieldItem(BaseModel):
    field_name: str = Field("", description="Field name")
    field_value: str = Field("", description="Field value")
    field_type: str = Field("text", description="Field type: text or password")


class AppCustomFieldResponse(AppCustomFieldItem):
    id: int = Field(0, description="Field ID")


class AppCustomFieldsRequest(BaseModel):
    fields: list[AppCustomFieldItem] = Field(default_factory=list, description="Custom fields to save")
