"""需求理解相关 Schemas."""

from typing import Literal
from pydantic import BaseModel, Field


class BusinessObject(BaseModel):
    """业务对象"""
    name: str
    description: str = ""
    fields: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list, description="与其他对象的关系")


class BusinessRule(BaseModel):
    """业务规则"""
    rule_id: str
    rule_type: Literal["validation", "calculation", "workflow", "permission", "constraint"]
    description: str
    condition: str = ""
    example: str = ""


class StateFlow(BaseModel):
    """状态流转"""
    object_name: str
    states: list[str]
    transitions: list["StateTransition"] = Field(default_factory=list)


class StateTransition(BaseModel):
    """状态转换"""
    from_state: str
    to_state: str
    trigger: str
    condition: str = ""


class Dependency(BaseModel):
    """依赖关系"""
    source_module: str
    target_module: str
    dependency_type: Literal["data", "api", "service", "event"]
    description: str


class Risk(BaseModel):
    """风险"""
    risk_id: str
    category: Literal["technical", "business", "resource", "schedule", "external"]
    description: str
    impact: Literal["high", "medium", "low"]
    likelihood: Literal["high", "medium", "low"]
    mitigation: str = ""


class Assumption(BaseModel):
    """假设"""
    assumption_id: str
    description: str
    validation_needed: str
    risk_if_invalid: str


class RequirementModule(BaseModel):
    """需求模块"""
    module_key: str
    module_name: str
    summary: str
    capabilities: list[str] = Field(default_factory=list, description="功能点列表")
    business_objects: list[BusinessObject] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    state_flows: list[StateFlow] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="依赖的其他模块")


class RequirementUnderstandingOutput(BaseModel):
    """需求理解输出"""
    modules: list[RequirementModule] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    understanding_summary: str = Field(description="需求理解总结")


__all__ = [
    "BusinessObject",
    "BusinessRule",
    "StateFlow",
    "StateTransition",
    "Dependency",
    "Risk",
    "Assumption",
    "RequirementModule",
    "RequirementUnderstandingOutput",
]
