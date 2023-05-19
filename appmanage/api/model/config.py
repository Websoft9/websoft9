from pydantic import BaseModel

class Config(BaseModel):
    port: int
    compose_file: None
    url: None
    admin_url: None
    admin_username: None
    admin_password: None
    default_domain: None
