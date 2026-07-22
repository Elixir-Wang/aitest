from __future__ import annotations

import math
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WaitTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_seconds: float = Field(ge=0.1)
    max_seconds: float = Field(ge=0.1)

    @model_validator(mode="after")
    def validate_range(self) -> "WaitTime":
        if self.max_seconds < self.min_seconds:
            raise ValueError("max wait time cannot be less than min wait time")
        return self


class HttpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_parameters: dict[str, Any] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    timeout_seconds: float = Field(default=30, gt=0, le=600)


class AssertionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["status_code", "jsonpath_exists", "jsonpath_equals"]
    status_codes: list[int] = Field(default_factory=list)
    json_path: str = ""
    expected: Any = None

    @model_validator(mode="after")
    def validate_rule(self) -> "AssertionRule":
        if self.kind == "status_code" and not self.status_codes:
            raise ValueError("status code assertion requires at least one status code")
        if self.kind != "status_code" and not self.json_path.strip():
            raise ValueError("JSONPath assertion requires json_path")
        return self


class HttpStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["http"] = "http"
    endpoint_id: str = Field(min_length=1)
    request: HttpRequest
    assertions: list[AssertionRule] = Field(min_length=1)


class ManagedPersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["default"] = "default"
    name: str = Field(default="默认用户", min_length=1, max_length=80)
    wait_time: WaitTime
    steps: list[HttpStep] = Field(min_length=1)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personas: list[ManagedPersona] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_v1_shape(self) -> "ScenarioDefinition":
        if len(self.personas) != 1:
            raise ValueError("V1 requires exactly one persona")
        if len(self.personas[0].steps) != 1:
            raise ValueError("V1 requires exactly one HTTP step")
        return self


class FixedLoadProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed"] = "fixed"
    target_users: int = Field(ge=1)
    spawn_rate: float = Field(gt=0)
    warmup_seconds: int = Field(ge=0)
    measurement_seconds: int = Field(ge=1)
    stop_timeout_seconds: int = Field(default=10, ge=0)

    @property
    def total_run_seconds(self) -> int:
        return math.ceil(self.target_users / self.spawn_rate) + self.warmup_seconds + self.measurement_seconds


class LoadStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    target_users: int = Field(ge=1)
    spawn_rate: float = Field(gt=0)
    hold_seconds: int = Field(ge=1)
    record_metrics: bool


class StagedLoadProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["staged"] = "staged"
    stages: list[LoadStage] = Field(min_length=1)
    stop_timeout_seconds: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def require_measured_stage(self) -> "StagedLoadProfile":
        if not any(stage.record_metrics for stage in self.stages):
            raise ValueError("staged load requires at least one measured stage")
        return self

    @property
    def total_run_seconds(self) -> int:
        previous_users = 0
        duration = 0
        for stage in self.stages:
            duration += math.ceil(abs(stage.target_users - previous_users) / stage.spawn_rate) + stage.hold_seconds
            previous_users = stage.target_users
        return duration


LoadProfile = Union[FixedLoadProfile, StagedLoadProfile]


class PerformanceDataSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["fixed", "json", "csv"] = "fixed"
    selection_strategy: Literal["sequential_loop", "random"] = "sequential_loop"
    rows: list[dict[str, Any]] = Field(default_factory=list)
    dataset_id: str | None = None


class QualityGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_fail_ratio: float | None = Field(default=None, ge=0, le=1)
    max_average_response_time_ms: float | None = Field(default=None, gt=0)
    max_p95_response_time_ms: float | None = Field(default=None, gt=0)
    min_average_rps: float | None = Field(default=None, ge=0)
    min_request_count: int | None = Field(default=None, ge=1)


class SafetyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    window_seconds: int = Field(default=10, ge=1)
    max_fail_ratio: float = Field(default=0.5, ge=0, le=1)
    consecutive_windows: int = Field(default=3, ge=1)


class PerformanceScenarioCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    api_environment_id: str = Field(min_length=1)
    scenario_definition: ScenarioDefinition
    load_profile: LoadProfile = Field(discriminator="mode")
    data_source: PerformanceDataSource = Field(default_factory=PerformanceDataSource)
    quality_gate: QualityGate = Field(default_factory=QualityGate)
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)


class PerformanceScenarioUpdateIn(PerformanceScenarioCreateIn):
    pass
