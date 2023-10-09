from typing import Optional, List
from pydantic import BaseModel, Field, validator
from src.core.exception import CustomException


class DomainNames(BaseModel):
    domain_names: List[str] 

    @validator('domain_names', each_item=True)
    def validate_domain_name(cls, v):
        if not v.strip():
            raise CustomException(400,"Invalid Request","domain_names' cannot be empty string.")
        if v.startswith('http://') or v.startswith('https://'):
            raise CustomException(400,"Invalid Request","'domain_names' cannot start with 'http://' or 'https://'.")
        return v
    
    @validator('domain_names')
    def validate_domain_names(cls, v):
        if not v:
            raise CustomException(400,"Invalid Request","domain_names' cannot be empty.")
        
        if len(set(v)) != len(v):
            raise CustomException(400,"Invalid Request","Duplicate entries found in 'domain_names'. All domains must be unique.")
        return v