from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductAuthOperator(BaseModel):
    id: str
    username: str
    display_name: str
    disabled: bool = False
    deleted: bool = False
    reset_password_eligible: bool = True
    created_at: str


class ProductAuthStorageBoundary(BaseModel):
    asset_group: str
    backup_scope: str = Field(default="product-owned")
    separated_from_integrations: bool = True


class ProductAuthStatusResponse(BaseModel):
    enabled: bool
    initialization_required: bool
    authenticated: bool
    protected_modules: list[str]
    current_user: Optional[ProductAuthOperator] = None
    storage_boundary: ProductAuthStorageBoundary


class ProductAuthInitializeRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) < 3:
            raise ValueError("Username must be at least 3 characters after trimming")
        return normalized

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Display name cannot be empty")
        return normalized


class ProductAuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) < 3:
            raise ValueError("Username must be at least 3 characters after trimming")
        return normalized