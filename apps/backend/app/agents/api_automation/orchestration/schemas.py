from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioPlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: Literal["api_request", "condition", "wait", "poll", "assign"]
    endpoint_id: str | None = None
    name: str = ""
    request_overrides: dict[str, Any] = Field(default_factory=dict)
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    extractors: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    control_config: dict[str, Any] = Field(default_factory=dict)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True


class ScenarioPlanEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    condition: str = "success"


class ScenarioPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_name: str = ""
    nodes: list[ScenarioPlanNode] = Field(default_factory=list, max_length=100)
    edges: list[ScenarioPlanEdge] = Field(default_factory=list, max_length=200)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    unresolved_items: list[str] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.5, ge=0, le=1)
