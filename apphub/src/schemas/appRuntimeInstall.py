import re
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.core.exception import CustomException

# Runtime families AppHub can deploy from source. Phase 1 only surfaces PHP in the console, but the
# install contract already covers the other families so a new runtime does not need a new schema.
RUNTIME_KEYS = ("php", "nodejs", "java", "python")

# Versions a request may ask for. Anything outside these lists is rejected instead of silently
# falling back to a default image; the lists mirror the runtime images the product publishes.
RUNTIME_VERSIONS = {
    "php": (
        "8.0-apache",
        "8.1-apache",
        "8.2-apache",
        "8.3-apache",
        "8.3-fpm",
        "8.4-apache",
        "8.4-fpm",
    ),
    "nodejs": ("20", "22", "24"),
    "java": ("8-jdk8-temurin", "9-jdk17-temurin", "10-jdk21-temurin"),
    "python": ("3.10", "3.11", "3.12", "3.13"),
}

# Templates a runtime may be installed with. The first entry is the default template.
RUNTIME_TEMPLATES = {
    "php": ("php", "phpfpmnginx"),
    "nodejs": ("nodejs",),
    "java": ("tomcat",),
    "python": ("python",),
}

# Runtimes whose container port cannot be inferred from the image, so the operator has to supply it.
RUNTIMES_REQUIRING_APP_PORT = ("nodejs",)

APP_ID_PATTERN = re.compile("^[a-z][a-z0-9]{1,19}$")


class RuntimeInstallValidationPayload(BaseModel):
    template_app_name: str = Field(..., description="Template used to deploy the runtime")
    runtime_label: str = Field(..., description="Operator facing runtime name", examples=["PHP Runtime"])
    proxy_enabled: bool = Field(..., description="Whether the runtime is published through the proxy")
    domain_names: List[str] = Field(..., description="Domains or host addresses of the runtime")
    app_port: int = Field(..., description="Port the runtime listens on inside the container")
    runtime_url: str = Field(..., description="URL the application is reached on")
    network_name: str = Field(..., description="Docker network the runtime joins")
    url_replace: bool = Field(..., description="Whether the application URL gets rewritten")


class RuntimeInstallRequest(BaseModel):
    runtime_key: str = Field(..., description="Runtime family to deploy", examples=["php"])
    app_id: str = Field(
        ...,
        description="Custom identifier of the application. 2 to 20 lowercase letters and digits, cannot start with a digit.",
        examples=["phpsite"],
    )
    version: str = Field(..., description="Runtime version, e.g. 8.3-apache or 24", examples=["8.3-apache"])
    host_port: int = Field(..., description="Port published on the host", examples=[9011])
    domain: Optional[str] = Field(None, description="Domain that publishes the runtime through the proxy")
    fallback_host: str = Field("127.0.0.1", description="Host or IP used when no domain is requested")
    template_app_name: Optional[str] = Field(None, description="Template override for the runtime")
    app_port: Optional[int] = Field(
        None, description="Port the runtime listens on inside the container", validate_default=True
    )
    runtime_url: Optional[str] = Field(None, description="URL the application should be reached on")
    network_name: Optional[str] = Field(None, description="Docker network the runtime joins")
    url_replace: Optional[bool] = Field(None, description="Override the runtime default URL rewriting")

    @field_validator("runtime_key")
    @classmethod
    def validate_runtime_key(cls, value):
        if value not in RUNTIME_KEYS:
            raise CustomException(400, "Invalid Request", f"Unsupported runtime '{value}'.")
        return value

    @field_validator("app_id")
    @classmethod
    def validate_app_id(cls, value):
        if not APP_ID_PATTERN.match(value):
            raise CustomException(
                400,
                "Invalid Request",
                "The app_id must be a combination of 2 to 20 lowercase letters and numbers, and cannot start with a number.",
            )
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value):
        if not value.strip():
            raise CustomException(400, "Invalid Request", "'version' cannot be empty.")
        return value

    @field_validator("template_app_name")
    @classmethod
    def validate_template_app_name(cls, value, info: ValidationInfo):
        if value is None:
            return value
        runtime_key = (info.data or {}).get("runtime_key")
        if runtime_key and value not in RUNTIME_TEMPLATES.get(runtime_key, ()):
            raise CustomException(400, "Invalid Request", f"Unsupported template '{value}' for runtime '{runtime_key}'.")
        return value

    @field_validator("app_port")
    @classmethod
    def validate_app_port(cls, value, info: ValidationInfo):
        runtime_key = (info.data or {}).get("runtime_key")
        if value is None and runtime_key in RUNTIMES_REQUIRING_APP_PORT:
            raise CustomException(400, "Invalid Request", "The selected runtime requires an internal application port.")
        return value
