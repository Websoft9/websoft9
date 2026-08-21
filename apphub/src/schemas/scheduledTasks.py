from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScheduledTaskWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    target: Literal["container", "host"] = "container"
    profile_id: Optional[str] = None
    schedule: str = Field(min_length=1, max_length=128)
    execution_mode: Literal["command", "path", "upload"] = "command"
    command: str = Field(default="", max_length=4096)
    script_path: Optional[str] = Field(default=None, max_length=4096)
    script_name: Optional[str] = Field(default=None, max_length=255)
    script_content: Optional[str] = Field(default=None, max_length=524288)
    timeout_seconds: int = Field(default=0, ge=0, le=86400)
    retry_count: int = Field(default=0, ge=0, le=10)
    enabled: bool = True


class ScheduledTaskToggleRequest(BaseModel):
    enabled: bool
