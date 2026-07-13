from typing import Any, Literal

from pydantic import BaseModel, Field


ApiAssertionExpected = str | int | float | bool | None


class ApiAssertion(BaseModel):
    type: Literal[
        "status_code",
        "jsonpath_equals",
        "jsonpath_exists",
        "content_type",
        "header_exists",
        "header_equals",
        "body_not_empty",
        "body_sha256",
    ]
    path: str = ""
    expected: ApiAssertionExpected = None


class ApiGeneratedCase(BaseModel):
    title: str
    test_description: str = ""
    priority: str = "P2"
    endpoint_id: str
    coverage: Literal["positive", "negative", "boundary", "security", "scenario"] = "positive"
    source: Literal["ai_generated", "manual", "approved_test_case"] = "ai_generated"
    request: dict[str, Any]
    test_data: dict[str, Any] = Field(default_factory=dict)
    assertions: list[ApiAssertion]


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
