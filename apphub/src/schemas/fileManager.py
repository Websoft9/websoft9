from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _normalize_volume_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Volume ID cannot be empty")
    return normalized


def _normalize_path(value: Optional[str]) -> str:
    normalized = str(value or "/").strip()
    if not normalized:
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _normalize_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Name cannot be empty")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("Name cannot include path separators")
    if normalized in {".", ".."}:
        raise ValueError("Name cannot be '.' or '..'")
    return normalized


class FileManagerVolumeSummary(BaseModel):
    volume_name: str
    driver: str
    app_id: Optional[str] = None
    owner: Optional[str] = None


class FileManagerVolumesResponse(BaseModel):
    volumes: list[FileManagerVolumeSummary]


class FileManagerItem(BaseModel):
    name: str
    path: str
    item_type: str
    size: int = 0
    mode: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
    accessed_at: Optional[str] = None
    modified_at: Optional[str] = None
    created_at: Optional[str] = None
    text_editable: bool = False


class FileManagerDirectoryResponse(BaseModel):
    volume_name: str
    current_path: str
    metadata: Optional['FileManagerMetadataResponse'] = None
    items: list[FileManagerItem]


class FileManagerTextFileResponse(BaseModel):
    volume_name: str
    path: str
    content: str


class FileManagerMetadataResponse(BaseModel):
    volume_name: str
    name: str
    path: str
    item_type: str
    size: int = 0
    mode: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
    accessed_at: Optional[str] = None
    modified_at: Optional[str] = None
    created_at: Optional[str] = None
    text_editable: bool = False


class FileManagerWriteTextRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    path: str = Field(default="/", max_length=4096)
    content: str = Field(default="", max_length=1024 * 1024)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)


class FileManagerCreateFolderRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    parent_path: str = Field(default="/", max_length=4096)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("parent_path", mode="before")
    @classmethod
    def normalize_parent_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_name(value)


class FileManagerCreateFileRequest(FileManagerCreateFolderRequest):
    pass


class FileManagerRenameRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    source_path: str = Field(min_length=1, max_length=4096)
    target_name: str = Field(min_length=1, max_length=255)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("source_path", mode="before")
    @classmethod
    def normalize_source_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)

    @field_validator("target_name", mode="before")
    @classmethod
    def normalize_target_name(cls, value: str) -> str:
        return _normalize_name(value)


class FileManagerCopyItemRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    source_path: str = Field(min_length=1, max_length=4096)
    destination_path: str = Field(min_length=1, max_length=4096)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("source_path", "destination_path", mode="before")
    @classmethod
    def normalize_paths(cls, value: Optional[str]) -> str:
        return _normalize_path(value)


class FileManagerDeleteRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    path: str = Field(min_length=1, max_length=4096)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)


class FileManagerPermissionBits(BaseModel):
    read: bool = False
    write: bool = False
    execute: bool = False


class FileManagerUpdateAttributesRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    source_path: str = Field(min_length=1, max_length=4096)
    target_name: Optional[str] = Field(default=None, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=128)
    group: Optional[str] = Field(default=None, max_length=128)
    owner_permissions: FileManagerPermissionBits = Field(default_factory=FileManagerPermissionBits)
    group_permissions: FileManagerPermissionBits = Field(default_factory=FileManagerPermissionBits)
    other_permissions: FileManagerPermissionBits = Field(default_factory=FileManagerPermissionBits)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("source_path", mode="before")
    @classmethod
    def normalize_source_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)

    @field_validator("target_name", mode="before")
    @classmethod
    def normalize_target_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return _normalize_name(normalized)

    @field_validator("owner", "group", mode="before")
    @classmethod
    def normalize_identity_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class FileManagerMutationResponse(BaseModel):
    volume_name: str
    path: str
    operation: str


class FileManagerAttributesMutationResponse(FileManagerMutationResponse):
    metadata: FileManagerMetadataResponse


FileManagerDirectoryResponse.model_rebuild()


class FileManagerUploadRequest(BaseModel):
    volume_id: str = Field(min_length=1, max_length=256)
    parent_path: str = Field(default="/", max_length=4096)
    file_name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)

    @field_validator("volume_id", mode="before")
    @classmethod
    def normalize_volume_id(cls, value: str) -> str:
        return _normalize_volume_id(value)

    @field_validator("parent_path", mode="before")
    @classmethod
    def normalize_parent_path(cls, value: Optional[str]) -> str:
        return _normalize_path(value)

    @field_validator("file_name", mode="before")
    @classmethod
    def normalize_file_name(cls, value: str) -> str:
        return _normalize_name(value)
