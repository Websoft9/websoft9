from datetime import datetime
from pydantic import BaseModel

class User(BaseModel):
    user_type: str
    user_name: str
    password: str
    nick_name: str
    create_time: datetime
    update_tiem: datetime