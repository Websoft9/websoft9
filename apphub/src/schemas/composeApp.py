from typing import Any, Optional
from pydantic import BaseModel, Field


class ComposeEnvEntry(BaseModel):
    key: str = Field(..., description="Environment variable key")
    value: str = Field(default="", description="Environment variable value")


class ComposeMountFile(BaseModel):
    path: str = Field(..., description="Relative path inside the repository, e.g. src/nginx.conf")
    content: str = Field(default="", description="File content")


class ComposeContentResponse(BaseModel):
    app_id: str = Field(..., description="Compose app ID")
    compose_content: str = Field(..., description="Raw docker-compose.yml content")
    env: list[ComposeEnvEntry] = Field(default_factory=list, description="User-defined environment variables")
    mounts: list[ComposeMountFile] = Field(default_factory=list, description="Mount/config files under src/")


class ComposeUpdateRequest(BaseModel):
    compose_content: str = Field(..., description="Updated docker-compose.yml content")
    env: list[ComposeEnvEntry] = Field(default_factory=list, description="User-defined environment variables")
    mounts: list[ComposeMountFile] = Field(default_factory=list, description="Mount/config files to write/update")


class ComposeRedeployRequest(BaseModel):
    pull_image: bool = Field(default=True, description="Whether to pull the latest image when redeploying")
