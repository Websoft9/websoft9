from pydantic import BaseModel


class SettingsSummaryItem(BaseModel):
    group: str
    key: str
    value: str
    sensitive: bool = False
    masked: bool = False
    editable: bool = False


class SettingsSummaryGroup(BaseModel):
    id: str
    items: list[SettingsSummaryItem]


class SettingsSummaryResponse(BaseModel):
    groups: list[SettingsSummaryGroup]