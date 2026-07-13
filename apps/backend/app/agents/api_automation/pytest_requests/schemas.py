from typing import Any, Literal

from pydantic import BaseModel, Field


class PytestRequestsEndpoint(BaseModel):
    id: str
    method: str
    path: str
    summary: str = ""


class PytestRequestsFrameworkConfig(BaseModel):
    python_version: str = ">=3.12"


class PytestRequestsGenerationInput(BaseModel):
    endpoint: PytestRequestsEndpoint
    cases: list[dict[str, Any]] = Field(default_factory=list)
    framework_config: PytestRequestsFrameworkConfig = Field(default_factory=PytestRequestsFrameworkConfig)


class GeneratedCodeFile(BaseModel):
    key: str
    kind: Literal["test", "data", "support", "config", "documentation"]
    language: Literal["python", "json", "toml", "ini", "markdown"]
    content: str


class PytestRequestsGenerationResult(BaseModel):
    endpoint_id: str
    endpoint_key: str
    files: list[GeneratedCodeFile]
    case_count: int
    warnings: list[str] = Field(default_factory=list)
