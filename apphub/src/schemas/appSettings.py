from typing import Optional

from pydantic import BaseModel, Field


class ApiKeySetting(BaseModel):
    key: str = Field(..., title="The api key")


class Domain(BaseModel):
    wildcard_domain: str = Field(None, title="The domain name")


class GenerateSelfSignedCertRequest(BaseModel):
    domain: str = Field('', title="Optional domain name for the certificate CN")
    validity_days: int = Field(3650, title="Certificate validity in days", ge=1, le=36500)


class ApplyLetsEncryptCertRequest(BaseModel):
    domain: str = Field(..., title="Domain name for Let's Encrypt certificate")
    email: str = Field('', title="Contact email for Let's Encrypt notifications")


class UploadCertRequest(BaseModel):
    cert_pem: str = Field(..., title="Certificate PEM content")
    key_pem: str = Field(..., title="Private key PEM content")
    intermediate_pem: str = Field('', title="Optional intermediate/chain certificate PEM")

class PlatformGatewaySetting(BaseModel):
    https_enabled: str = Field(..., title="Whether platform gateway HTTPS is enabled")
    ssl_cert: str = Field(..., title="The SSL certificate path for platform gateway")
    ssl_key: str = Field(..., title="The SSL key path for platform gateway")


class PlatformGatewayBatchUpdateRequest(BaseModel):
    bound_domain: str = Field('', title="The bound domain for platform gateway")
    https_enabled: str = Field(..., title="Whether platform gateway HTTPS is enabled")
    force_https: str = Field(..., title="Whether force HTTPS is enabled for platform gateway")
    ssl_cert: str = Field('', title="The SSL certificate path for platform gateway")
    ssl_key: str = Field('', title="The SSL key path for platform gateway")

class ProductAuthSetting(BaseModel):
    enabled: str = Field(..., title="Whether product auth is enabled")
    protected_modules: str = Field(..., title="Protected modules list")


class DockerMirrorEntryPayload(BaseModel):
    # The stored entry being edited. It is what keeps a renamed address attached to its
    # credentials, so the console sends it back for rows it loaded.
    id: Optional[int] = Field(None, title="Identifier of the stored entry, when editing one")
    url: str = Field(..., title="Accelerator prefix, for example docker.1ms.run")
    username: str = Field('', title="Registry user name, empty for a public accelerator")
    # None keeps the stored password: the console does not send it back after a read.
    password: Optional[str] = Field(None, title="Registry password; null keeps the stored one")
    enabled: bool = Field(True, title="Whether this accelerator may be used")


class DockerMirrorEntriesRequest(BaseModel):
    """The whole accelerator list, in the order it must be tried."""

    entries: list[DockerMirrorEntryPayload] = Field(default_factory=list, title="Ordered accelerators")

class AppSettings(BaseModel):
    api_key: ApiKeySetting
    domain: Domain
    platform_gateway: Optional[PlatformGatewaySetting] = None
    product_auth: Optional[ProductAuthSetting] = None