from pydantic import BaseModel

class RunningInfo(BaseModel):
    port: int
    compose_file: str
    url: str
    admin_url: str
    user_name: str
    password: str
    default_domain: str
    set_domain: str
