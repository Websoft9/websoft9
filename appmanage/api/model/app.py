from pydantic import BaseModel

class App(BaseModel):
    id: str
    name: str
    trade_mark: str
    status_code: int
    status: str
    port: int
    volume: str
    url: str
    image_url: str
    admin_url: str
    user_name: str
    password: str
