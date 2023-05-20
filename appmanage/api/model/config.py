from pydantic import BaseModel

class Config(BaseModel):
    port: int
    compose_file: str
    url: str
    admin_url: str
    admin_username: str
    admin_password: str
    default_domain: str
    admin_path: str
    admin_domain_url: str