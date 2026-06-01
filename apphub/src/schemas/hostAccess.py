from pathlib import PurePosixPath
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


HostAccessAuthMethod = Literal["password", "key"]
HostAccessFileViewMode = Literal["list", "grid"]


def _normalize_username(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Username cannot be empty")
    return normalized


def _normalize_host(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Host cannot be empty")
    return normalized


def _normalize_shell(value: str) -> str:
    normalized = str(value or "").strip()
    return normalized


def _normalize_optional_path(value: Optional[str]) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return str(PurePosixPath(normalized))


class HostAccessProfileUpsertRequest(BaseModel):
    profile_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=512)
    host: str = Field(min_length=1, max_length=255)
    auth_method: HostAccessAuthMethod = Field(default="password")
    username: str = Field(min_length=1, max_length=128)
    port: int = Field(default=22, ge=1, le=65535)
    password: str = Field(default="", max_length=4096)
    private_key: str = Field(default="", max_length=65535)
    passphrase: str = Field(default="", max_length=4096)
    working_directory: str = Field(default="", max_length=4096)
    shell: str = Field(default="", max_length=512)
    remember: bool = Field(default=True)
    is_default: bool = Field(default=False)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("host", mode="before")
    @classmethod
    def normalize_host(cls, value: str) -> str:
        return _normalize_host(value)

    @field_validator("shell", mode="before")
    @classmethod
    def normalize_shell(cls, value: str) -> str:
        return _normalize_shell(value)

    @field_validator("working_directory", mode="before")
    @classmethod
    def normalize_working_directory(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)

    @model_validator(mode="after")
    def validate_auth_secret(self):
        if self.auth_method == "password" and not self.password.strip():
            raise ValueError("Password cannot be empty when password authentication is selected")
        if self.auth_method == "key" and not self.private_key.strip():
            raise ValueError("Private key cannot be empty when key authentication is selected")
        return self


class HostAccessProfileResponse(BaseModel):
    configured: bool
    remembered: bool
    host: str = "172.17.0.1"
    port: int = 22
    local_host_ip: str = "172.17.0.1"
    active_profile_id: Optional[str] = None
    default_profile_id: Optional[str] = None
    auth_method: Optional[HostAccessAuthMethod] = None
    username: Optional[str] = None
    working_directory: Optional[str] = None
    shell: Optional[str] = None
    has_password: bool = False
    has_private_key: bool = False
    saved_profiles: list['HostAccessSavedProfileSummary'] = Field(default_factory=list)
    file_preferences: 'HostAccessFilePreferences' = Field(default_factory=lambda: HostAccessFilePreferences())


class HostAccessSavedProfileSummary(BaseModel):
    profile_id: str
    name: str = ""
    description: str = ""
    host: str
    username: str
    auth_method: HostAccessAuthMethod
    port: int = 22
    shell: str
    is_default: bool = False
    is_local: bool = False
    updated_at: Optional[str] = None
    has_password: bool = False
    has_private_key: bool = False


class HostAccessConnectionTestResponse(BaseModel):
    success: bool = True
    message: str
    host: str
    port: int
    username: str


class HostAccessFileItem(BaseModel):
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


class HostAccessFileMetadata(HostAccessFileItem):
    pass


class HostAccessFilePreferences(BaseModel):
    view_mode: HostAccessFileViewMode = Field(default='list')
    show_hidden_files: bool = Field(default=False)


class HostAccessFilePreferencesUpdateRequest(HostAccessFilePreferences):
    pass


class HostAccessDirectoryResponse(BaseModel):
    current_path: str
    metadata: HostAccessFileMetadata
    items: list[HostAccessFileItem]


class HostAccessTextFileResponse(BaseModel):
    path: str
    content: str


class HostAccessWriteTextRequest(BaseModel):
    path: str = Field(default='/', max_length=4096)
    content: str = Field(default='', max_length=1024 * 1024)

    @field_validator('path', mode='before')
    @classmethod
    def normalize_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)


class HostAccessCreateFolderRequest(BaseModel):
    parent_path: str = Field(default='/', max_length=4096)
    name: str = Field(min_length=1, max_length=255)

    @field_validator('parent_path', mode='before')
    @classmethod
    def normalize_parent_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)

    @field_validator('name', mode='before')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('Name cannot be empty')
        if '/' in normalized or normalized in {'.', '..'}:
            raise ValueError('Name must be a single path segment')
        return normalized


class HostAccessCreateFileRequest(HostAccessCreateFolderRequest):
    pass


class HostAccessRenameItemRequest(BaseModel):
    source_path: str = Field(default='/', max_length=4096)
    target_name: str = Field(min_length=1, max_length=255)

    @field_validator('source_path', mode='before')
    @classmethod
    def normalize_source_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)

    @field_validator('target_name', mode='before')
    @classmethod
    def normalize_target_name(cls, value: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('Target name cannot be empty')
        if '/' in normalized or normalized in {'.', '..'}:
            raise ValueError('Target name must be a single path segment')
        return normalized


class HostAccessDeleteItemRequest(BaseModel):
    path: str = Field(default='/', max_length=4096)

    @field_validator('path', mode='before')
    @classmethod
    def normalize_delete_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)


class HostAccessCopyItemRequest(BaseModel):
    source_path: str = Field(default='/', max_length=4096)
    destination_path: str = Field(default='/', max_length=4096)

    @field_validator('source_path', 'destination_path', mode='before')
    @classmethod
    def normalize_copy_paths(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)


class HostAccessPermissionBits(BaseModel):
    read: bool = False
    write: bool = False
    execute: bool = False


class HostAccessUpdateAttributesRequest(BaseModel):
    source_path: str = Field(default='/', max_length=4096)
    target_name: Optional[str] = Field(default=None, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=128)
    group: Optional[str] = Field(default=None, max_length=128)
    owner_permissions: HostAccessPermissionBits = Field(default_factory=HostAccessPermissionBits)
    group_permissions: HostAccessPermissionBits = Field(default_factory=HostAccessPermissionBits)
    other_permissions: HostAccessPermissionBits = Field(default_factory=HostAccessPermissionBits)

    @field_validator('source_path', mode='before')
    @classmethod
    def normalize_update_source_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)

    @field_validator('target_name', mode='before')
    @classmethod
    def normalize_update_target_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if '/' in normalized or normalized in {'.', '..'}:
            raise ValueError('Target name must be a single path segment')
        return normalized

    @field_validator('owner', 'group', mode='before')
    @classmethod
    def normalize_identity_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class HostAccessUploadRequest(BaseModel):
    parent_path: str = Field(default='/', max_length=4096)
    file_name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)

    @field_validator('parent_path', mode='before')
    @classmethod
    def normalize_upload_parent_path(cls, value: Optional[str]) -> str:
        return _normalize_optional_path(value)

    @field_validator('file_name', mode='before')
    @classmethod
    def normalize_file_name(cls, value: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('File name cannot be empty')
        if '/' in normalized or normalized in {'.', '..'}:
            raise ValueError('File name must be a single path segment')
        return normalized


class HostAccessMutationResponse(BaseModel):
    path: str
    operation: str


class HostAccessAttributesMutationResponse(HostAccessMutationResponse):
    metadata: HostAccessFileMetadata


HostAccessProfileResponse.model_rebuild()
