from pydantic import BaseModel
from running_info import RunningInfo
from status_reason import StatusReason

class App(BaseModel):
    app_id: str
    app_name: str
    customer_name: str
    trade_mark: str
    status: str
    official_app: bool
    running_info: RunningInfo
    status_reason: StatusReason