from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiAssertion(BaseModel):
    type: Literal["status_code", "jsonpath_equals", "jsonpath_exists", "schema_contains"]
    path: str = ""
    expected: Any = None


class ApiGeneratedCase(BaseModel):
    title: str
    priority: str = "P2"
    endpoint_id: str
    source: Literal["ai_generated", "manual", "approved_test_case"] = "ai_generated"
    request: dict[str, Any]
    expected: dict[str, Any]
    assertions: list[dict[str, Any] | ApiAssertion]
    variables: dict[str, Any] = Field(default_factory=dict)
    data_origin: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "ready", "needs_input"] = "draft"
    notes: str = ""


class ApiAutomationGenerationInput(BaseModel):
    project_id: str
    endpoints: list[dict[str, Any]]
    environment_summary: dict[str, Any] = Field(default_factory=dict)
    source_test_cases: list[dict[str, Any]] = Field(default_factory=list)
    generation_goal: str = ""
    include_security_cases: bool = False


class ApiAutomationGenerationResult(BaseModel):
    summary: str
    cases: list[ApiGeneratedCase]
