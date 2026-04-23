from typing import Optional

from pydantic import BaseModel, Field

from src.schemas.domainNames import DomainNames
from src.schemas.proxyHosts import ProxyHost


class ProxyMutationRequest(DomainNames):
    certificate_id: Optional[int] = Field(default=None, description="Optional certificate id from Nginx Proxy Manager")


class ProxyTaskAcceptedResponse(BaseModel):
    task_id: str
    status: str = "accepted"


class ProxyTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    proxy_host: Optional[ProxyHost] = None
    error: Optional[str] = None