from pydantic import BaseModel, Field

Status = str


class ModelProviderOut(BaseModel):
    id: str
    provider: str
    model: str
    base_url: str
    api_key: str
    description: str
    status: Status
    health_status: str
    last_test_at: str | None
    last_test_message: str
    created_by: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ModelProviderIn(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str = ""
    description: str = ""
    status: Status = "enabled"


class AiCapabilityOut(BaseModel):
    id: str
    name: str
    description: str


class ModelAssignmentIn(BaseModel):
    model_provider_id: str = Field(min_length=1)


class ModelAssignmentOut(BaseModel):
    capability_id: str
    capability_name: str
    capability_description: str
    model_provider_id: str | None = None
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_status: str | None = None
    updated_at: str | None = None
