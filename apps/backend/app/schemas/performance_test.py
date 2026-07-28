from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator


class PerformanceRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_parameters: dict[str, Any] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    random_seed: int | None = None
    transport: Literal["http", "sse"] = "http"
    sse: "PerformanceSseConfig | None" = None

    @model_validator(mode="after")
    def validate_sse(self) -> "PerformanceRequestConfig":
        if self.transport == "sse" and self.sse is None:
            raise ValueError("SSE 请求必须配置 sse")
        if self.transport == "http" and self.sse is not None:
            raise ValueError("HTTP 请求不能配置 sse")
        return self


class PerformanceSseMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(default="", max_length=120)
    source: Literal["data_json", "data_text", "event_name"]
    path: str = Field(default="", max_length=512)
    operator: Literal["exists", "non_empty", "equals", "contains", "matches"]
    expected: Any = None

    @model_validator(mode="after")
    def validate_match(self) -> "PerformanceSseMatch":
        from app.services.performance_testing.sse import validate_metric_rule

        validate_metric_rule({"id": "rule", "match": self.model_dump(mode="json")})
        return self


class PerformanceSseMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    match: PerformanceSseMatch
    occurrence: Literal["first"] = "first"
    missing_policy: Literal["record_null", "fail_request", "ignore"] = "record_null"

    @model_validator(mode="after")
    def validate_metric(self) -> "PerformanceSseMetric":
        from app.services.performance_testing.sse import validate_metric_rule

        validate_metric_rule(self.model_dump(mode="json"))
        return self


class PerformanceSseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_stream_seconds: float = Field(default=60, gt=0, le=600)
    end_rule: PerformanceSseMatch | None = None
    metrics: list[PerformanceSseMetric] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_metric_ids(self) -> "PerformanceSseConfig":
        if len({metric.id for metric in self.metrics}) != len(self.metrics):
            raise ValueError("SSE 指标 ID 不能重复")
        return self


class PerformanceLoadStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    target_users: int = Field(gt=0)
    spawn_rate: float = Field(gt=0)
    hold_seconds: int = Field(gt=0)
    order: int = Field(ge=0)


class PerformanceLoadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "gradient", "stress", "spike", "endurance"] = "fixed"
    users: int = Field(default=10, ge=1)
    spawn_rate: float = Field(default=1, gt=0)
    measurement_duration_seconds: int = Field(default=60, ge=1)
    wait_time_min_seconds: float = Field(default=1, ge=0.1)
    wait_time_max_seconds: float = Field(default=3, ge=0.1)
    request_timeout_seconds: float = Field(default=30, gt=0, le=600)
    stages: list[PerformanceLoadStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_wait_time_range(self) -> "PerformanceLoadConfig":
        if self.wait_time_max_seconds < self.wait_time_min_seconds:
            raise ValueError("最大等待时间不能小于最小等待时间")
        if self.mode == "fixed":
            if self.stages:
                raise ValueError("固定负载不需要配置阶段")
            return self
        if not self.stages:
            raise ValueError("非固定负载至少需要一个阶段")
        ordered = sorted(self.stages, key=lambda stage: stage.order)
        if [stage.order for stage in ordered] != list(range(len(ordered))):
            raise ValueError("阶段顺序必须从 0 连续编号")
        if self.mode in {"gradient", "stress", "endurance"}:
            users = [stage.target_users for stage in ordered]
            if users != sorted(users):
                raise ValueError("该测试模式的目标用户数必须逐阶段递增")
        if self.mode == "spike" and len(ordered) < 3:
            raise ValueError("峰值测试至少需要正常、峰值和恢复三个阶段")
        if self.mode == "spike" and not (
            ordered[1].target_users > ordered[0].target_users
            and ordered[-1].target_users < ordered[1].target_users
        ):
            raise ValueError("峰值测试必须包含升压和恢复阶段")
        return self


class PerformanceDataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["fixed", "json", "csv"] = "fixed"
    selection_strategy: Literal["sequential_loop", "random"] = "sequential_loop"
    json_rows: list[dict[str, Any]] = Field(default_factory=list)
    csv_file_name: str = ""
    csv_file_path: str = ""

    @model_validator(mode="after")
    def validate_source(self) -> "PerformanceDataConfig":
        if self.source == "json" and not self.json_rows:
            raise ValueError("JSON 数据源至少需要一条数据")
        if self.source == "csv" and not self.csv_file_name:
            raise ValueError("CSV 数据源必须包含文件名")
        if self.source == "fixed" and self.json_rows:
            raise ValueError("固定数据源不能包含 JSON 数据列表")
        return self


class PerformanceCircuitBreaker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    window_seconds: int = Field(default=10, ge=1)
    max_fail_ratio: float = Field(default=0.5, ge=0, le=1)
    consecutive_windows: int = Field(default=3, ge=1)


class PerformanceGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_fail_ratio: float = Field(default=0.0, ge=0, le=1)
    max_average_response_time_ms: float = Field(default=1000.0, gt=0)
    max_p95_response_time_ms: float | None = Field(default=None, gt=0)
    min_average_rps: float | None = Field(default=None, ge=0)


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

    @model_serializer(mode="plain")
    def serialize_rule(self) -> dict[str, Any]:
        if self.kind == "status_code":
            return {"kind": self.kind, "status_codes": self.status_codes}
        if self.kind == "jsonpath_exists":
            return {"kind": self.kind, "json_path": self.json_path}
        return {"kind": self.kind, "json_path": self.json_path, "expected": self.expected}


def default_success_rules() -> list[PerformanceSuccessRule]:
    return [PerformanceSuccessRule(kind="status_code", status_codes=[200])]


class PerformanceTestCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    target_type: Literal["endpoint"] = "endpoint"
    endpoint_id: str = Field(min_length=1)
    api_environment_id: str = Field(min_length=1)
    request_config: PerformanceRequestConfig = Field(default_factory=PerformanceRequestConfig)
    load_config: PerformanceLoadConfig = Field(default_factory=PerformanceLoadConfig)
    data_config: PerformanceDataConfig = Field(default_factory=PerformanceDataConfig)
    circuit_breaker: PerformanceCircuitBreaker = Field(default_factory=PerformanceCircuitBreaker)
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
    request_config: PerformanceRequestConfig | None = None
    load_config: PerformanceLoadConfig | None = None
    data_config: PerformanceDataConfig | None = None
    circuit_breaker: PerformanceCircuitBreaker | None = None
    performance_goal: PerformanceGoal | None = None
    success_rules: list[PerformanceSuccessRule] | None = Field(default=None, min_length=1)

    @field_validator("name", "description", "endpoint_id", "api_environment_id", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class PerformanceRequestPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_id: str = Field(min_length=1)
    api_environment_id: str | None = None


class PerformanceSseRulePreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample: str = Field(min_length=1, max_length=65_536)
    sse: PerformanceSseConfig


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
    latest_script_id: str | None = None
    request_config: PerformanceRequestConfig
    load_config: PerformanceLoadConfig
    data_config: PerformanceDataConfig
    circuit_breaker: PerformanceCircuitBreaker
    performance_goal: PerformanceGoal
    success_rules: list[PerformanceSuccessRule]
    latest_run_status: str
    latest_goal_status: str
    latest_run_at: str | None
    created_by: str
    created_at: str
    updated_at: str


class PerformanceScriptConfigurationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, Any] | None = None
    load: dict[str, Any] | None = None
    success_rules: list[dict[str, Any]] | None = None
    random_seed: int | None = None


class PerformanceScriptOut(BaseModel):
    id: str
    performance_test_id: str
    project_id: str
    generation_source: str
    model_id: str
    prompt_version: str
    plan: dict[str, Any]
    code: str
    assumptions: list[Any]
    required_runtime_variables: list[str]
    validation_status: str
    validation_result: dict[str, Any]
    confirmed_by: str | None
    confirmed_at: str | None
    created_at: str
    updated_at: str
    runtime_preview: dict[str, Any] | None = None
