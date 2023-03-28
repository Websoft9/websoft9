from pydantic import BaseModel

class App(BaseModel):
    app_id: str
    name: str
    customer_name: str
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
    official_app: bool
