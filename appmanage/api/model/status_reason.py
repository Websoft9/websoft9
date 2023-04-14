from pydantic import BaseModel

class StatusReason(BaseModel):
    Code: str
    Message: str
    Detail: str
