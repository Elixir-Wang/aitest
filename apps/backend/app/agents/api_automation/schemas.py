from typing import Any, Literal

from pydantic import BaseModel, Field


ApiAssertionExpected = str | int | float | bool | None


class ApiAssertion(BaseModel):
    type: Literal["status_code", "jsonpath_equals", "jsonpath_exists"]
    path: str = ""
    expected: ApiAssertionExpected = None


class ApiGeneratedCase(BaseModel):
    title: str
    priority: str = "P2"
    endpoint_id: str
    tags: list[str] = Field(default_factory=list)
    coverage: Literal["positive", "negative", "boundary", "security", "scenario"] = "positive"
    source: Literal["ai_generated", "manual", "approved_test_case"] = "ai_generated"
    preconditions: list[str] = Field(default_factory=list)
    request: dict[str, Any]
    test_data: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any]
    assertions: list[ApiAssertion]
    variables: dict[str, Any] = Field(default_factory=dict)
    data_origin: dict[str, Any] = Field(default_factory=dict)
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
