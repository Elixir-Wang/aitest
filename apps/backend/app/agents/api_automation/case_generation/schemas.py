import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ApiAssertionExpected = str | int | float | bool | None
JSON_ASSERTION_TYPES = {"string", "number", "boolean", "object", "array", "null"}


class ApiAssertion(BaseModel):
    type: Literal[
        "status_code",
        "jsonpath_equals",
        "jsonpath_exists",
        "jsonpath_type",
        "content_type",
        "header_exists",
        "header_equals",
        "body_not_empty",
        "body_sha256",
    ]
    path: str = ""
    expected: ApiAssertionExpected = None

    @model_validator(mode="after")
    def _validate_jsonpath_type(self) -> "ApiAssertion":
        if self.type != "jsonpath_type":
            return self
        if not self.path:
            raise ValueError("jsonpath_type 必须指定 JSONPath。")
        if self.expected not in JSON_ASSERTION_TYPES:
            raise ValueError("jsonpath_type 的 expected 必须是标准 JSON 类型。")
        return self


def _unwrap_text_encoded_object(value: Any, *, field_name: str) -> Any:
    """Normalize the single-key object encoding emitted by some tool-call providers."""
    if not isinstance(value, dict) or set(value) != {"$text"}:
        return value
    text = value["$text"]
    if not isinstance(text, str):
        raise ValueError(f"{field_name}.$text 必须是 JSON 字符串对象。")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name}.$text 不是有效 JSON 对象。") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{field_name}.$text 必须解码为 JSON 对象。")
    return decoded


class ApiGeneratedRequest(BaseModel):
    """Executable request contract returned by the API case-generation agent."""

    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    query: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    files: Any = None

    @model_validator(mode="before")
    @classmethod
    def _unwrap_text_encoded_request(cls, value: Any) -> Any:
        return _unwrap_text_encoded_object(value, field_name="request")


class ApiGeneratedCase(BaseModel):
    title: str
    test_description: str = ""
    priority: str = "P2"
    endpoint_id: str
    test_point_key: str
    oracle_status: Literal["confirmed", "inferred", "needs_confirmation"]
    coverage: Literal["positive", "negative", "boundary", "security", "scenario"] = "positive"
    source: Literal["ai_generated", "manual", "approved_test_case"] = "ai_generated"
    request: ApiGeneratedRequest
    test_data: dict[str, Any] = Field(default_factory=dict)
    assertions: list[ApiAssertion]
    generation_notes: str = ""

    @field_validator("test_data", mode="before")
    @classmethod
    def _unwrap_text_encoded_test_data(cls, value: Any) -> Any:
        return _unwrap_text_encoded_object(value, field_name="test_data")


class ApiAutomationGenerationInput(BaseModel):
    project_id: str
    endpoints: list[dict[str, Any]]
    environment_summary: dict[str, Any] = Field(default_factory=dict)
    source_test_cases: list[dict[str, Any]] = Field(default_factory=list)
    generation_goal: str = ""
    include_security_cases: bool = False
    planned_test_points: list[dict[str, Any]] = Field(default_factory=list)


class ApiAutomationGenerationResult(BaseModel):
    summary: str
    cases: list[ApiGeneratedCase]
