from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.core.exception import CustomException


SetupWizardStep = Literal[
    "welcome",
    "platform_init",
    "app_init_ready",
    "app_init_running",
    "app_init_failed",
    "complete",
]

SetupWizardInstallStatus = Literal["running", "succeeded", "failed"]
SetupWizardInputType = Literal["text", "number", "password"]


class SetupWizardError(BaseModel):
    code: str
    message: str
    retryable: bool = True
    field_names: list[str] = Field(default_factory=list)


class SetupWizardStateResponse(BaseModel):
    enabled: bool
    current_step: SetupWizardStep
    app_slug: Optional[str] = None
    installed_app_id: Optional[str] = None
    completed: bool
    tracking_id: Optional[str] = None
    pending_app_id: Optional[str] = None
    last_error: Optional[SetupWizardError] = None
    updated_at: str
    completed_at: Optional[str] = None


class SetupWizardInputField(BaseModel):
    name: str
    label: str
    type: SetupWizardInputType = "text"
    required: bool = True
    default_value: Optional[str] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None


class SetupWizardAppResponse(BaseModel):
    app_slug: str
    display_name: str
    logo_url: Optional[str] = None
    edition: str
    default_app_id: str
    is_web_app: bool
    requires_user_inputs: bool
    required_inputs: list[SetupWizardInputField] = Field(default_factory=list)
    settings: dict[str, str] = Field(default_factory=dict)


class SetupWizardPlatformInitCompleteResponse(BaseModel):
    current_step: SetupWizardStep
    updated_at: str


class SetupWizardInstallRequest(BaseModel):
    app_id: str = Field(min_length=2, max_length=20)
    edition: str = Field(min_length=1, max_length=128)
    domain_name: str = Field(min_length=1, max_length=255)
    user_inputs: dict[str, str] = Field(default_factory=dict)

    @field_validator("app_id", mode="before")
    @classmethod
    def normalize_app_id(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise CustomException(400, "Invalid Request", "'app_id' cannot be empty.")
        return normalized

    @field_validator("edition", mode="before")
    @classmethod
    def normalize_edition(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise CustomException(400, "Invalid Request", "'edition' cannot be empty.")
        return normalized

    @field_validator("domain_name", mode="before")
    @classmethod
    def normalize_domain_name(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise CustomException(400, "Invalid Request", "'domain_name' cannot be empty.")
        return normalized


class SetupWizardInstallAcceptedResponse(BaseModel):
    tracking_id: str
    current_step: SetupWizardStep


class SetupWizardInstallStatusResponse(BaseModel):
    status: SetupWizardInstallStatus
    current_step: SetupWizardStep
    installed_app_id: Optional[str] = None
    last_error: Optional[SetupWizardError] = None


class SetupWizardCompleteResponse(BaseModel):
    current_step: SetupWizardStep
    installed_app_id: str
    completed: bool
    completed_at: str