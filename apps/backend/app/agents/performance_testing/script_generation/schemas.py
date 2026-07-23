"""Structured models used by the performance script generation capability."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocustRequestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    name: str
    path_parameters: dict[str, Any] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    timeout_seconds: float = Field(gt=0, le=600)


class LocustLoadPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "gradient", "stress", "spike", "endurance"] = "fixed"
    wait_time_min_seconds: float = Field(ge=0.1)
    wait_time_max_seconds: float = Field(ge=0.1)
    stages: list["LocustLoadStagePlan"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_configuration(self) -> "LocustLoadPlan":
        if self.wait_time_min_seconds > self.wait_time_max_seconds:
            raise ValueError("wait_time_min_seconds must not exceed wait_time_max_seconds")
        if self.mode != "fixed" and not self.stages:
            raise ValueError("stages must not be empty when mode is not fixed")
        return self


class LocustLoadStagePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    target_users: int = Field(gt=0)
    spawn_rate: float = Field(gt=0)
    hold_seconds: int = Field(gt=0)
    order: int = Field(ge=0)


class LocustDataPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["fixed", "json", "csv"] = "fixed"
    selection_strategy: Literal["sequential_loop", "random"] = "sequential_loop"
    json_rows: list[dict[str, Any]] = Field(default_factory=list)


class LocustSuccessRulePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["status_code", "jsonpath_exists", "jsonpath_equals"]
    status_codes: list[int] = Field(default_factory=list)
    json_path: str = ""
    expected: Any = None


class LocustScriptPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    test_id: str
    random_seed: int | None = None
    request: LocustRequestPlan
    load: LocustLoadPlan
    data: LocustDataPlan = Field(default_factory=LocustDataPlan)
    success_rules: list[LocustSuccessRulePlan]


class ScriptValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    code_hash: str = ""
