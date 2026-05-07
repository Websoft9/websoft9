from typing import Optional

from pydantic import BaseModel, Field

class ApiKeySetting(BaseModel):
    key: str = Field(..., title="The api key")

class Domain(BaseModel):
    wildcard_domain: str = Field(None, title="The domain name")

class PlatformGatewaySetting(BaseModel):
    https_enabled: str = Field(..., title="Whether platform gateway HTTPS is enabled")
    ssl_cert: str = Field(..., title="The SSL certificate path for platform gateway")
    ssl_key: str = Field(..., title="The SSL key path for platform gateway")

class ProductAuthSetting(BaseModel):
    enabled: str = Field(..., title="Whether product auth is enabled")
    protected_modules: str = Field(..., title="Protected modules list")

class AppSettings(BaseModel):
    api_key: ApiKeySetting
    domain: Domain
    platform_gateway: Optional[PlatformGatewaySetting] = None
    product_auth: Optional[ProductAuthSetting] = None