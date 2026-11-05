from typing import List

from pydantic import BaseModel, field_validator

from src.core.exception import CustomException


class ProxyHost(BaseModel):
    proxy_id: int
    domain_names: List[str]
    certificate_id: int | None = None
    certificate_name: str | None = None
    ssl_forced: bool = False

    @field_validator('domain_names')
    @classmethod
    def validate_domain_name(cls, v: list[str]) -> list[str]:
        # pydantic v2 没有 each_item：逐个元素校验后再交给列表级校验器
        for item in v:
            if not item.strip():
                raise CustomException(400, "Invalid Request", "domain_names' cannot be empty string.")
            if item.startswith(('http://', 'https://')):
                raise CustomException(400, "Invalid Request", "'domain_names' cannot start with 'http://' or 'https://'.")
        return v

    @field_validator('domain_names')
    @classmethod
    def validate_domain_names(cls, v):
        if not v:
            raise CustomException(400, "Invalid Request", "domain_names' cannot be empty.")

        if len(set(v)) != len(v):
            raise CustomException(
                400, "Invalid Request", "Duplicate entries found in 'domain_names'. All domains must be unique."
            )
        return v
