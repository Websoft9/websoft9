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

class AppSettings(BaseModel):
    api_key: ApiKeySetting
    domain: Domain
    platform_gateway: Optional[PlatformGatewaySetting] = None
    product_auth: Optional[ProductAuthSetting] = None