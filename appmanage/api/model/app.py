from pydantic import BaseModel
from api.model.running_info import RunningInfo
from api.model.status_reason import StatusReason

class App(BaseModel):
    app_id: str
    app_name: str
    customer_name: str
    trade_mark: str
    status: str
    status_reason: StatusReason
    official_app: bool
    image_url: str
    running_info: RunningInfo
