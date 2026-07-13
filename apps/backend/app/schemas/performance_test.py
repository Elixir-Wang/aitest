from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PerformanceRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_parameters: dict[str, Any] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    random_seed: int | None = None


class PerformanceLoadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: int = Field(default=10, ge=1)
    spawn_rate: float = Field(default=1, gt=0)
    measurement_duration_seconds: int = Field(default=60, ge=1)
    wait_time_min_seconds: float = Field(default=1, ge=0.1)
    wait_time_max_seconds: float = Field(default=3, ge=0.1)
    request_timeout_seconds: float = Field(default=30, gt=0, le=600)

    @model_validator(mode="after")
    def validate_wait_time_range(self) -> "PerformanceLoadConfig":
        if self.wait_time_max_seconds < self.wait_time_min_seconds:
            raise ValueError("最大等待时间不能小于最小等待时间")
        return self


class PerformanceGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_fail_ratio: float | None = Field(default=None, ge=0, le=1)
    max_average_response_time_ms: float | None = Field(default=None, gt=0)
    max_p95_response_time_ms: float | None = Field(default=None, gt=0)
    min_average_rps: float | None = Field(default=None, gt=0)


class PerformanceSuccessRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["status_code", "jsonpath_exists", "jsonpath_equals"]
    status_codes: list[int] = Field(default_factory=list)
    json_path: str = ""
    expected: Any = None

    @model_validator(mode="after")
    def validate_rule(self) -> "PerformanceSuccessRule":
        if self.kind == "status_code":
            if not self.status_codes:
                raise ValueError("状态码规则必须至少包含一个允许的状态码")
            if any(code < 100 or code > 599 for code in self.status_codes):
                raise ValueError("HTTP 状态码必须在 100 到 599 之间")
        elif not self.json_path.strip():
            raise ValueError("JSONPath 规则必须填写 json_path")
        return self


def default_success_rules() -> list[PerformanceSuccessRule]:
    return [PerformanceSuccessRule(kind="status_code", status_codes=[200])]


class PerformanceTestCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    target_type: Literal["endpoint"] = "endpoint"
    endpoint_id: str = Field(min_length=1)
    api_environment_id: str = Field(min_length=1)
    source_api_test_case_id: str | None = None
    request_config: PerformanceRequestConfig = Field(default_factory=PerformanceRequestConfig)
    load_config: PerformanceLoadConfig = Field(default_factory=PerformanceLoadConfig)
    performance_goal: PerformanceGoal = Field(default_factory=PerformanceGoal)
    success_rules: list[PerformanceSuccessRule] = Field(default_factory=default_success_rules, min_length=1)

    @field_validator("name", "description", "endpoint_id", "api_environment_id", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class PerformanceTestUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    endpoint_id: str | None = Field(default=None, min_length=1)
    api_environment_id: str | None = Field(default=None, min_length=1)
    source_api_test_case_id: str | None = None
    request_config: PerformanceRequestConfig | None = None
    load_config: PerformanceLoadConfig | None = None
    performance_goal: PerformanceGoal | None = None
    success_rules: list[PerformanceSuccessRule] | None = Field(default=None, min_length=1)

    @field_validator("name", "description", "endpoint_id", "api_environment_id", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class PerformanceRequestPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_id: str = Field(min_length=1)
    source_api_test_case_id: str | None = None


class PerformanceEndpointSummary(BaseModel):
    id: str
    method: str
    path: str
    name: str


class PerformanceRequestPreviewOut(BaseModel):
    endpoint: PerformanceEndpointSummary
    request_config: PerformanceRequestConfig
    success_rules: list[PerformanceSuccessRule]
    provenance: dict[str, str]
    warnings: list[str]


class PerformanceTestOut(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    target_type: Literal["endpoint"]
    endpoint_id: str | None
    endpoint_name: str
    endpoint_method: str
    endpoint_path: str
    api_environment_id: str | None
    environment_name: str
    source_api_test_case_id: str | None
    request_config: PerformanceRequestConfig
    load_config: PerformanceLoadConfig
    performance_goal: PerformanceGoal
    success_rules: list[PerformanceSuccessRule]
    latest_run_status: str
    latest_goal_status: str
    latest_run_at: str | None
    created_by: str
    created_at: str
    updated_at: str
