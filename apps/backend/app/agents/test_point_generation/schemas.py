from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TestPointCategory = Literal["功能", "异常", "边界", "权限", "数据", "状态", "性能", "安全", "兼容性"]
TestPointPriority = Literal["P0", "P1", "P2", "P3"]


class TestPointGenerationInput(BaseModel):
    requirement_name: str = Field(min_length=1)
    requirement_content: str = Field(min_length=1)
    requirement_version_id: str = Field(min_length=1)

    @field_validator("requirement_name", "requirement_content", "requirement_version_id", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GeneratedTestPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    module: str = Field(default="", max_length=120)
    category: TestPointCategory
    priority: TestPointPriority
    description: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    notes: str = ""
    requirement_obligation_keys: list[str] = Field(min_length=1)


class GeneratedTestPointDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = Field(min_length=1, max_length=120)
    test_point: str = Field(
        min_length=1,
        max_length=240,
        description="简短且全局唯一的测试目标名称，不得拼接完整所属模块或模块层级路径，必要时用最短业务对象自然区分",
    )
    priority: TestPointPriority
    requirement_obligation_keys: list[str] = Field(min_length=1)


class TestPointGenerationDraftResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[GeneratedTestPointDraft] = Field(min_length=1)


class TestPointGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[GeneratedTestPoint] = Field(min_length=1)
    unsupported_assumptions: list[str] = Field(default_factory=list)


class RequirementObligation(BaseModel):
    obligation_key: str = Field(min_length=1, max_length=120)
    source_section: str = Field(min_length=1, max_length=240)
    statement: str = Field(min_length=1)
    obligation_type: Literal[
        "business_rule",
        "module",
        "flow",
        "threshold",
        "compatibility",
        "display",
        "logging",
        "performance",
        "permission",
        "security",
        "exception",
    ]
    modules: list[str] = Field(default_factory=list)
    thresholds: list[str] = Field(default_factory=list)
    explicit: bool = True
    test_required: bool = True


class RequirementObligationExtractionResult(BaseModel):
    obligations: list[RequirementObligation] = Field(min_length=1)
    unverifiable_items: list[str] = Field(default_factory=list)


class TestPointCoverageResult(BaseModel):
    status: Literal["complete", "incomplete", "invalid"]
    obligation_count: int
    covered_obligation_count: int
    missing_obligation_keys: list[str] = Field(default_factory=list)
    unknown_obligation_keys: list[str] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)


__all__ = [
    "GeneratedTestPoint",
    "GeneratedTestPointDraft",
    "RequirementObligation",
    "RequirementObligationExtractionResult",
    "TestPointCoverageResult",
    "TestPointGenerationInput",
    "TestPointGenerationResult",
    "TestPointGenerationDraftResult",
    "TestPointCategory",
    "TestPointPriority",
]
