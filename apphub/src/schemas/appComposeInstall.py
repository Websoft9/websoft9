from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.exception import CustomException


def _normalize_non_empty(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CustomException(400, "Invalid Request", f"'{field_name}' cannot be empty.")
    return normalized


def _normalize_optional_text(value: Optional[str]) -> str:
    return str(value or "").strip()


class ComposeEnvironmentEntry(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(default="", max_length=4000)

    @field_validator("key", mode="before")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = _normalize_non_empty(value, "key")
        if "=" in normalized or any(char.isspace() for char in normalized):
            raise CustomException(400, "Invalid Request", "Environment variable keys cannot contain spaces or '='.")
        return normalized

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: Optional[str]) -> str:
        return _normalize_optional_text(value)


class ComposeInstallBase(BaseModel):
    app_id: str = Field(..., min_length=2, max_length=20)
    display_name: str = Field(..., min_length=1, max_length=128)
    compose_content: str = Field(..., min_length=1)
    env: list[ComposeEnvironmentEntry] = Field(default_factory=list)

    @field_validator("app_id", mode="before")
    @classmethod
    def validate_app_id(cls, value: str) -> str:
        normalized = _normalize_non_empty(value, "app_id").lower()
        if not normalized[0].isalpha() or not normalized.isalnum() or len(normalized) < 2 or len(normalized) > 20:
            raise CustomException(400, "Invalid Request", "The app_id must be a combination of 2 to 20 lowercase letters and numbers, and cannot start with a number.")
        return normalized

    @field_validator("display_name", mode="before")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _normalize_non_empty(value, "display_name")

    @field_validator("compose_content", mode="before")
    @classmethod
    def validate_compose_content(cls, value: str) -> str:
        return _normalize_non_empty(value, "compose_content")

    @model_validator(mode="after")
    def validate_env_duplicates(self):
        keys = [entry.key for entry in self.env]
        if len(keys) != len(set(keys)):
            raise CustomException(400, "Invalid Request", "Duplicate environment variable keys are not allowed.")
        return self


class ComposeValidationRequest(ComposeInstallBase):
    pass


class ComposeValidationResponse(BaseModel):
    valid: bool = True
    services: list[str] = Field(default_factory=list)
    environment_keys: list[str] = Field(default_factory=list)
    details: str = Field(default="Compose content is valid.")


class ComposeInstallRequest(ComposeInstallBase):
    domain: Optional[str] = Field(default=None, max_length=253)

    @field_validator("domain", mode="before")
    @classmethod
    def validate_domain(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_optional_text(value)
        return normalized or None


class ComposeInstallAcceptedResponse(BaseModel):
    app_id: str = Field(..., description="Resolved installation tracking app id")
    tracking_id: str = Field(..., description="Compose installation tracking id")
    message: str = Field(default="Success")
    details: str = Field(default="The custom compose request has been accepted and can be tracked through 'My Apps'.")
