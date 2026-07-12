"""Schemas for durable exploration operations."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReplayStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["navigate", "click", "fill", "press", "wait", "go_back"]
    element_key: str = ""
    path: str = ""
    value: str = ""
    value_ref: str = ""
    key: str = ""
    milliseconds: int = Field(default=500, ge=100, le=3000)
    expected: list["ReplayExpectation"] = Field(default_factory=list)


class ReplayExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["url_contains", "title_contains", "overlay_visible", "element_value"]
    value: str = ""
    value_ref: str = ""
    element_key: str = ""


class ReplayParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "integer", "boolean"] = "string"
    required: bool = True
    default: Any = None


class EnvironmentValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: str
    status: Literal["passed", "failed"]
    validated_at: str
    error: str = ""


class ReplayOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    version: int = Field(default=1, ge=1)
    status: Literal["draft", "validated", "published", "degraded", "deprecated"] = "draft"
    page_path: str = "/"
    parameters: dict[str, ReplayParameter] = Field(default_factory=dict)
    steps: list[ReplayStep]
    validations: list[EnvironmentValidation] = Field(default_factory=list)


class OperationsArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    browser: Literal["chrome"] = "chrome"
    base_url_source: Literal["environment"] = "environment"
    operations: list[ReplayOperation] = Field(default_factory=list)


class ReplayStepResult(BaseModel):
    index: int
    action: str
    element_key: str = ""
    success: bool
    detail: dict[str, Any] = Field(default_factory=dict)


class ReplayResult(BaseModel):
    project_id: str
    environment_id: str
    operation_key: str
    success: bool
    steps: list[ReplayStepResult]
