from typing import List
from pydantic import BaseModel, Field

class Response(BaseModel):
    code: int = Field(default=None, description="响应码")
    message: str = Field(default=None, description="响应信息")
    data: List = Field(default=None, description="响应数据")
