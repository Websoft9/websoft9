from pydantic import BaseModel, Field


class AppPhpMigrationRequest(BaseModel):
    target_version: str = Field(..., description="Requested PHP target version", json_schema_extra={"example": "8.3"})
    remarks: str = Field(
        ...,
        description="Contact details and migration remarks",
        json_schema_extra={"example": "admin@example.com, please help validate plugin compatibility"},
    )
