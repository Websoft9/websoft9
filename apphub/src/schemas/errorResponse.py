from pydantic import BaseModel

class ErrorResponse(BaseModel):
    message: str
    details: str
