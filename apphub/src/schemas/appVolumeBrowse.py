from pydantic import BaseModel, Field


class AppVolumeBrowseItem(BaseModel):
    name: str
    path: str
    item_type: str
    size: int = 0
    mode: str
    owner: str
    group: str
    accessed_at: int
    modified_at: int
    created_at: int
    text_viewable: bool = False


class AppVolumeBrowseTreeResponse(BaseModel):
    volume_name: str
    source_container: str
    current_path: str
    directory: AppVolumeBrowseItem
    truncated: bool = False
    items: list[AppVolumeBrowseItem]


class AppVolumeBrowseContentResponse(BaseModel):
    volume_name: str
    source_container: str
    path: str
    content: str