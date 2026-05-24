from typing import Literal, Optional

from pydantic import BaseModel, Field, validator

from src.core.exception import CustomException
from src.schemas.proxyHosts import ProxyHost


class AppAccessCandidate(BaseModel):
    container_name: str = Field(..., description="Container name")
    forward_host: str = Field(..., description="Forward host used by Nginx Proxy Manager")
    forward_port: int = Field(..., description="Target port inside the selected container")
    published_ports: list[str] = Field(default_factory=list, description="Published port pairs like 8080:80")


class AppAccessProfile(BaseModel):
    enabled: bool = Field(default=False, description="Whether this app exposes a web entry")
    source: Literal["builtin", "profile", "unknown"] = Field(default="unknown")
    locked: bool = Field(default=False, description="Whether the target is inferred from built-in app metadata and cannot be edited")
    forward_host: Optional[str] = Field(default=None, description="Forward host for the proxy target")
    forward_port: Optional[int] = Field(default=None, description="Forward port for the proxy target")
    forward_scheme: Literal["http", "https"] = Field(default="http")


class AppAccessOverviewResponse(BaseModel):
    app_id: str
    app_dist: Optional[str] = None
    requires_definition: bool = False
    profile: AppAccessProfile
    candidates: list[AppAccessCandidate] = Field(default_factory=list)
    proxy_hosts: list[ProxyHost] = Field(default_factory=list)
    certificates: list[dict] = Field(default_factory=list)


class AppAccessProfileUpdateRequest(BaseModel):
    enabled: bool = Field(default=True)
    forward_host: Optional[str] = Field(default=None)
    forward_port: Optional[int] = Field(default=None)
    forward_scheme: Literal["http", "https"] = Field(default="http")

    @validator("forward_port")
    def validate_forward_port(cls, value: Optional[int]):
        if value is None:
            return value
        if value < 1 or value > 65535:
            raise CustomException(400, "Invalid Request", "forward_port must be between 1 and 65535")
        return value


class AppAccessDomainBindingRequest(BaseModel):
    domain_names: list[str] = Field(..., description="One or more domain names")
    certificate_id: Optional[int] = Field(default=None, description="Optional certificate id")
    ssl_forced: bool = Field(default=False, description="Whether HTTP should be redirected to HTTPS")
    proxy_id: Optional[int] = Field(default=None, description="Optional proxy host id to update")

    @validator("domain_names")
    def validate_domain_names(cls, value: list[str]):
        normalized = [item.strip() for item in value if item and item.strip()]
        if not normalized:
            raise CustomException(400, "Invalid Request", "domain_names cannot be empty")
        if len(set(normalized)) != len(normalized):
            raise CustomException(400, "Invalid Request", "domain_names must be unique")
        return normalized


class AppAccessCertificateRequest(BaseModel):
    email: str = Field(..., description="Let's Encrypt account email")
    domain_names: list[str] = Field(..., description="Certificate domain names")
    proxy_id: Optional[int] = Field(default=None, description="Optional proxy host to bind after issuing the certificate")

    @validator("email")
    def validate_email(cls, value: str):
        email = value.strip()
        if not email or "@" not in email:
            raise CustomException(400, "Invalid Request", "email is invalid")
        return email

    @validator("domain_names")
    def validate_certificate_domains(cls, value: list[str]):
        normalized = [item.strip() for item in value if item and item.strip()]
        if not normalized:
            raise CustomException(400, "Invalid Request", "domain_names cannot be empty")
        return normalized