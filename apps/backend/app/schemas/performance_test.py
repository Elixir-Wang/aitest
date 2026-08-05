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
    scenario_step_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_sse(self) -> "PerformanceRequestConfig":
        if self.transport == "sse" and self.sse is None:
            raise ValueError("SSE 请求必须配置 sse")
        if self.transport == "http" and self.sse is not None:
            raise ValueError("HTTP 请求不能配置 sse")
        if self.transport == "http" and self.scenario_step_id is not None:
            raise ValueError("HTTP 请求不能配置 SSE 场景步骤")
        if self.transport == "sse" and self.sse is not None and self.scenario_step_id is not None:
            for metric in self.sse.metrics:
                source_request_id = metric.timing.source_request_id
                if source_request_id is not None and source_request_id != self.scenario_step_id:
                    raise ValueError("SSE 指标时间起点必须绑定当前 SSE 场景步骤")
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


class PerformanceSseMetricTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["request"] = "request"
    start: Literal["request_started"] = "request_started"
    source_request_id: str | None = Field(default=None, min_length=1, max_length=120)
    source_request_name: str | None = Field(default=None, min_length=1, max_length=240)


class PerformanceSseMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    category: Literal[
        "first_output",
        "milestone_start",
        "milestone_end",
        "completion",
        "first_external_action",
        "state_transition",
        "custom_event",
    ] = "custom_event"
    timing: PerformanceSseMetricTiming = Field(default_factory=PerformanceSseMetricTiming)
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
    stress_start_users: int = Field(default=10, ge=1)
    stress_max_users: int = Field(default=100, ge=2)
    stress_step_users: int = Field(default=10, ge=1)
    stress_hold_seconds: int = Field(default=180, ge=1)
    stages: list[PerformanceLoadStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_wait_time_range(self) -> "PerformanceLoadConfig":
        if self.wait_time_max_seconds < self.wait_time_min_seconds:
            raise ValueError("最大等待时间不能小于最小等待时间")
        if self.mode == "fixed":
            if self.stages:
                raise ValueError("固定负载不需要配置阶段")
            return self
        if self.mode == "stress":
            if self.stress_max_users <= self.stress_start_users:
                raise ValueError("最大用户数必须大于初始用户数")
            targets = list(range(self.stress_start_users, self.stress_max_users, self.stress_step_users))
            if not targets or targets[-1] != self.stress_max_users:
                targets.append(self.stress_max_users)
            self.stages = [
                PerformanceLoadStage(
                    name=f"压力阶段 {order + 1}",
                    target_users=target_users,
                    spawn_rate=self.spawn_rate,
                    hold_seconds=self.stress_hold_seconds,
                    order=order,
                )
                for order, target_users in enumerate(targets)
            ]
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


class PerformanceSseMetricGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    percentile: Literal["p95", "p99"]
    operator: Literal["lte"] = "lte"
    target_ms: float = Field(gt=0)


class PerformanceGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_fail_ratio: float = Field(default=0.0, ge=0, le=1)
    max_average_response_time_ms: float = Field(default=1000.0, gt=0)
    max_p95_response_time_ms: float | None = Field(default=None, gt=0)
    min_average_rps: float | None = Field(default=None, ge=0)
    sse_metric_goals: list[PerformanceSseMetricGoal] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_sse_metric_goals(self) -> "PerformanceGoal":
        keys = [(goal.metric_id, goal.percentile) for goal in self.sse_metric_goals]
        if len(set(keys)) != len(keys):
            raise ValueError("同一 SSE 指标和分位数只能配置一个性能目标")
        return self


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
    target_type: Literal["endpoint", "scenario"] = "endpoint"
    endpoint_id: str | None = Field(default=None, min_length=1)
    scenario_id: str | None = Field(default=None, min_length=1)
    api_environment_id: str = Field(min_length=1)
    request_config: PerformanceRequestConfig = Field(default_factory=PerformanceRequestConfig)
    load_config: PerformanceLoadConfig = Field(default_factory=PerformanceLoadConfig)
    data_config: PerformanceDataConfig = Field(default_factory=PerformanceDataConfig)
    circuit_breaker: PerformanceCircuitBreaker = Field(default_factory=PerformanceCircuitBreaker)
    performance_goal: PerformanceGoal = Field(default_factory=PerformanceGoal)
    success_rules: list[PerformanceSuccessRule] = Field(default_factory=default_success_rules, min_length=1)

    @field_validator("name", "description", "endpoint_id", "scenario_id", "api_environment_id", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_target(self) -> "PerformanceTestCreateIn":
        if self.target_type == "endpoint" and (not self.endpoint_id or self.scenario_id):
            raise ValueError("接口性能测试必须且只能选择一个接口")
        if self.target_type == "scenario" and (not self.scenario_id or self.endpoint_id):
            raise ValueError("场景性能测试必须且只能选择一个接口场景")
        if self.target_type == "endpoint" and self.request_config.scenario_step_id is not None:
            raise ValueError("单接口性能测试不能配置场景步骤")
        if (
            self.target_type == "scenario"
            and self.request_config.transport == "sse"
            and not self.request_config.scenario_step_id
        ):
            raise ValueError("场景 SSE 性能测试必须选择一个接口步骤")
        validate_sse_goal_references(
            self.request_config.model_dump(mode="json"),
            self.performance_goal.model_dump(mode="json", exclude_none=True),
        )
        return self


class PerformanceTestUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    target_type: Literal["endpoint", "scenario"] | None = None
    endpoint_id: str | None = Field(default=None, min_length=1)
    scenario_id: str | None = Field(default=None, min_length=1)
    api_environment_id: str | None = Field(default=None, min_length=1)
    request_config: PerformanceRequestConfig | None = None
    load_config: PerformanceLoadConfig | None = None
    data_config: PerformanceDataConfig | None = None
    circuit_breaker: PerformanceCircuitBreaker | None = None
    performance_goal: PerformanceGoal | None = None
    success_rules: list[PerformanceSuccessRule] | None = Field(default=None, min_length=1)

    @field_validator("name", "description", "endpoint_id", "scenario_id", "api_environment_id", mode="before")
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


class PerformanceSseMetricGenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_id: str | None = Field(default=None, min_length=1)
    scenario_id: str | None = Field(default=None, min_length=1)
    scenario_step_id: str | None = Field(default=None, min_length=1, max_length=120)
    api_environment_id: str = Field(min_length=1)
    path_parameters: dict[str, Any] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    max_stream_seconds: float = Field(default=60, gt=0, le=600)
    candidate_sse: PerformanceSseConfig | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "PerformanceSseMetricGenerateIn":
        endpoint_target = bool(self.endpoint_id) and not self.scenario_id and not self.scenario_step_id
        scenario_target = bool(self.scenario_id) and bool(self.scenario_step_id) and not self.endpoint_id
        if not endpoint_target and not scenario_target:
            raise ValueError("SSE 指标生成必须选择单接口，或选择接口场景及其目标步骤")
        return self


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
    target_type: Literal["endpoint", "scenario"]
    endpoint_id: str | None
    endpoint_name: str
    endpoint_method: str
    endpoint_path: str
    scenario_id: str | None
    scenario_name: str
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
    created_at: str
    updated_at: str
    runtime_preview: dict[str, Any] | None = None


def validate_sse_goal_references(request_config: dict[str, Any], performance_goal: dict[str, Any]) -> None:
    goals = performance_goal.get("sse_metric_goals") or []
    if not goals:
        return
    if request_config.get("transport") != "sse" or not isinstance(request_config.get("sse"), dict):
        raise ValueError("SSE 指标目标只能用于 SSE 性能测试")
    metric_ids = {
        str(metric.get("id") or "")
        for metric in request_config["sse"].get("metrics") or []
        if isinstance(metric, dict)
    }
    unknown = sorted({str(goal.get("metric_id") or "") for goal in goals if goal.get("metric_id") not in metric_ids})
    if unknown:
        raise ValueError(f"SSE 指标目标引用了不存在的指标: {', '.join(unknown)}")
