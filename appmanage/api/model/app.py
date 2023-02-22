from pydantic import BaseModel

class App(BaseModel):
    id: int
    name: str
    status_code: int
    status: str
    port: int
    volume: str
    url: str
    user_name: str
    password: str
