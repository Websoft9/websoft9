from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AppDatabaseTool(BaseModel):
    label: str = Field(..., description="Display label of a database admin tool", json_schema_extra={"example": "phpMyAdmin"})
    app_key: str = Field(..., description="App store key used to open the tool", json_schema_extra={"example": "phpmyadmin"})


class AppDatabaseAccount(BaseModel):
    user: str = Field(
        ..., description="Account name resolved from the declared source", json_schema_extra={"example": "wordpress"}
    )
    usage: List[str] = Field(
        default_factory=list,
        description="English usage enums: application, initialization, administration. Empty when not declared",
        json_schema_extra={"example": ["application"]},
    )
    password: Optional[str] = Field(
        None,
        description="Resolved password. null means unknown: the declaration has no source or the value is missing",
    )


class AppDatabaseComponent(BaseModel):
    id: str = Field(..., description="Component id declared by the application", json_schema_extra={"example": "rds"})
    driver: str = Field(..., description="Engine key from the type dictionary", json_schema_extra={"example": "mysql"})
    service: Optional[str] = Field(
        None, description="Compose service that hosts the database", json_schema_extra={"example": "mysql"}
    )
    mode: Literal["internal", "external", "unknown"] = Field(
        "internal", description="Connection currently used by the instance, as far as the config can tell"
    )
    host: Optional[str] = Field(None, description="Host known inside the instance network, never a public address")
    port: Optional[int] = Field(None, description="Container listening port")
    port_from_dictionary: bool = Field(
        True, description="True when the port comes from the type dictionary default rather than the instance config"
    )
    names: List[str] = Field(default_factory=list, description="Known database names. Unresolvable entries are omitted")
    accounts: List[AppDatabaseAccount] = Field(default_factory=list, description="Known accounts paired with their passwords")
    auth: Literal["password", "none", "unknown"] = Field(
        "unknown", description="none only when the declaration says users: []"
    )
    unknown_fields: List[str] = Field(
        default_factory=list, description="Fields the declaration asks for but the instance does not provide"
    )
    tools: List[AppDatabaseTool] = Field(default_factory=list, description="Database admin tools matching the driver")


class AppDatabasesResponse(BaseModel):
    app_id: str = Field(..., description="App ID", json_schema_extra={"example": "seafile"})
    declaration: Literal["v2", "legacy", "missing"] = Field(
        ...,
        description=(
            "v2: database[] is present and resolved. "
            "legacy: the snapshot only has the deprecated object, so the caller keeps its previous rendering. "
            "missing: the snapshot has no database declaration at all."
        ),
    )
    external_active: bool = Field(
        False, description="True when the instance runs with W9_DATABASE_MODE=external; external rows stay on the legacy path"
    )
    components: List[AppDatabaseComponent] = Field(default_factory=list, description="Resolved internal components")
