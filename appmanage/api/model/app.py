from pydantic import BaseModel
from api.model.config import Config
from api.model.status_reason import StatusReason

class App(BaseModel):
    app_id: None
    app_name: None
    customer_name: None
    trade_mark: None
    status: None
    status_reason: StatusReason = None
    official_app: bool
    app_version: None
    create_time: None
    volume_data = []
    config_path = None
    image_url: None
    app_https: bool
    app_replace_url: bool
    config: Config = None
