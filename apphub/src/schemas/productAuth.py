from typing import Optional
import re

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_username(value: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) < 3:
        raise ValueError("Username must be at least 3 characters after trimming")
    return normalized


def _normalize_display_name(value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Display name cannot be empty")
    return normalized


def _normalize_password(value: str) -> str:
    normalized = str(value)
    if len(normalized) < 8:
        raise ValueError("Password must be at least 8 characters and include uppercase, lowercase, number, and special character")
    if not re.search(r"[A-Z]", normalized) or not re.search(r"[a-z]", normalized) or not re.search(r"\d", normalized) or not re.search(r"[^A-Za-z0-9]", normalized):
        raise ValueError("Password must be at least 8 characters and include uppercase, lowercase, number, and special character")
    return normalized


def _normalize_locale(value: Optional[str]) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return "en"
    if normalized not in {"en", "zh-CN"}:
        raise ValueError("Locale must be one of: en, zh-CN")
    return normalized


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', normalized):
        raise ValueError("Email must be a valid email address")
    return normalized


def _normalize_app_key(value: str) -> str:
    normalized = str(value).strip().lower()
    if not normalized:
        raise ValueError("App key cannot be empty")
    return normalized


class ProductAuthOperator(BaseModel):
    id: str
    username: str
    display_name: str
    email: Optional[str] = None
    locale: str = "en"
    disabled: bool = False
    deleted: bool = False
    reset_password_eligible: bool = True
    delete_eligible: bool = True
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


class ProductAuthUsersResponse(BaseModel):
    users: list[ProductAuthOperator]


class ProductAuthCreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)
    email: Optional[str] = None
    locale: str = Field(default="en", max_length=16)
    disabled: bool = False

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("password", mode="before")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        return _normalize_password(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return _normalize_display_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_email(value)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value: Optional[str]) -> str:
        return _normalize_locale(value)


class ProductAuthResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)

    @field_validator("password", mode="before")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        return _normalize_password(value)


class ProductAuthUpdateUserRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    email: Optional[str] = None
    locale: str = Field(default="en", max_length=16)
    disabled: Optional[bool] = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_email(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return _normalize_display_name(value)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value: Optional[str]) -> str:
        return _normalize_locale(value)


class ProductAuthInitializeRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)
    locale: str = Field(default="en", max_length=16)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("password", mode="before")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        return _normalize_password(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return _normalize_display_name(value)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value: Optional[str]) -> str:
        return _normalize_locale(value)


class ProductAuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalize_username(value)


class ProductAuthFavoritesResponse(BaseModel):
    favorites: list[str]


class ProductAuthFavoriteRequest(BaseModel):
    app_key: str = Field(min_length=1, max_length=128)

    @field_validator("app_key", mode="before")
    @classmethod
    def normalize_app_key(cls, value: str) -> str:
        return _normalize_app_key(value)