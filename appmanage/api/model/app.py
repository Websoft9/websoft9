from pydantic import BaseModel
from api.model.config import Config
from api.model.status_reason import StatusReason

class App(BaseModel):
    app_id: str
    app_name: str
    customer_name: str
    trade_mark: str
    status: str
    status_reason: StatusReason = None
    official_app: bool
    app_version: str
    create_time: str
    volume_data : str
    config_path : str
    image_url: str
    app_https: bool
    app_replace_url: bool
    config: Config = None
