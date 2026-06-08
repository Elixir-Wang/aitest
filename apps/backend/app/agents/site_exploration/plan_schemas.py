from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
ExecutionPolicy = Literal["auto", "manual", "confirm_before_submit", "confirm_external_call"]


class ExplorationPlanModule(BaseModel):
    module_name: str = Field(min_length=1, description="根据页面事实识别出的探索模块名称。")
    reason: str = Field(min_length=1, description="为什么认为这是一个探索模块，只能引用输入中的页面事实。")
    entry_hint: str = Field(default="", description="页面中的模块入口线索，例如导航、按钮、链接或当前页面区域。")
    steps: list[str] = Field(default_factory=list, description="后续探索该模块的步骤。")
    expected_evidence: list[str] = Field(default_factory=list, description="探索该模块时应保留的证据。")
    risk_level: RiskLevel = "low"
    execution_policy: ExecutionPolicy = "auto"


class ExplorationPlanInput(BaseModel):
    run: dict = Field(default_factory=dict)
    page_facts: dict = Field(default_factory=dict)
    scope_constraints: dict = Field(default_factory=dict)


class ExplorationPlanOutput(BaseModel):
    summary: str = Field(min_length=1, description="本次模块计划生成结论。")
    modules: list[ExplorationPlanModule] = Field(default_factory=list, description="探索范围内识别出的模块计划。")
